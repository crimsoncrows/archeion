"""
Functional and Feature Matrix (FFM) generation with Claude Haiku 4.5.

One API call per similarity check. The model reads the uploaded study
(first 3,000 words of the cleaned text) and the title + abstract of each
matched repository paper, lists the key features, and marks which papers
have each one. Results are saved to FFMResult / FFM / FFMEntry.

If the API key is missing or the call fails, nothing is saved and the
results page still shows the ranked matches with an "unavailable" note.
"""
import logging
import re

from django.conf import settings
from django.db import transaction

# Adjust this import if your FFM models live in another app.
from .models import FFM, FFMEntry, FFMResult

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"
UPLOAD_WORDS = 3000   # covers Introduction + Objectives, where features are stated
MAX_FEATURES = 12
DOMAINS = [
    "Core Function",
    "Algorithm / Technique",
    "Platform / Technology",
    "Domain / Users",
]

# Research/development methods are not system features; drop them even if the model lists them
NOT_FEATURES = re.compile(
    r"metric|testing|evaluation|methodolog|sdlc|agile|scrum|waterfall|rapid application|\biso\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """You build a Functional and Feature Matrix (FFM) comparing undergraduate IT capstone and thesis studies.

Rules:
- Use ONLY the text given. Do not guess from general knowledge.
- List 6 to 12 key features of the UPLOADED study (id "U"): its main functions or modules, the algorithms or techniques it uses, its platform or technology, and its target domain or users. You may add up to 3 key features of the repository papers that the uploaded study does not have.
- Skip generic features almost every system has (login, registration, CRUD, dashboard, reports) unless one is the study's main purpose. Also skip research methods that are not system features (testing, evaluation, performance metrics, surveys, ISO 25010).
- Name algorithms at the family level so versions match (e.g. "YOLO object detection", not "YOLOv9 object detection"); put the exact version in the evidence.
- Feature names: short, at most 6 words.
- For every feature, give an entry for EVERY paper id. present = true only if that paper's text clearly states it. evidence = a short phrase (at most 15 words) from that paper's text, or "Not mentioned" when absent.
- Repository papers are given as title + abstract only, so judge only from what is written there.
Return the result with the record_ffm tool."""

FFM_TOOL = {
    "name": "record_ffm",
    "description": "Record the Functional and Feature Matrix.",
    "input_schema": {
        "type": "object",
        "properties": {
            "features": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": (
                                "Short feature name, max 6 words. Use the algorithm family without "
                                "version numbers (e.g. 'YOLO object detection', never 'YOLOv9'). "
                                "Never a testing, evaluation, metrics, or development methodology item."
                            ),
                        },                        
                        "domain": {"type": "string", "enum": DOMAINS},
                        "papers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "present": {"type": "boolean"},
                                    "evidence": {"type": "string"},
                                },
                                "required": ["id", "present", "evidence"],
                            },
                        },
                    },
                    "required": ["name", "domain", "papers"],
                },
            }
        },
        "required": ["features"],
    },
}


def _matches(results):
    """Only papers that passed the threshold go into the FFM.
    Assumes similarity_score is the same score you compare to SIMILARITY_THRESHOLD."""
    return [r for r in results if r.similarity_score >= settings.SIMILARITY_THRESHOLD]


def _paper_block(pid, title, text):
    return f'<paper id="{pid}">\nTitle: {title}\n{text}\n</paper>'


def _call_haiku(upload_text, matched_papers):
    import anthropic  # imported here so the site still runs without the package

    excerpt = " ".join(upload_text.split()[:UPLOAD_WORDS])
    blocks = [_paper_block("U", "Uploaded study", excerpt)]
    for i, paper in enumerate(matched_papers, start=1):
        # Adjust field names if your ResearchPaper uses different ones.
        blocks.append(_paper_block(f"P{i}", paper.title, paper.abstract or "No abstract available."))

    client = anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY, timeout=60.0, max_retries=2
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[FFM_TOOL],
        tool_choice={"type": "tool", "name": "record_ffm"},
        messages=[{"role": "user", "content": "\n\n".join(blocks)}],
    )
    if response.stop_reason == "max_tokens":
        raise ValueError("FFM response was cut off (max_tokens).")
    for block in response.content:
        if block.type == "tool_use":
            return block.input.get("features", [])
    raise ValueError("No tool output in FFM response.")


def generate_ffm(submission, upload_text, results):
    """
    Build and save the FFM for one similarity check.

    submission  - the hidden ResearchPaper saved for this check
    upload_text - the cleaned text of the upload (the same text that was embedded)
    results     - this check's SimilarityResult rows, ordered by rank_order

    Returns the FFMResult, or None if there were no matches or the call failed.
    """
    matches = _matches(list(results))
    if not matches or not upload_text:
        return None
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("FFM skipped: ANTHROPIC_API_KEY is not set.")
        return None

    matched_papers = [r.compared_paper for r in matches]
    try:
        features = _call_haiku(upload_text, matched_papers)
    except Exception:
        logger.exception("FFM generation failed.")
        return None

    id_to_paper = {"U": submission}
    id_to_paper.update({f"P{i}": p for i, p in enumerate(matched_papers, start=1)})

    with transaction.atomic():
        ffm_result = FFMResult.objects.create(similarity=matches[0])
        entries, seen = [], set()
        for item in features[:MAX_FEATURES]:
            name = str(item.get("name", "")).strip()[:150]
            domain = item.get("domain") if item.get("domain") in DOMAINS else DOMAINS[0]
            if not name or name.lower() in seen or NOT_FEATURES.search(name):
                continue  # skip blanks, duplicates (unique_together), and research methods
            seen.add(name.lower())

            feature = (FFM.objects.filter(feature_name=name, domain=domain).first()
                       or FFM.objects.create(feature_name=name, domain=domain))
            given = {e.get("id"): e for e in item.get("papers", []) if isinstance(e, dict)}
            for pid, paper in id_to_paper.items():
                entry = given.get(pid, {})
                entries.append(FFMEntry(
                    ffm_result=ffm_result,
                    paper=paper,
                    feature=feature,
                    is_present=bool(entry.get("present", False)),
                    analysis=str(entry.get("evidence", "Not mentioned"))[:500],
                ))
        FFMEntry.objects.bulk_create(entries)
    return ffm_result


def ffm_context(results):
    """
    Turn the saved FFM for a check into rows/columns for the template.

    results - this check's SimilarityResult rows, ordered by rank_order.
    Returns {"no_matches": True}, None (no FFM saved), or the table data.
    """
    matches = _matches(list(results))
    if not matches:
        return {"no_matches": True}

    ffm_result = (FFMResult.objects.filter(similarity=matches[0])
                  .order_by("-generated_at").first())
    if ffm_result is None:
        return None

    cells, features = {}, {}
    for e in ffm_result.entries.select_related("feature"):
        cells[(e.feature_id, e.paper_id)] = e
        features[e.feature_id] = e.feature
    if not features:
        return None

    paper_ids = [matches[0].input_paper_id] + [r.compared_paper_id for r in matches]
    columns = [{"label": "Your study", "title": "Your uploaded study"}] + [
        {"label": f"#{r.rank_order}", "title": r.compared_paper.title} for r in matches
    ]

    def sort_key(f):
        order = DOMAINS.index(f.domain) if f.domain in DOMAINS else len(DOMAINS)
        return (order, f.feature_id)

    rows, shared = [], [0] * len(matches)
    for feature in sorted(features.values(), key=sort_key):
        row_cells = []
        for pid in paper_ids:
            e = cells.get((feature.feature_id, pid))
            row_cells.append({
                "present": bool(e and e.is_present),
                "evidence": e.analysis if e else "Not mentioned",
            })
        if row_cells[0]["present"]:
            for i, cell in enumerate(row_cells[1:]):
                if cell["present"]:
                    shared[i] += 1
        rows.append({"name": feature.feature_name, "domain": feature.domain, "cells": row_cells})

    return {"columns": columns, "rows": rows, "shared": shared}