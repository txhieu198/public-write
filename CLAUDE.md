# CLAUDE.md — Cinematic Drama Agent Queue Orchestrator (Claude Code)

> This repo is a thin workspace for AI agents that claim, write, and submit
> Cinematic Drama stories to the Source2Draft → Agent Queue API on
> `hlagency.net` (the happykitemedia WebApp). It is NOT the WebApp codebase,
> and it does NOT mirror the guide — there is nothing to build or deploy
> here, and nothing here goes stale, because the rules live on the server.

## Start here — ALWAYS fetch the live guide first

This repo intentionally does not bundle a copy of the spec. The spec lives
on the server and changes (genre rules, concurrency caps, new modes) land
there first. Bundling a copy here just means re-syncing it forever and
risking agents following stale rules. So:

1. Export credentials (never hardcode a real key in any file you write or commit):
   ```bash
   export AQ_BASE="https://hlagency.net/api/n8n/agent-queue"
   export AQ_KEY="sk_ag_..."          # Settings → Agent API Keys, never commit this
   export AQ_AGENT="<MACHINE_ID>-claude-orchestrator-1"
   mkdir -p /tmp/agy_scratch
   ```
2. Pull the operating docs + QC tool fresh, every session, before doing anything else:
   ```bash
   curl -s "$AQ_BASE/guide" -H "X-Automation-Key: $AQ_KEY" > /tmp/agy_scratch/GUIDE.md
   curl -s "$AQ_BASE/qc"    -H "X-Automation-Key: $AQ_KEY" > /tmp/agy_scratch/cinematic_qc.py
   ```
3. Read `/tmp/agy_scratch/GUIDE.md` (via the file tool — never print it to the terminal). It is
   authoritative: API reference, 7-stage writing pipeline, Revision/Social-Kit modes, quality
   standards, the Red Team Writer/Critic pattern, current concurrency cap, current genre rules.
   If anything in this repo ever disagrees with `GUIDE.md`, **`GUIDE.md` wins**.

## What actually lives in this repo (and why)

Only things that have no server-side equivalent and are genuinely reusable across sessions:

- **`.claude/agents/CD_Writer.md` / `CD_Critic.md`** — subagent definitions so the Task tool can
  spawn `@CD_Writer` / `@CD_Critic` directly. Their system prompts tell them to read the
  freshly-fetched `/tmp/agy_scratch/GUIDE.md`, not a bundled copy.
- **`scripts/agent-worker/*`** — claim → write → qc → submit helper scripts (revision batches,
  payload building, mechanical fixes). These are workspace tooling, not spec; update them only
  when the *mechanics* of calling the API change, not when the writing rules change.

## How this orchestrator works

You (the top-level Claude Code session) are the **Orchestrator**. You hold the
only gate that allows `/complete` to be called. You never write story prose
yourself — you spawn two kinds of subagents per story via the **Task tool**:

- **CD_Writer** (`.claude/agents/CD_Writer.md`) — one per story, lives until
  PASS. Writes `task_<id>/{title,fb,comment,website,image_prompt}.txt` +
  `character_sheet.json`. Never self-approves, never submits.
- **CD_Critic** (`.claude/agents/CD_Critic.md`) — a **fresh** instance per
  review round, given a clean context (only `task_<id>/` + the task's genre
  scoring profile). Runs the QC tool as a hard gate, then scores the rubric.
  Read-only.

Claude Code has no `define_subagent` or `schedule` tool (those are
Antigravity-only) — use the Task tool to spawn, and `/loop 1m` (or a bash
`while sleep 60; do ...; done` loop) to poll the queue. Check `GUIDE.md` for
the current concurrency cap (count live CD_Writer Tasks before claiming
another — do not hardcode a number here, it has changed before).

## Main loop (per tick)

1. Claim — save to file, never print the JSON (large source transcripts get
   truncated by terminals):
   ```bash
   curl -s "$AQ_BASE/next?agent_id=$AQ_AGENT" \
     -H "X-Automation-Key: $AQ_KEY" -H "X-Agent-Id: $AQ_AGENT" \
     -H "Accept: application/json" > /tmp/agy_scratch/task.json
   ```
   `data == null` or already at the concurrency cap → do nothing this tick.
2. Otherwise `POST $AQ_BASE/<id>/start`, create `/tmp/agy_scratch/task_<id>/`,
   spawn a CD_Writer Task with the source material + `data.input.instructions`.
3. On `DRAFT_READY`, spawn a fresh CD_Critic Task. Follow `GUIDE.md` for hard-gate vs
   soft-score round limits and the PASS thresholds.
4. On PASS: build `payload.json` from the files (title from `title.txt`,
   `analysis.genre`/`analysis.genre_note` from `analysis.json` — REQUIRED, the
   server 422s without it), upload `hero.png` via `POST /<id>/image` if the
   Writer produced one, then `POST $AQ_BASE/<id>/complete`. Helper script:
   `scripts/agent-worker/build_payload.py`.
5. `rm -rf /tmp/agy_scratch/task_<id>` and claim a replacement.

Full detail (genre classification, revision mode, social kit mode, error
codes, the verdict format, current concurrency cap) is in the freshly-fetched
`GUIDE.md` — read it fully before running the loop unattended.

## Revision batches

If the queue is mostly `revision_note` tasks (bulk mechanical fixes, not fresh
stories), check `GUIDE.md` for the revision-batch kickoff instead — it skips the
7-step pipeline and the genre rubric, and drives
`scripts/agent-worker/process_one_revision.sh` / `process_revision_batch.sh`.

## Hard invariants (re-assert every tick, don't re-read the whole guide)

- Re-check the concurrency cap from `GUIDE.md` at session start — it has changed before
  (do not assume a fixed number). Writer never self-approves; submit only on Critic
  PASS or best-of ≥ 70.
- `analysis.genre` + `analysis.genre_note` MUST be in the `/complete` payload.
- HARD 60-minute timeout from claim (up to 75 min with an active heartbeat — a recent
  heartbeat buys up to 15 min of grace, but never rely on it; finish well under 60 min).
- Never commit a real `AQ_KEY` / `sk_ag_...` anywhere in this repo.
- All large JSON → file + `python3` parse. Never print raw task JSON or full
  story text into the terminal/transcript.
