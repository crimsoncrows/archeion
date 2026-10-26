"""
Embeds and classifies repository papers that have no embedding yet
(e.g. papers the admin added through the dashboard).

Uses the same functions as the live similarity check:
extract_pdf_text -> clean_text -> 300/50 chunks -> BGE-M3 -> average -> normalize.

Usage:
    python manage.py embed_pending            # embed + classify all pending papers
    python manage.py embed_pending --dry-run  # only list pending papers

Restart the Django server afterwards: the similarity corpus is cached (load_corpus).
"""
import io

from django.core.management.base import BaseCommand
from django.db import transaction

from papers.models import ResearchPaper
from similarity.models import Embedding
from similarity.pipeline import embed_document, extract_pdf_text
from similarity.vectors import vector_to_bytes
from papers.classification import assign_category  # <- change if classification.py lives elsewhere

CONFIDENCE_MARGIN = 0.02  # same flag rule as the Trends classification


def read_pdf_text(paper):
    """Read the stored PDF (Cloudinary or local) and extract text like a live upload."""
    with paper.file_path.open("rb") as fh:
        data = fh.read()
    if not data.startswith(b"%PDF-"):
        raise ValueError("stored file is not a valid PDF")
    return extract_pdf_text(io.BytesIO(data))


class Command(BaseCommand):
    help = "Embed and classify papers that have no embedding yet."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        # Default manager already hides 'submission' rows, so only real repository papers.
        embedded_ids = Embedding.objects.values_list("paper_id", flat=True)
        pending = ResearchPaper.objects.exclude(pk__in=embedded_ids).order_by("pk")

        if not pending.exists():
            self.stdout.write(self.style.SUCCESS("No pending papers."))
            return

        if opts["dry_run"]:
            for paper in pending:
                self.stdout.write(f"PENDING {paper.pk}: {paper.title[:70]}")
            self.stdout.write(f"DRY RUN - {pending.count()} pending, nothing saved.")
            return

        done = failed = 0
        for paper in pending:
            label = f"{paper.pk}: {paper.title[:60]}"
            if not paper.file_path:
                self.stderr.write(f"SKIP {label} - no PDF attached")
                failed += 1
                continue
            try:
                vector = embed_document(read_pdf_text(paper))
                with transaction.atomic():
                    emb, _ = Embedding.objects.update_or_create(
                        paper=paper,
                        defaults={"vector_data": vector_to_bytes(vector.tolist())},
                    )
                    name, score, margin = assign_category(paper, emb)
            except Exception as exc:  # one bad paper shouldn't stop the rest
                self.stderr.write(f"FAIL {label} - {exc}")
                failed += 1
                continue

            flag = "  <- low confidence, confirm category in dashboard" if margin < CONFIDENCE_MARGIN else ""
            self.stdout.write(f"OK   {label} -> {name} ({score:.3f}){flag}")
            done += 1

        self.stdout.write(self.style.SUCCESS(
            f"Embedded {done}, failed/skipped {failed}. Restart the server to refresh the similarity corpus."))