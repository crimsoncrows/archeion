import csv
import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from papers.models import ResearchPaper
from similarity.models import Embedding
from similarity.vectors import vector_to_bytes

EXPECTED_MODEL = "BAAI/bge-m3"


def normalize_title(title):
    """Ignore case and extra spaces when matching titles."""
    return re.sub(r"\s+", " ", title or "").strip().casefold()


class Command(BaseCommand):
    help = "Load paper vectors from embeddings.json into the Embedding table."

    def add_arguments(self, parser):
        parser.add_argument("json_path", help="embeddings.json from archeion-ocr")
        parser.add_argument("csv_path", help="Sheet export with filename and title columns")

    def handle(self, *args, **opts):
        json_path = Path(opts["json_path"])
        csv_path = Path(opts["csv_path"])
        for path in (json_path, csv_path):
            if not path.exists():
                raise CommandError(f"File not found: {path}")

        data = json.loads(json_path.read_text(encoding="utf-8"))

        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            missing = {"filename", "title"} - set(reader.fieldnames or [])
            if missing:
                raise CommandError(f"CSV is missing column(s): {', '.join(sorted(missing))}")
            filename_to_title = {
                row["filename"].strip(): row["title"]
                for row in reader
                if row["filename"].strip()
            }

        papers_by_title = {
            normalize_title(p.title): p for p in ResearchPaper.objects.all()
        }

        saved, problems = 0, []
        with transaction.atomic():
            for key, entry in data.items():
                stem = Path(key).stem                     # "NA_2022_01.md" -> "NA_2022_01"
                if entry.get("model") != EXPECTED_MODEL:
                    problems.append(f"{key}: made with {entry.get('model')}, not {EXPECTED_MODEL}")
                    continue
                title = filename_to_title.get(stem)
                if title is None:
                    problems.append(f"{key}: no row with filename '{stem}' in the CSV")
                    continue
                paper = papers_by_title.get(normalize_title(title))
                if paper is None:
                    problems.append(f"{key}: no paper in the database titled '{title}'")
                    continue
                Embedding.objects.update_or_create(
                    paper=paper,
                    defaults={"vector_data": vector_to_bytes(entry["vector"])},
                )
                saved += 1

        for msg in problems:
            self.stdout.write(self.style.WARNING("SKIPPED " + msg))
        self.stdout.write(self.style.SUCCESS(
            f"Saved {saved} embedding(s); skipped {len(problems)}."
        ))