"""Uploaded paper -> top similar repository papers with High/Moderate bands.

This MUST mirror archeion-ocr/scripts/embed_papers.py (same cleaning,
chunking, model settings, averaging, normalization), or the scores are
not comparable with the F1-selected threshold.
"""
import math
from functools import lru_cache

import numpy as np
import pdfplumber
from django.conf import settings

from .clean_ocr import clean_text
from .vectors import bytes_to_vector

CHUNK_WORDS = 300
OVERLAP_WORDS = 50
MAX_TOKENS = 512
TOP_K = 5


def _inside_any(obj, boxes):
    """True if a character/line sits inside any detected table box."""
    x = (obj.get("x0", 0) + obj.get("x1", 0)) / 2
    y = (obj.get("top", 0) + obj.get("bottom", 0)) / 2
    return any(x0 <= x <= x1 and top <= y <= bottom for x0, top, x1, bottom in boxes)


def extract_pdf_text(file_obj):
    """Extract text page by page, skipping table regions.

    pdfplumber doesn't output markdown tables, so clean_ocr's table
    removal won't catch them. Dropping table areas here keeps uploads
    consistent with the repository papers.
    """
    pages = []
    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            boxes = [t.bbox for t in page.find_tables()]
            if boxes:
                page = page.filter(lambda obj, b=boxes: not _inside_any(obj, b))
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def chunk_words(text):
    """Fixed 300-word chunks with 50-word overlap."""
    words = text.split()
    step = CHUNK_WORDS - OVERLAP_WORDS
    last_start = max(len(words) - OVERLAP_WORDS, 1)
    chunks = [" ".join(words[i:i + CHUNK_WORDS]) for i in range(0, last_start, step)]
    return [c for c in chunks if c]


@lru_cache(maxsize=1)
def get_model():
    """Load BGE-M3 once per server process (first call takes a while)."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("BAAI/bge-m3", device="cpu")
    model.max_seq_length = MAX_TOKENS
    return model


def embed_document(text):
    """Clean -> chunk -> embed each chunk -> average -> normalize (same as embed_papers.py)."""
    chunks = chunk_words(clean_text(text))
    if not chunks:
        raise ValueError("No readable text was found. If this is a scanned PDF, paste the text instead.")
    vectors = get_model().encode(chunks, batch_size=8, normalize_embeddings=True)
    mean = vectors.mean(axis=0)
    return mean / np.linalg.norm(mean)


@lru_cache(maxsize=1)
def load_corpus():
    """Repository papers, their stored vectors, and the corpus mean (cached).

    Restart the server after importing new papers so the cache refreshes.
    """
    from .models import Embedding
    rows = list(Embedding.objects.select_related("paper"))
    if not rows:
        raise ValueError("The repository has no embeddings yet.")
    papers = [row.paper for row in rows]
    matrix = np.vstack([bytes_to_vector(row.vector_data) for row in rows])
    return papers, matrix, matrix.mean(axis=0)


def centered_cosine(query, matrix, mean):
    """Cosine similarity after subtracting the corpus mean from both sides."""
    q = query - mean
    m = matrix - mean
    return (m @ q) / (np.linalg.norm(m, axis=1) * np.linalg.norm(q) + 1e-12)


def band_for(score):
    if score >= settings.SIMILARITY_HIGH_BAND:
        return "High"
    if score >= settings.SIMILARITY_THRESHOLD:
        return "Moderate"
    return "Low"


def find_similar(text):
    """Top 5 repository papers at or above the threshold, highest first."""
    papers, matrix, mean = load_corpus()
    scores = centered_cosine(embed_document(text), matrix, mean)
    results = []
    for i in np.argsort(-scores)[:TOP_K]:
        score = float(scores[i])
        if score < settings.SIMILARITY_THRESHOLD:
            break
        results.append({
            "paper_id": papers[i].pk,
            "title": papers[i].title,
            "score": round(score, 4),
            # floor, not round, so 0.389 shows 38% and stays "Moderate"
            "percent": math.floor(max(0.0, score) * 100),
            "band": band_for(score),
        })
    return results