#!/usr/bin/env python3
"""
Bootstrap a revision task workspace from agent-queue task.json.

Reads /tmp/agy_scratch/task.json (or path arg), extracts current_draft layers
into task_<id>/ files for the Writer/Critic workflow.

Usage:
    python3 bootstrap_revision.py [task.json] [output_dir]

Default: task.json = /tmp/agy_scratch/task.json
         output_dir = /tmp/agy_scratch/task_<id>/

Note: if current_draft is missing and only s2d_job_id is present, this script
shells out to scripts/agent-worker/recover_draft.php, which is NOT included in
this repo (it depends on the happykitemedia Laravel app/DB). That fallback path
only matters when current_draft is absent from the /next response; the normal
revision flow (current_draft present) works standalone.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def extract_layers(draft: dict) -> dict[str, str]:
    """Mirror CinematicDramaDraftAuditor::extractLayers()."""
    pkg = draft.get("cinematic_drama_package") or {}
    fb = str(pkg.get("facebook_post") or "").strip()
    cm = str(pkg.get("comment") or "").strip()
    web = str(pkg.get("website_full") or "").strip()

    chapters = draft.get("chapters") or []
    if chapters and isinstance(chapters, list):
        if not fb and len(chapters) > 0:
            ch0 = chapters[0] if isinstance(chapters[0], dict) else {}
            fb = str(ch0.get("narrative") or ch0.get("content") or "").strip()
        if not cm and len(chapters) > 1:
            ch1 = chapters[1] if isinstance(chapters[1], dict) else {}
            cm = str(ch1.get("narrative") or ch1.get("content") or "").strip()
        if not web and len(chapters) > 2:
            ch2 = chapters[2] if isinstance(chapters[2], dict) else {}
            web = str(ch2.get("narrative") or ch2.get("content") or "").strip()

    image_prompt = draft.get("image_prompt") or ""
    if isinstance(image_prompt, list):
        image_prompt = image_prompt[0] if image_prompt else ""
    image_prompt = str(image_prompt).strip()

    return {
        "title": str(draft.get("title") or "").strip(),
        "facebook_post": fb,
        "comment": cm,
        "website_full": web,
        "image_prompt": image_prompt,
    }


def main() -> int:
    task_json_path = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/agy_scratch/task.json")
    if not task_json_path.is_file():
        print(f"ERROR: task file not found: {task_json_path}", file=sys.stderr)
        return 1

    with task_json_path.open(encoding="utf-8") as f:
        payload = json.load(f)

    data = payload.get("data")
    if not data:
        print("ERROR: no task in response (data is null)", file=sys.stderr)
        return 1

    task_id = data.get("task_id")
    if not task_id:
        print("ERROR: missing task_id", file=sys.stderr)
        return 1

    inp = data.get("input") or {}
    options = inp.get("options") or {}
    revision_note = str(options.get("revision_note") or "").strip()
    if not revision_note:
        print("ERROR: not a revision task (no revision_note)", file=sys.stderr)
        return 1

    current_draft = options.get("current_draft") or {}
    if not current_draft or not current_draft.get("chapters"):
        s2d_job_id = options.get("s2d_job_id")
        if not s2d_job_id:
            print("ERROR: revision task missing current_draft and s2d_job_id", file=sys.stderr)
            return 1
        repo = Path(__file__).resolve().parents[2]
        recover_script = repo / "scripts" / "agent-worker" / "recover_draft.php"
        if not recover_script.is_file():
            print(
                "ERROR: current_draft missing and recover_draft.php is not available in this "
                "repo (it requires the happykitemedia Laravel app). Re-claim a task whose "
                "current_draft is populated, or run this against the happykitemedia checkout.",
                file=sys.stderr,
            )
            return 1
        proc = subprocess.run(
            ["php", str(recover_script), str(s2d_job_id)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            print(proc.stderr or proc.stdout, file=sys.stderr)
            return 1
        current_draft = json.loads(proc.stdout)

    if len(sys.argv) > 2:
        out_dir = Path(sys.argv[2])
    else:
        out_dir = Path(f"/tmp/agy_scratch/task_{task_id}")

    out_dir.mkdir(parents=True, exist_ok=True)

    layers = extract_layers(current_draft)
    character_sheet = current_draft.get("character_sheet")
    if not character_sheet or not isinstance(character_sheet, list):
        character_sheet = []

    files = {
        "title.txt": layers["title"],
        "fb.txt": layers["facebook_post"],
        "comment.txt": layers["comment"],
        "website.txt": layers["website_full"],
        "image_prompt.txt": layers["image_prompt"],
        "revision_note.txt": revision_note,
    }

    for name, content in files.items():
        (out_dir / name).write_text(content, encoding="utf-8")

    (out_dir / "character_sheet.json").write_text(
        json.dumps(character_sheet, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Baseline word counts for optional drift check
    baseline = {
        "facebook": len(layers["facebook_post"].split()),
        "comment": len(layers["comment"].split()),
        "website": len(layers["website_full"].split()),
    }
    (out_dir / "baseline_word_counts.json").write_text(
        json.dumps(baseline, indent=2),
        encoding="utf-8",
    )

    meta = {
        "task_id": task_id,
        "s2d_job_id": options.get("s2d_job_id"),
        "output_dir": str(out_dir),
    }
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
