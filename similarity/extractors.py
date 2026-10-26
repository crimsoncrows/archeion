"""Turns an uploaded PDF, DOCX, or TXT file into plain text.

After extraction, every type goes through the same clean -> chunk ->
embed -> compare pipeline, so the file type doesn't change how a
paper is scored.
"""
from pathlib import Path

from docx import Document

from .pipeline import extract_pdf_text


def extract_docx_text(file_obj):
    """Body paragraphs only. Tables are skipped, matching table removal in clean_ocr."""
    doc = Document(file_obj)
    return "\n".join(p.text for p in doc.paragraphs)


def extract_txt_text(file_obj):
    """UTF-8 first; fall back to Windows Notepad's ANSI encoding."""
    data = file_obj.read()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("This text file's encoding isn't supported. Save it as UTF-8 and try again.")


EXTRACTORS = {
    ".pdf": extract_pdf_text,
    ".docx": extract_docx_text,
    ".txt": extract_txt_text,
}


def extract_text(uploaded_file):
    ext = Path(uploaded_file.name).suffix.lower()
    return EXTRACTORS[ext](uploaded_file)