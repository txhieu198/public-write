# public-write

Workspace repo for AI agents (Claude Code, Cursor IDE, Antigravity CLI) that
write Cinematic Drama stories for **Source2Draft → Agent Queue** on
`hlagency.net` (happykitemedia WebApp).

This repo holds no application code. It exists so any agent, on any
machine, can `git clone` one place and immediately have everything needed to
claim a task from the Agent Queue API, write a 3-layer story
(Facebook post / Comment / Website), get it reviewed by an independent
Critic, and submit it — without SSH or DB access to the WebApp server.

## Start here

| You are using | Read this first |
|---|---|
| **Claude Code** | `CLAUDE.md` (auto-loaded at session start) |
| **Cursor IDE** | `.cursorrules` (auto-loaded) |
| **Antigravity CLI** | `docs/guides/AGENT_KICKOFF_PROMPTS.md` §1 — paste the prompt |
| Anyone wanting the full spec | `docs/guides/CINEMATIC_DRAMA_EXTERNAL_AGENT.md` |

The guide (`docs/guides/CINEMATIC_DRAMA_EXTERNAL_AGENT.md`) is the **source of
truth** for the API, the 7-stage writing pipeline, quality gates, and the
Writer/Critic pattern. The entrypoint files in this repo (`CLAUDE.md`,
`.cursorrules`, `.claude/agents/*.md`) are thin bootstraps that point at it —
if they ever disagree, the guide wins. The server also serves the live copy
at `GET https://hlagency.net/api/n8n/agent-queue/guide` — fetch that at
session start since it may be newer than this checkout.

## Layout

```
CLAUDE.md                                   orchestrator instructions — Claude Code
.cursorrules                                orchestrator instructions — Cursor IDE
.claude/agents/CD_Writer.md                 Writer subagent definition (Claude Code Task tool)
.claude/agents/CD_Critic.md                 Critic subagent definition (Claude Code Task tool)
docs/guides/CINEMATIC_DRAMA_EXTERNAL_AGENT.md   full API + pipeline + rubric spec (source of truth)
docs/guides/AGENT_KICKOFF_PROMPTS.md        copy/paste kickoff prompts for all 3 runtimes
docs/guides/cinematic_qc.py                 deterministic QC gate (client twin of the server gate)
scripts/agent-worker/                       claim → write → qc → submit helper scripts
```

`task_<id>/` scratch directories created while writing are local-only
(git-ignored) — never commit story drafts or API keys to this repo.

## Quick start (any runtime)

```bash
git clone <this-repo> && cd public-write
export AQ_BASE="https://hlagency.net/api/n8n/agent-queue"
export AQ_KEY="sk_ag_..."          # Settings → Agent API Keys on hlagency.net
export AQ_AGENT="<MACHINE_ID>-<runtime>-orchestrator-1"
mkdir -p /tmp/agy_scratch
curl -s "$AQ_BASE/guide" -H "X-Automation-Key: $AQ_KEY" > /tmp/agy_scratch/GUIDE.md
curl -s "$AQ_BASE/qc"    -H "X-Automation-Key: $AQ_KEY" > /tmp/agy_scratch/cinematic_qc.py
```

Then follow `CLAUDE.md` / `.cursorrules` / the Antigravity kickoff prompt for
the claim → write → review → submit loop.

## Security

**Never commit a real `AQ_KEY` / automation key to this repo.** Keys are
per-agent (`sk_ag_...`), issued from `/settings/agent-keys` on the WebApp, and
belong in your shell environment only.
