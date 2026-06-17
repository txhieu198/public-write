# CLAUDE.md — Cinematic Drama Agent Queue Orchestrator (Claude Code)

> This repo is the dedicated workspace for AI agents that claim, write, and submit
> Cinematic Drama stories to the Source2Draft → Agent Queue API on `hlagency.net`
> (the happykitemedia WebApp). It is NOT the WebApp codebase — it only contains
> guides, helper scripts, and per-runtime entrypoints. There is nothing to build
> or deploy here.

## Start here

1. Read `docs/guides/CINEMATIC_DRAMA_EXTERNAL_AGENT.md` — the full spec: API
   reference, 7-stage writing pipeline, Revision/Social-Kit modes, quality
   standards, and the Red Team Writer/Critic pattern. This file (and the live
   `GET $AQ_BASE/guide` endpoint) is authoritative; everything else here is a
   shortcut into it.
2. Read `docs/guides/AGENT_KICKOFF_PROMPTS.md` §4 ("Claude Code Agent") for the
   full kickoff prompt this file summarizes operationally.
3. Credentials — export before any `curl`, never hardcode a real key in any
   file you write or commit:
   ```bash
   export AQ_BASE="https://hlagency.net/api/n8n/agent-queue"
   export AQ_KEY="sk_ag_..."          # Settings → Agent API Keys, never commit this
   export AQ_AGENT="<MACHINE_ID>-claude-orchestrator-1"
   mkdir -p /tmp/agy_scratch
   ```

## How this orchestrator works

You (the top-level Claude Code session) are the **Orchestrator**. You hold the
only gate that allows `/complete` to be called. You never write story prose
yourself — you spawn two kinds of subagents per story via the **Task tool**:

- **CD_Writer** (`.claude/agents/CD_Writer.md`) — one per story, lives until
  PASS. Writes `task_<id>/{title,fb,comment,website,image_prompt}.txt` +
  `character_sheet.json`. Never self-approves, never submits.
- **CD_Critic** (`.claude/agents/CD_Critic.md`) — a **fresh** instance per
  review round, given a clean context (only `task_<id>/` + the task's genre
  scoring profile). Runs `docs/guides/cinematic_qc.py` as a hard gate, then
  scores the rubric. Read-only.

Claude Code has no `define_subagent` or `schedule` tool (those are
Antigravity-only) — use the Task tool to spawn, and `/loop 1m` (or a bash
`while sleep 60; do ...; done` loop) to poll the queue. Max 5 concurrent
stories (count live CD_Writer Tasks before claiming another).

## Main loop (per tick)

1. Claim — save to file, never print the JSON (large source transcripts get
   truncated by terminals):
   ```bash
   curl -s "$AQ_BASE/next?agent_id=$AQ_AGENT" \
     -H "X-Automation-Key: $AQ_KEY" -H "X-Agent-Id: $AQ_AGENT" \
     -H "Accept: application/json" > /tmp/agy_scratch/task.json
   ```
   `data == null` or already 5 CD_Writers alive → do nothing this tick.
2. Otherwise `POST $AQ_BASE/<id>/start`, create `/tmp/agy_scratch/task_<id>/`,
   spawn a CD_Writer Task with the source material + `data.input.instructions`.
3. On `DRAFT_READY`, spawn a fresh CD_Critic Task. Hard-gate fail → give FIXES
   back to the Writer (max 4 hard rounds, then `POST /<id>/fail`). Score below
   threshold → Writer fixes the 2 lowest-scoring dimensions (max 3 soft
   rounds, then best-of ≥ 70 or `/fail`). `TOTAL ≥ 80` AND `fb_hook ≥ 17` AND
   `comment_pull ≥ 13` → PASS.
4. On PASS: build `payload.json` from the files (title from `title.txt`,
   `analysis.genre`/`analysis.genre_note` from `analysis.json` — REQUIRED, the
   server 422s without it), upload `hero.png` via `POST /<id>/image` if the
   Writer produced one, then `POST $AQ_BASE/<id>/complete`. Helper scripts:
   `scripts/agent-worker/build_payload.py`.
5. `rm -rf /tmp/agy_scratch/task_<id>` and claim a replacement.

Full detail (genre classification, revision mode, social kit mode, error
codes, the verdict format) is in `docs/guides/CINEMATIC_DRAMA_EXTERNAL_AGENT.md`
— read it fully before running the loop unattended.

## Revision batches

If the queue is mostly `revision_note` tasks (bulk mechanical fixes, not fresh
stories), use `docs/guides/AGENT_KICKOFF_PROMPTS.md` §4a instead — it skips the
7-step pipeline and the genre rubric, and drives
`scripts/agent-worker/process_one_revision.sh` / `process_revision_batch.sh`.

## Hard invariants (re-assert every tick, don't re-read the whole guide)

- ≤ 5 CD_Writer Tasks alive. Writer never self-approves; submit only on Critic
  PASS or best-of ≥ 70.
- `analysis.genre` + `analysis.genre_note` MUST be in the `/complete` payload.
- HARD 60-minute timeout from claim — heartbeats do not extend it.
- Never commit a real `AQ_KEY` / `sk_ag_...` anywhere in this repo.
- All large JSON → file + `python3` parse. Never print raw task JSON or full
  story text into the terminal/transcript.
