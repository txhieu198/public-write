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
    character_sheet.json   Stage-1 sheet: [{"assigned_name": "...", "source_name": "...",
                                "aliases_to_avoid": [...]}, ...]
    image_prompt.txt       (optional)
    source.txt             (optional) raw transcript — enables the deterministic
                            real-name leak check below.

Exit code 0 = PASS, 1 = FAIL. Full report on stdout.

Character-name drift is now a deterministic hard check: each character_sheet
entry must carry the real `source_name` pulled from the transcript plus any
`aliases_to_avoid` (nicknames/diminutives of that real name, e.g. Abigail ->
Abby). The script expands well-known diminutives automatically and FAILS hard
on any exact match found in the output — no Critic guessing required.
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
TITLE_WORDS = {
    "mr", "mrs", "ms", "dr", "captain", "general", "major", "colonel",
    "sergeant", "lieutenant", "private", "admiral", "aunt", "uncle", "mom",
    "dad", "father", "mother", "professor", "judge", "officer", "sir",
}
NAME_STOPWORDS = {
    "The", "He", "She", "They", "I", "We", "My", "His", "Her", "It", "But",
    "And", "That", "This", "When", "After", "Before", "Part", "End", "A", "An",
    "On", "In", "At", "By", "As", "For", "Then", "Now", "So", "Yet", "Or", "If",
    "Because", "While", "Though", "God", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday", "January", "February", "March",
    "April", "May", "June", "July", "August", "September", "October",
    "November", "December",
}

# Common English first-name diminutives, used to auto-expand each
# character_sheet "source_name" into the nicknames a Writer might forget to
# rename (Abigail -> Abby is exactly the leak this table exists to catch).
# Diminutives that collide with ordinary English words (e.g. "Will" the name
# vs. "will" the verb) — too noisy as leak signals, so they're excluded.
DIMINUTIVE_STOPWORDS = {"will", "hope", "grace", "faith", "pat", "val", "sue", "jo", "may", "june"}

DIMINUTIVES = {
    "abigail": ["abby", "abbie", "gail"], "alexander": ["alex", "xander", "lex"],
    "alexandra": ["alex", "lexie", "sandra"], "andrew": ["andy", "drew"],
    "anthony": ["tony"], "benjamin": ["ben", "benny"], "catherine": ["cathy", "kate", "katie"],
    "charles": ["charlie", "chuck"], "christopher": ["chris", "topher"],
    "daniel": ["dan", "danny"], "david": ["dave", "davey"], "deborah": ["deb", "debbie"],
    "edward": ["ed", "eddie"], "elizabeth": ["liz", "beth", "eliza", "lizzie"],
    "frederick": ["fred", "freddie"], "gregory": ["greg"], "henry": ["hank", "harry"],
    "jacob": ["jake"], "james": ["jim", "jimmy"], "jennifer": ["jen", "jenny"],
    "jonathan": ["jon", "johnny"], "joseph": ["joe", "joey"], "katherine": ["kathy", "kate", "katie"],
    "kenneth": ["ken", "kenny"], "margaret": ["maggie", "meg", "peggy"],
    "matthew": ["matt"], "michael": ["mike", "mick", "mickey"], "nathaniel": ["nathan", "nate"],
    "nicholas": ["nick"], "patricia": ["pat", "patty", "trish"], "patrick": ["pat", "paddy"],
    "rebecca": ["becky"], "richard": ["rick", "ricky", "dick"], "robert": ["rob", "bob", "bobby"],
    "ronald": ["ron", "ronnie"], "samuel": ["sam", "sammy"], "stephanie": ["steph"],
    "susan": ["sue", "susie"], "theodore": ["ted", "teddy"], "thomas": ["tom", "tommy"],
    "timothy": ["tim", "timmy"], "victoria": ["vicky", "tori"], "william": ["will", "bill", "billy"],
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

    # ── Real-name leak (deterministic, needs character_sheet.json source_name) ──
    leaks = []
    declared_real_names = [c.get("source_name") or c.get("real_name", "")
                            for c in sheet if isinstance(c, dict)]
    # Any token used in ANY assigned_name is fair game (two characters can
    # legitimately share a first name in the rewrite) — exclude those globally.
    all_assigned_tokens = {
        tok.lower()
        for c in sheet if isinstance(c, dict)
        for tok in re.findall(r"[A-Za-z]+", c.get("assigned_name", ""))
    }
    if any(declared_real_names):
        for c in sheet:
            if not isinstance(c, dict):
                continue
            real = (c.get("source_name") or c.get("real_name") or "").strip()
            if not real:
                continue
            variants = {real}
            variants |= {a.strip() for a in c.get("aliases_to_avoid", []) if a.strip()}
            for word in re.findall(r"[A-Za-z]+", real):
                wl = word.lower()
                if wl in TITLE_WORDS:
                    continue
                variants.add(word)
                variants |= set(DIMINUTIVES.get(wl, [])) - DIMINUTIVE_STOPWORDS
            for v in variants:
                if not v or v.lower() in all_assigned_tokens:
                    continue
                if re.search(r"\b" + re.escape(v) + r"\b", combined, re.I):
                    leaks.append(v)
        out.append(f"real_name_leak: {'none' if not leaks else 'FAIL ' + str(leaks)}")
        if leaks:
            fails.append(f"Real-name leak from source (incl. nicknames): {leaks}")
    else:
        out.append("real_name_leak: skipped (character_sheet.json missing source_name "
                   "per entry — Stage 1 must declare it)")

    # ── Unrecognised capitalised tokens (advisory only, not a gate) ──
    allowed = set()
    for c in sheet:
        val = c.get("assigned_name", "") if isinstance(c, dict) else str(c)
        allowed |= set(re.findall(r"[A-Z][a-z]+", val))
    if allowed:
        cand = Counter(re.findall(r"(?<=[a-z,;:] )([A-Z][a-z]{2,})", web))
        unknown = [w for w in cand if w not in allowed and w not in NAME_STOPWORDS]
        out.append(f"unrecognised_capitalised_tokens (advisory, likely places/orgs): "
                   f"{'none' if not unknown else str(unknown[:12])}")

    print("\n".join(out))
    print("\nGATE:", "PASS" if not fails else "FAIL — " + " | ".join(fails))
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
