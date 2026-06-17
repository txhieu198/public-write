#!/usr/bin/env python3
"""
cinematic_qc.py — deterministic quality gate for a Cinematic Drama draft.

Run by the independent Red Team Critic BEFORE it gives a verdict, so the
verdict is grounded in measurement, not vibes. This is the STRICT client-side
twin of the server gate (App\\Services\\EngineStory\\CinematicDramaQualityGate):
the server is the backstop, this catches more (incl. character-name drift) and
hands the Critic a concrete fix list.

Usage:
    python3 cinematic_qc.py <task_dir>

<task_dir> must contain (written by the Writer subagent):
    fb.txt                 facebook post
    comment.txt            comment
    website.txt            website_full (third person, ends with THE END)
    character_sheet.json   Stage-1 sheet: [{"assigned_name": "...", ...}, ...]
    image_prompt.txt       (optional)

Exit code 0 = PASS, 1 = FAIL. Full report on stdout.
"""
import sys
import os
import re
import json
from collections import Counter

# ── Tunables (strict — the Critic enforces one sentence per line) ──
FB_FLOOR, COMMENT_FLOOR, WEBSITE_FLOOR = 700, 300, 3500
CLICHE_NAMES = ["Julian", "Chloe", "Sterling", "Thorne",
                "Marcus", "Vance", "Elara", "Liam"]
ABBREV = ["Mr", "Mrs", "Ms", "Dr", "St", "Jr", "Sr", "vs", "etc", "Inc", "Ltd", "Co"]
NAME_STOPWORDS = {
    "The", "He", "She", "They", "I", "We", "My", "His", "Her", "It", "But",
    "And", "That", "This", "When", "After", "Before", "Part", "End", "A", "An",
    "On", "In", "At", "By", "As", "For", "Then", "Now", "So", "Yet", "Or", "If",
    "Because", "While", "Though", "God", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday", "January", "February", "March",
    "April", "May", "June", "July", "August", "September", "October",
    "November", "December",
}


def read(d, f):
    p = os.path.join(d, f)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def words(s):
    return len(re.findall(r"\b[\w'-]+\b", s))


def strip_abbrev(line):
    return re.sub(r"\b(" + "|".join(ABBREV) + r")\.", r"\1", line, flags=re.I)


def main():
    if len(sys.argv) < 2:
        print("usage: python3 cinematic_qc.py <task_dir>")
        sys.exit(2)
    d = sys.argv[1]

    fb, cm, web = read(d, "fb.txt"), read(d, "comment.txt"), read(d, "website.txt")
    title = read(d, "title.txt").strip()
    try:
        sheet = json.loads(read(d, "character_sheet.json") or "[]")
    except json.JSONDecodeError:
        sheet = []

    fails = []
    out = []

    # ── Title present (missing title.txt = Orchestrator invents a junk title) ──
    title_ok = len(title) >= 10
    out.append(f"title: {'OK' if title_ok else 'FAIL missing/short title.txt'}"
               + (f' (\"{title[:40]}\")' if title else ''))
    if not title_ok:
        fails.append("title.txt missing or too short — write the Stage-3 headline to title.txt")

    # ── Word floors ──
    for name, txt, floor in [("FB", fb, FB_FLOOR), ("Comment", cm, COMMENT_FLOOR),
                             ("Website", web, WEBSITE_FLOOR)]:
        n = words(txt)
        ok = n >= floor
        out.append(f"{name}_words: {n} ({'OK' if ok else 'FAIL <' + str(floor)})")
        if not ok:
            fails.append(f"{name} {n}w < {floor}")

    # ── THE END ──
    end_ok = bool(re.search(r"THE END\s*$", web, re.I))
    out.append(f"THE_END: {'OK' if end_ok else 'FAIL missing'}")
    if not end_ok:
        fails.append("Website missing 'THE END'")

    combined = fb + "\n" + cm + "\n" + web

    # ── Mobile format: one sentence per line ──
    boundary = re.compile(r"[a-z0-9][.!?][\"')\]]?\s+[\"'(\[]?[A-Z]")
    walls, soft = [], 0
    for i, raw in enumerate(combined.splitlines(), 1):
        line = strip_abbrev(raw.strip())
        if not line:
            continue
        b = len(boundary.findall(line))
        if b >= 2:
            walls.append(i)
        elif b == 1:
            soft += 1
    out.append(f"mobile_walls(3+ sentences): {len(walls)} "
               f"({'OK' if not walls else 'FAIL lines ' + str(walls[:15])})")
    out.append(f"mobile_2sentence_lines: {soft} "
               f"({'OK' if soft == 0 else 'WARN split to one per line'})")
    if walls:
        fails.append(f"{len(walls)} lines with 3+ sentences (mobile format)")
    if soft >= 8:
        fails.append(f"{soft} lines with 2 sentences — split one per line")

    # ── Duplicate lines ──
    lines = [l.strip() for l in combined.splitlines() if len(l.strip()) >= 30]
    dups = [l for l, c in Counter(lines).items() if c > 1]
    out.append(f"dup_lines: {len(dups)} ({'OK' if not dups else 'FAIL'})")
    if dups:
        fails.append('Duplicate line: "' + dups[0][:60] + '..."')

    # ── Cliché names ──
    hit = [n for n in CLICHE_NAMES if re.search(r"\b" + n + r"\b", combined)]
    out.append(f"cliche_names: {'OK' if not hit else 'FAIL ' + str(hit)}")
    if hit:
        fails.append(f"Cliché names: {hit}")

    # ── Character-name drift (needs character_sheet.json) ──
    allowed = set()
    for c in sheet:
        val = c.get("assigned_name", "") if isinstance(c, dict) else str(c)
        allowed |= set(re.findall(r"[A-Z][a-z]+", val))
    if allowed:
        # Capitalised first-name-like token used MID-sentence (after a lowercase
        # letter/comma) that is not an allowed character name or a stopword.
        cand = Counter(re.findall(r"(?<=[a-z,;:] )([A-Z][a-z]{2,})", web))
        drift = [w for w in cand if w not in allowed and w not in NAME_STOPWORDS]
        # NOTE: place/company names (Boston, Henderson, Ritz) may appear here.
        # The Critic must judge each candidate: a PERSON name not in the sheet
        # = real drift (FAIL); a place/org = ignore.
        out.append(f"name_drift_candidates: "
                   f"{'none' if not drift else str(drift[:12])} "
                   f"(Critic: FAIL only those that are PERSON names)")
        if drift:
            fails.append(f"Review name-drift candidates (person names?): {drift[:12]}")
    else:
        out.append("name_drift_candidates: skipped (no character_sheet.json)")

    print("\n".join(out))
    print("\nGATE:", "PASS" if not fails else "FAIL — " + " | ".join(fails))
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
