from functools import lru_cache

import numpy as np
from django.db import transaction
from sentence_transformers import SentenceTransformer

from papers.models import Category, PaperCategory
from similarity.vectors import bytes_to_vector

# Category name -> description.
# v1: built from the child terms of the mapped ACM CCS 2012 node(s) (ACM, 2012).
# v2 (one revision after the first evaluation): same CCS nodes, plus the
# terms local capstone abstracts use for each topic, phrased positively.
CATEGORIES = {
    "Artificial Intelligence & Machine Learning":
        "Systems whose main contribution is an artificial intelligence or "
        "machine learning model: supervised and unsupervised learning, neural "
        "networks, regression and classification models trained on data, "
        "prediction, recommendation systems, knowledge representation and "
        "reasoning, and planning, scheduling and optimization algorithms.",
    "Natural Language Processing":
        "Systems that process human language: information extraction, machine "
        "translation, chatbots and dialogue systems, natural language generation, "
        "speech recognition, sentiment analysis, and text classification.",
    "Computer Vision & Image Processing":
        "Systems that analyze images and video from cameras: object detection, "
        "object recognition, tracking, image segmentation, face and biometric "
        "recognition, image-based detection and classification with convolutional "
        "neural networks, plant and crop disease detection from photos, and "
        "image processing.",
    "Internet of Things & Embedded Systems":
        "Systems built on embedded and cyber-physical hardware: sensor networks, "
        "sensors and actuators, microcontrollers, robotics, and embedded software "
        "for monitoring and automation.",
    "Networking & Cybersecurity":
        "Studies whose main focus is computer networks and information security: "
        "network architectures and network access control, protocols, "
        "cryptography and encryption algorithms, hashing and integrity "
        "verification, blockchain, secret sharing, authentication schemes, "
        "intrusion detection, and vulnerability assessment.",
    "Geographic Information Systems & Mapping":
        "Location-based systems whose main purpose is maps and geographic data: "
        "geographic information systems, GPS tracking of vehicles or people, "
        "location based services, route mapping and route optimization, "
        "evacuation maps, and campus or city locators.",
    "Data Analytics & Visualization":
        "Decision support and data analysis systems whose main output is "
        "analysis: forecasting, time-series models such as ARIMA and SARIMA, "
        "sales and demand forecasting, decision support, data mining, "
        "descriptive statistics, incident and trend analysis, and dashboards "
        "and visualization of statistics.",
    "Games, Multimedia & AR/VR":
        "Computer games and interactive multimedia: educational and entertainment "
        "games, gamified learning apps, quizzes, interactive lessons and "
        "simulations, multimedia content creation, augmented reality, and "
        "virtual reality.",
    "Information & Management Systems":
        "Web and mobile information systems that manage an organization's "
        "records and transactions: records management, inventory, billing and "
        "payments, appointments and reservations, attendance and clearance, "
        "content and news management, online portals, registration, monitoring "
        "with SMS or email notifications, QR codes, health care, school and "
        "government services, and e-commerce.",
}

MODEL_NAME = "BAAI/bge-m3"
MAX_TOKENS = 512   # same setting as embed_papers.py


@lru_cache(maxsize=1)
def get_model():
    # If your similarity code already loads the model, import that instead
    # so BGE-M3 (~2GB RAM) is only loaded once.
    model = SentenceTransformer(MODEL_NAME)
    model.max_seq_length = MAX_TOKENS
    return model


@lru_cache(maxsize=1)
def get_label_vectors():
    names = list(CATEGORIES.keys())
    vecs = get_model().encode(
        list(CATEGORIES.values()), normalize_embeddings=True
    )
    return names, np.asarray(vecs)


def paper_text(paper):
    """Title + abstract: the same text the human labelers used."""
    title = " ".join((paper.title or "").split())
    abstract = " ".join((paper.abstract or "").split())
    return f"{title}. {abstract}".strip(". ")


def load_paper_vector(embedding_obj):
    # Fallback only: full-paper vector, used if a paper has no abstract.
    vec = bytes_to_vector(embedding_obj.vector_data)
    return vec / np.linalg.norm(vec)


def text_vector(paper):
    return np.asarray(
        get_model().encode(paper_text(paper), normalize_embeddings=True)
    )


def classify_vector(paper_vec):
    """Returns (best_name, best_score, margin_over_second)."""
    names, label_vecs = get_label_vectors()
    scores = label_vecs @ paper_vec          # cosine, since both are normalized
    order = np.argsort(scores)[::-1]
    best, second = order[0], order[1]
    return names[best], float(scores[best]), float(scores[best] - scores[second])


@transaction.atomic
def assign_category(paper, embedding_obj=None):
    if paper.abstract and paper.abstract.strip():
        vec = text_vector(paper)
    elif embedding_obj is not None:
        vec = load_paper_vector(embedding_obj)
    else:
        raise ValueError(f"No abstract or embedding for paper: {paper.title}")

    name, score, margin = classify_vector(vec)
    category, _ = Category.objects.get_or_create(category_name=name)
    PaperCategory.objects.filter(paper=paper).delete()   # one primary category
    PaperCategory.objects.create(paper=paper, category=category)
    return name, score, margin