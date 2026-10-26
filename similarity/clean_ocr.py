"""
scripts/clean_ocr.py

Cleans OCR output before embedding:
- removes markdown tables and image placeholders (mostly shared boilerplate)
- keeps only the body (Introduction/Project Context up to References/Appendices)
- removes lone page numbers and running headers
- rejoins words split across lines with a hyphen
- fixes the systematic OCR error where 'e' was read as 'c' (futurc -> future)

Usage:
    pip install pyspellchecker
    python scripts/clean_ocr.py ocr_raw ocr_clean

Writes cleaned copies to the output folder and a summary to ocr_review.txt.
"""
import itertools
import re
import sys
from collections import Counter
from pathlib import Path

from spellchecker import SpellChecker

spell = SpellChecker()

# Section headers (allow markdown #, bold **, numbering like "1.1", "CHAPTER 1")
PREFIX = r"^[#*\s]*(?:chapter\s+\w+\s*[:.\-]?\s*)?(?:\d+(?:\.\d+)*\.?\s+)?"
SUFFIX = r"[*\s]*$"
START = re.compile(PREFIX + r"(introduction|project context|background of the study)" + SUFFIX, re.I | re.M)
END = re.compile(PREFIX + r"(references|bibliography|literature cited|appendices|appendix\s+a\b.*)" + SUFFIX, re.I | re.M)

PAGE_NUM = re.compile(r"^\s*(page\s*)?(\d{1,3}|[ivx]{1,5})\s*$", re.I)
TABLE_LINE = re.compile(r"^\s*\|")                      # markdown table rows and separators
IMAGE_LINE = re.compile(r"^\s*<!--\s*image\s*-->\s*$", re.I)  # Docling image placeholders
WORD = re.compile(r"\b[A-Za-z]+\b")

# Flag papers where more than 40% of the text was removed
MIN_KEPT_RATIO = 0.60

_cache = {}


def remove_tables_and_images(text):
    """Drop markdown table lines and image placeholders. Captions like 'Table 3. ...' are kept."""
    lines = text.splitlines()
    kept = [l for l in lines if not TABLE_LINE.match(l) and not IMAGE_LINE.match(l)]
    return "\n".join(kept), len(lines) - len(kept)


def remove_noise_lines(text):
    """Drop lone page numbers and running headers (short lines repeated 5+ times)."""
    lines = text.splitlines()
    counts = Counter(l.strip() for l in lines if 3 < len(l.strip()) < 80)
    repeated = {l for l, c in counts.items() if c >= 5}
    kept = [l for l in lines if not PAGE_NUM.match(l) and l.strip() not in repeated]
    return "\n".join(kept)


def join_hyphenated(text):
    """'simi-\\nlarity' -> 'similarity' (only when the next part starts lowercase)."""
    return re.sub(r"(\w)-\n\s*([a-z])", r"\1\2", text)


def best_c_to_e(low):
    """Try swapping each 'c' to 'e'; return the most common real word, or None."""
    if low in _cache:
        return _cache[low]
    positions = [i for i, ch in enumerate(low) if ch == "c"]
    result = None
    if 0 < len(positions) <= 8:
        candidates = []
        for combo in itertools.product("ce", repeat=len(positions)):
            chars = list(low)
            for pos, ch in zip(positions, combo):
                chars[pos] = ch
            cand = "".join(chars)
            if cand != low and spell.known([cand]):
                candidates.append(cand)
        if candidates:
            result = max(candidates, key=spell.word_usage_frequency)
    _cache[low] = result
    return result


def fix_c_for_e(text, fixed):
    """Only touches words that are NOT in the dictionary and contain 'c'."""
    def repl(m):
        tok = m.group(0)
        low = tok.lower()
        # Skip all-caps codes/acronyms, words without 'c', and real words
        if (len(tok) > 1 and tok.isupper()) or "c" not in low or spell.known([low]):
            return tok
        new = best_c_to_e(low)
        if new is None:
            return tok
        if tok[0].isupper():
            new = new.capitalize()
        fixed[f"{tok} -> {new}"] += 1
        return new
    return WORD.sub(repl, text)


def trim_body(text):
    """Keep text from the first real start header up to references/appendices.
    Skips table-of-contents matches by requiring a body longer than 3000 chars."""
    for s in START.finditer(text):
        rest = text[s.start():]
        e = END.search(rest, 1)
        body = rest[:e.start()] if e else rest
        if len(body) > 3000:
            return body, "trimmed"
    return text, "NOT TRIMMED - check manually"


def tidy(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main(src_dir, dst_dir):
    src, dst = Path(src_dir), Path(dst_dir)
    dst.mkdir(parents=True, exist_ok=True)
    report = []
    files = sorted(list(src.glob("*.txt")) + list(src.glob("*.md")))
    for path in files:
        raw = path.read_text(encoding="utf-8", errors="replace")
        fixed = Counter()

        text, table_lines = remove_tables_and_images(raw)
        text = remove_noise_lines(text)
        text = join_hyphenated(text)
        text = fix_c_for_e(text, fixed)
        text, trim_status = trim_body(text)
        text = tidy(text)

        (dst / path.name).write_text(text, encoding="utf-8")

        kept = len(text) / len(raw) if raw else 0
        flag = "  <-- CHECK: large cut" if kept < MIN_KEPT_RATIO else ""
        line = (f"{path.name}: {trim_status} | {len(raw):,} -> {len(text):,} chars "
                f"({kept:.0%} kept) | {table_lines} table/image lines | "
                f"{sum(fixed.values())} c->e fixes{flag}")
        report.append(line)
        if fixed:
            report.append("   sample: " + ", ".join(k for k, _ in fixed.most_common(15)))
        print(line)

    Path("ocr_review.txt").write_text("\n".join(report), encoding="utf-8")
    print("\nDone. Summary saved to ocr_review.txt")


def clean_text(raw):
    """Clean one paper's text with the exact steps and order main() uses.

    Used by the Django upload flow so uploaded papers are cleaned the same
    way as the repository papers that were embedded offline.
    """
    fixed = Counter()
    text, _ = remove_tables_and_images(raw)
    text = remove_noise_lines(text)
    text = join_hyphenated(text)
    text = fix_c_for_e(text, fixed)
    text, _ = trim_body(text)
    return tidy(text)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python scripts/clean_ocr.py <raw_dir> <clean_dir>")
    main(sys.argv[1], sys.argv[2])


