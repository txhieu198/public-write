#!/usr/bin/env python3
"""
Build /complete payload JSON from a task directory.

Usage:
    python3 build_payload.py <task_dir> [output.json]

Reads: title.txt, fb.txt, comment.txt, website.txt, image_prompt.txt
       analysis.json (genre + genre_note from Stage 1 — REQUIRED for 7-step tasks)
Writes: payload.json in task_dir (or output path).

The cinematic genre is classified by the agent in Stage 1 ANALYZE and MUST be
echoed back in `analysis.genre` — the server rejects (HTTP 422) a full 7-step
submission without a valid genre slug. This script lifts it from analysis.json
(falling back to genre.txt / character_sheet.json) into the payload's `analysis`
block.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

VALID_GENRES = {
    "betrayal_revenge",
    "heartwarming",
    "justice_exposure",
    "redemption",
    "mystery_reveal",
    "neutral",
}


def word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


def read_analysis(task_dir: Path) -> dict:
    """Resolve genre + genre_note from the Writer's Stage-1 artifacts.

    Order: analysis.json → genre.txt/genre_note.txt → character_sheet.json.
    Returns {} when nothing is found so the caller can warn (the server will
    then 422 on a 7-step task — that is the intended hard gate).
    """
    genre = ""
    note = ""

    aj = task_dir / "analysis.json"
    if aj.is_file():
        try:
            data = json.loads(aj.read_text(encoding="utf-8"))
            genre = str(data.get("genre", "") or "").strip()
            note = str(data.get("genre_note", "") or "").strip()
        except (ValueError, OSError) as exc:
            print(f"WARNING: could not parse analysis.json: {exc}", file=sys.stderr)

    if not genre and (task_dir / "genre.txt").is_file():
        genre = (task_dir / "genre.txt").read_text(encoding="utf-8").strip()
    if not note and (task_dir / "genre_note.txt").is_file():
        note = (task_dir / "genre_note.txt").read_text(encoding="utf-8").strip()

    if not genre and (task_dir / "character_sheet.json").is_file():
        try:
            cs = json.loads((task_dir / "character_sheet.json").read_text(encoding="utf-8"))
            if isinstance(cs, dict):
                genre = str(cs.get("genre", "") or "").strip()
                note = note or str(cs.get("genre_note", "") or "").strip()
        except (ValueError, OSError):
            pass

    if not genre:
        return {}

    if genre not in VALID_GENRES:
        print(
            f"WARNING: genre '{genre}' is not a known slug ({', '.join(sorted(VALID_GENRES))}); "
            "server will 422. Submitting as-is.",
            file=sys.stderr,
        )

    out = {"genre": genre}
    if note:
        out["genre_note"] = note[:120]
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: build_payload.py <task_dir> [output.json]", file=sys.stderr)
        return 1

    task_dir = Path(sys.argv[1])
    if not task_dir.is_dir():
        print(f"ERROR: not a directory: {task_dir}", file=sys.stderr)
        return 1

    required = ["title.txt", "fb.txt", "comment.txt", "website.txt", "image_prompt.txt"]
    missing = [f for f in required if not (task_dir / f).is_file()]
    if missing:
        print(f"ERROR: missing files: {', '.join(missing)}", file=sys.stderr)
        return 1

    title = (task_dir / "title.txt").read_text(encoding="utf-8").strip()
    fb = (task_dir / "fb.txt").read_text(encoding="utf-8").strip()
    comment = (task_dir / "comment.txt").read_text(encoding="utf-8").strip()
    website = (task_dir / "website.txt").read_text(encoding="utf-8").strip()
    image_prompt = (task_dir / "image_prompt.txt").read_text(encoding="utf-8").strip()

    if not title:
        print("ERROR: title.txt is empty", file=sys.stderr)
        return 1

    fb_w = word_count(fb)
    cm_w = word_count(comment)
    web_w = word_count(website)

    payload = {
        "title": title,
        "facebook_post": fb,
        "comment": comment,
        "website_full": website,
        "image_prompt": image_prompt,
        "word_counts": {
            "facebook": fb_w,
            "comment": cm_w,
            "website": web_w,
            "total": fb_w + cm_w + web_w,
        },
    }

    # Agent-classified genre (Stage 1). REQUIRED for full 7-step tasks — the
    # server 422s "analysis.genre" without it. Placed first for readability.
    analysis = read_analysis(task_dir)
    if analysis:
        payload = {"analysis": analysis, **payload}
    else:
        print(
            "WARNING: no genre found (analysis.json / genre.txt / character_sheet.json). "
            "A full 7-step task will be rejected with 422 analysis.genre.",
            file=sys.stderr,
        )

    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else task_dir / "payload.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
