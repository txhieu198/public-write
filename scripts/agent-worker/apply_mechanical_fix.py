#!/usr/bin/env python3
"""
Apply mechanical revision fixes from revision_note.txt to task dir files.

Usage:
    python3 apply_mechanical_fix.py <task_dir>

Reads revision_note.txt and modifies fb.txt, comment.txt, website.txt in place.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CLICHE_NAMES = [
    "Julian", "Chloe", "Sterling", "Thorne",
    "Marcus", "Vance", "Elara", "Liam",
]
REPLACEMENTS = {
    "Julian": "Daniel", "Chloe": "Megan", "Sterling": "Robert",
    "Thorne": "Craig", "Marcus": "Brian", "Vance": "Keith",
    "Elara": "Laura", "Liam": "Ryan",
}
BOILERPLATE_PREFIXES = [
    "I turned back to the television screen",
    "I adjusted my grip on my sleeping son",
    "The silence in the room was absolutely suffocating",
]
SENT_BOUNDARY = re.compile(r'[a-z0-9][.!?][\"\'\)\]]?\s+[\"\'(\[]?[A-Z]')
ABBREV = re.compile(r"\b(Mr|Mrs|Ms|Dr|St|Jr|Sr|vs|etc|Inc|Ltd|Co)\.", re.I)


def strip_abbrev(line: str) -> str:
    return ABBREV.sub(r"\1", line)


def split_sentences(line: str) -> list[str]:
    """Split a line into sentences (one per mobile-format line)."""
    parts: list[str] = []
    start = 0
    while start < len(line):
        segment = line[start:]
        m = SENT_BOUNDARY.search(segment)
        if not m:
            tail = segment.strip()
            if tail:
                parts.append(tail)
            break
        end = m.start() + 1
        while end < len(segment) and segment[end] in '.!?':
            end += 1
        chunk = segment[:end].strip()
        if chunk:
            parts.append(chunk)
        start += m.end() - 1
        while start < len(line) and line[start] in ' "\'([]':
            start += 1
    return parts


def one_sentence_per_line(text: str) -> str:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue
        line = strip_abbrev(line)
        for part in split_sentences(line):
            out.append(part)
    return "\n".join(out)


def dedupe_lines(text: str, min_len: int = 30) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for line in text.splitlines():
        key = line.strip()
        if len(key) >= min_len:
            if key in seen:
                continue
            seen.add(key)
        out.append(line)
    return "\n".join(out)


def global_dedupe_task(task_dir: Path, min_len: int = 30) -> None:
    """Drop cross-layer duplicate lines; prefer keeping Website copy."""
    fnames = ("fb.txt", "comment.txt", "website.txt")
    file_lines: list[list[str]] = []
    for fname in fnames:
        path = task_dir / fname
        if path.is_file():
            file_lines.append(path.read_text(encoding="utf-8").splitlines())
        else:
            file_lines.append([])

    from collections import defaultdict

    locs: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for fi, lines in enumerate(file_lines):
        for li, line in enumerate(lines):
            key = line.strip()
            if len(key) >= min_len:
                locs[key].append((fi, li))

    to_remove: set[tuple[int, int]] = set()
    for _key, positions in locs.items():
        if len(positions) <= 1:
            continue
        website_pos = [p for p in positions if p[0] == 2]
        keep = website_pos[0] if website_pos else positions[0]
        for p in positions:
            if p != keep:
                to_remove.add(p)

    for fi, fname in enumerate(fnames):
        path = task_dir / fname
        if not path.is_file():
            continue
        out = [line for li, line in enumerate(file_lines[fi]) if (fi, li) not in to_remove]
        path.write_text("\n".join(out), encoding="utf-8")


def remove_boilerplate_duplicates(text: str) -> str:
    counts: dict[str, int] = {p: 0 for p in BOILERPLATE_PREFIXES}
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        drop = False
        for prefix in BOILERPLATE_PREFIXES:
            if stripped.startswith(prefix):
                counts[prefix] += 1
                if counts[prefix] > 1:
                    drop = True
                break
        if not drop:
            out.append(line)
    return "\n".join(out)


def replace_cliche_names(text: str, note: str) -> str:
    targets = [n for n in CLICHE_NAMES if re.search(rf"\b{n}\b", note) or re.search(rf"\b{n}\b", text)]
    if not targets:
        targets = [n for n in CLICHE_NAMES if re.search(rf"\b{n}\b", text)]
    for name in targets:
        repl = REPLACEMENTS.get(name, "Alex")
        text = re.sub(rf"\b{name}\b", repl, text)
    return text


def ensure_the_end(text: str) -> str:
    if re.search(r"THE END\s*$", text, re.I):
        return text
    text = text.rstrip()
    return text + "\n\nTHE END"


def apply_fix(text: str, note: str) -> str:
    lower = note.lower()
    if "mobile format" in lower or "one sentence" in lower:
        text = one_sentence_per_line(text)
    if "duplicate" in lower and "boilerplate" not in lower:
        text = dedupe_lines(text)
    if "boilerplate" in lower:
        text = remove_boilerplate_duplicates(text)
    if "cliché" in lower or "cliche" in lower or "forbidden" in lower:
        text = replace_cliche_names(text, note)
    if "the end" in lower:
        text = ensure_the_end(text)
    return text


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: apply_mechanical_fix.py <task_dir> [--aggressive]", file=sys.stderr)
        return 1

    task_dir = Path(sys.argv[1])
    aggressive = "--aggressive" in sys.argv[2:]
    note_path = task_dir / "revision_note.txt"
    if not note_path.is_file():
        print("ERROR: revision_note.txt missing", file=sys.stderr)
        return 1

    note = note_path.read_text(encoding="utf-8").strip()
    for fname in ("fb.txt", "comment.txt", "website.txt"):
        path = task_dir / fname
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        path.write_text(apply_fix(content, note), encoding="utf-8")

    if aggressive:
        global_dedupe_task(task_dir)
        for fname in ("fb.txt", "comment.txt", "website.txt"):
            path = task_dir / fname
            if not path.is_file():
                continue
            content = remove_boilerplate_duplicates(path.read_text(encoding="utf-8"))
            path.write_text(content, encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
