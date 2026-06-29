#!/usr/bin/env python3
"""
Build /complete payload JSON for a Social Kit task (repurpose_scope=social_kit).

Usage:
    python3 build_social_kit_payload.py <task_dir> [output.json]

Reads: title.txt, fb.txt, comment.txt, image_prompt.txt, angle_summary.txt (optional),
       website_locked.txt (the immutable Part 3 — embedded byte-identical, never stripped)
Writes: payload.json in task_dir (or output path).

website_full must be byte-identical to source_material[0].content — the server verifies
its sha1, so website_locked.txt is read raw and never touched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: build_social_kit_payload.py <task_dir> [output.json]", file=sys.stderr)
        return 1

    task_dir = Path(sys.argv[1])
    if not task_dir.is_dir():
        print(f"ERROR: not a directory: {task_dir}", file=sys.stderr)
        return 1

    required = ["title.txt", "fb.txt", "comment.txt", "image_prompt.txt", "website_locked.txt"]
    missing = [f for f in required if not (task_dir / f).is_file()]
    if missing:
        print(f"ERROR: missing files: {', '.join(missing)}", file=sys.stderr)
        return 1

    title = (task_dir / "title.txt").read_text(encoding="utf-8").strip()
    fb = (task_dir / "fb.txt").read_text(encoding="utf-8").strip()
    comment = (task_dir / "comment.txt").read_text(encoding="utf-8").strip()
    image_prompt = (task_dir / "image_prompt.txt").read_text(encoding="utf-8").strip()
    website_full = (task_dir / "website_locked.txt").read_text(encoding="utf-8")

    if not title:
        print("ERROR: title.txt is empty", file=sys.stderr)
        return 1

    payload = {
        "title": title,
        "facebook_post": fb,
        "comment": comment,
        "image_prompt": image_prompt,
        "website_full": website_full,
        "word_counts": {
            "facebook": word_count(fb),
            "comment": word_count(comment),
        },
    }

    angle_path = task_dir / "angle_summary.txt"
    if angle_path.is_file():
        angle = angle_path.read_text(encoding="utf-8").strip()
        if angle:
            payload["angle_summary"] = angle

    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else task_dir / "payload.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
