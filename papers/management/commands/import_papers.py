"""
Imports repository papers from the sheet CSV + embeddings.json (+ optional PDFs).

CSV columns (required): filename, title, authors, year, program, abstract
CSV columns (optional): track, category (semicolon-separated), type (thesis/capstone)

Usage:
    python manage.py import_papers --csv PATH --embeddings PATH [--pdf-dir PATH] [--dry-run] [--limit N]

Re-running is safe: papers are matched by title + year and updated, not duplicated.
"""
import csv
import json
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from papers.models import Category, PaperCategory, ResearchPaper
from similarity.models import Embedding
from similarity.vectors import DIM, vector_to_bytes

REQUIRED = ["filename", "title", "authors", "year", "program", "abstract"]
VALID_TYPES = {"thesis", "capstone"}


def stem(name):
    return Path(name.strip()).stem   # "NA_2022_01.md" -> "NA_2022_01"


class Command(BaseCommand):
    help = "Import repository papers, embeddings, categories and PDFs."

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True)
        parser.add_argument("--embeddings", required=True)
        parser.add_argument("--pdf-dir", default=None)
        parser.add_argument("--type", default="capstone", choices=sorted(VALID_TYPES))
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **opts):
        csv_path, emb_path = Path(opts["csv"]), Path(opts["embeddings"])
        pdf_dir = Path(opts["pdf_dir"]) if opts["pdf_dir"] else None
        for p in [csv_path, emb_path] + ([pdf_dir] if pdf_dir else []):
            if not p.exists():
                raise CommandError(f"Not found: {p}")

        with open(emb_path, encoding="utf-8") as f:
            embeddings = {stem(k): v for k, v in json.load(f).items()}

        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
            if missing:
                raise CommandError(f"CSV is missing columns: {missing}")
            rows = list(reader)[:opts["limit"]] if opts["limit"] else list(reader)

        created = updated = skipped = 0
        for row in rows:
            key = stem(row["filename"])
            problem = self.check_row(row, key, embeddings, opts["type"])
            if problem:
                self.stderr.write(f"SKIP {key}: {problem}")
                skipped += 1
                continue
            if opts["dry_run"]:
                self.stdout.write(f"OK   {key}: {row['title'][:60]}")
                continue
            pdf = pdf_dir / f"{key}.pdf" if pdf_dir else None
            with transaction.atomic():
                was_created = self.import_row(row, key, embeddings[key], pdf, opts["type"])
            created += was_created
            updated += not was_created
            self.stdout.write(f"{'NEW' if was_created else 'UPD'}  {key}")

        mode = "DRY RUN - nothing saved. " if opts["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{mode}Created {created}, updated {updated}, skipped {skipped}."))

    def check_row(self, row, key, embeddings, default_type):
        for col in REQUIRED:
            if not (row.get(col) or "").strip():
                return f"empty '{col}'"
        if not row["year"].strip().isdigit():
            return "year is not a number"
        paper_type = (row.get("type") or default_type).strip().lower()
        if paper_type not in VALID_TYPES:
            return f"type '{paper_type}' must be thesis or capstone"
        if key not in embeddings:
            return "no vector in embeddings.json (run embed_papers.py)"
        if len(embeddings[key]["vector"]) != DIM:
            return f"vector is not {DIM}-dim"
        return None

    def import_row(self, row, key, emb, pdf, default_type):
        program = row["program"].strip()
        track = (row.get("track") or "").strip()
        if track:
            program = f"{program}-{track}"          # e.g. IT-NA

        paper, created = ResearchPaper.objects.update_or_create(
            title=row["title"].strip(),
            year=int(row["year"]),
            defaults={
                "abstract": row["abstract"].strip(),
                "authors": row["authors"].strip(),
                "program": program,
                "type": (row.get("type") or default_type).strip().lower(),
            },
        )

        if pdf and pdf.exists() and not paper.file_path:
            with open(pdf, "rb") as fh:
                if fh.read(5) != b"%PDF-":
                    raise CommandError(f"{pdf} is not a valid PDF")
                fh.seek(0)
                paper.file_path.save(pdf.name, File(fh), save=True)
        elif pdf and not pdf.exists():
            self.stderr.write(f"     {key}: no PDF at {pdf} (saved without file)")

        Embedding.objects.update_or_create(
            paper=paper, defaults={"vector_data": vector_to_bytes(emb["vector"])})

        for name in (row.get("category") or "").split(";"):
            name = name.strip()
            if name:
                category, _ = Category.objects.get_or_create(category_name=name)
                PaperCategory.objects.get_or_create(paper=paper, category=category)

        return created