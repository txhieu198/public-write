# CLAUDE.md — Cinematic Drama Agent Queue Orchestrator (universal entrypoint)

> Read by Claude Code, Antigravity CLI, Cursor, and any agent that reads the
> project root. This repo is a thin bootstrap for AI agents that claim, write,
> and submit Cinematic Drama stories to the Source2Draft → Agent Queue API on
> `hlagency.net`. It holds **no spec and no kickoff text** — both live on the
> server and are fetched fresh, so nothing here ever goes stale.
>
> If a human only told you *"pull `txhieu198/public-write`, read its
> instructions, you are <X>, here is the AQ key"* — this file IS those
> instructions. Follow the 3 steps below.

## Step 1 — Identify your role

Which runtime are you? Pick the matching `<role>` slug:

| You are…                                   | `<role>` |
|--------------------------------------------|----------|
| Claude Code                                | `claude-code` |
| Antigravity CLI                            | `antigravity-cli` |
| Cursor IDE                                 | `cursor-ide` |
| (queue is mostly bulk `revision_note` fixes, any runtime) | `revision` |

If you weren't told which runtime you are, infer it from your own tooling
(Task tool + `/loop` → `claude-code`; `define_subagent` + cron →
`antigravity-cli`; inside Cursor → `cursor-ide`).

## Step 2 — Export credentials, then fetch YOUR kickoff prompt + the live docs

Never hardcode or commit a real key. Replace `<...>` placeholders:

```bash
export AQ_BASE="https://hlagency.net/api/n8n/agent-queue"
export AQ_KEY="sk_ag_..."          # Settings → Agent API Keys, never commit this
export AQ_AGENT="<MACHINE_ID>-<runtime>-orchestrator-1"   # e.g. HLA05-claude-orchestrator-1
mkdir -p /tmp/agy_scratch

# Your role-specific bootstrap prompt (omit <role> to get an index of valid roles):
curl -s "$AQ_BASE/kickoff/<role>" -H "X-Automation-Key: $AQ_KEY" > /tmp/agy_scratch/KICKOFF.md

# The authoritative operating docs + QC tool:
curl -s "$AQ_BASE/guide" -H "X-Automation-Key: $AQ_KEY" > /tmp/agy_scratch/GUIDE.md
curl -s "$AQ_BASE/qc"    -H "X-Automation-Key: $AQ_KEY" > /tmp/agy_scratch/cinematic_qc.py
```

## Step 3 — Read `/tmp/agy_scratch/KICKOFF.md` and do exactly what it says

Read it via the file tool — never print it to the terminal. It is a complete,
self-contained orchestrator prompt for your runtime: setup, the claim → write →
QC → submit loop, heartbeat, round limits, and the `/complete` payload. It will
also tell you to read `GUIDE.md` for the full pipeline and quality rules.

**`GUIDE.md` is the single source of truth.** If anything — this file, the
kickoff, your memory — disagrees with `GUIDE.md`, **`GUIDE.md` wins.**

## What lives in this repo (and why)

Only things with no server-side equivalent, reusable across sessions:

- **`.claude/agents/CD_Writer.md` / `CD_Critic.md`** — subagent definitions so
  Claude Code's Task tool can spawn `@CD_Writer` / `@CD_Critic`. They read the
  freshly-fetched `/tmp/agy_scratch/GUIDE.md`, not a bundled copy.
- **`scripts/agent-worker/*`** — claim → write → qc → submit helper scripts
  (revision batches, payload building). Update these only when the *mechanics*
  of calling the API change — never when writing/quality rules change.

`task_<id>/` scratch dirs are local-only. **Never commit a real `AQ_KEY`
(`sk_ag_...`) or story drafts to this repo.**

## Hard invariants (re-assert every tick; don't re-read the whole guide)

- Follow the loop in your `KICKOFF.md`; re-check the concurrency cap from
  `GUIDE.md` at session start (it has changed before — never hardcode it).
- Writer never self-approves; submit only on Critic PASS or best-of ≥ 70.
- The `/complete` payload MUST carry `analysis.genre` + `analysis.genre_note`,
  a non-empty `image_prompt` (≥ 40 chars), and a `website_full` (≥ 500 chars,
  ending "THE END") — the server **422s** otherwise, and also 422s a
  `website_full` with a short phrase repeated 10+ times (repetition glitch).
- Heartbeat every ≤ 25 min for every running task — no heartbeat → reaper-killed
  at 60 min. HARD 60-min timeout from claim (up to 75 with an active heartbeat).
- All large JSON → file + `python3` parse. Never print raw task JSON or full
  story text into the terminal/transcript.
