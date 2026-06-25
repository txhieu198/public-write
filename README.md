# public-write

Workspace repo for AI agents (Claude Code, Cursor IDE, Antigravity CLI) that
write Cinematic Drama stories for **Source2Draft → Agent Queue** on
`hlagency.net` (happykitemedia WebApp).

This repo holds no application code, and — by design — **no mirrored copy of
the spec**. The spec (API reference, 7-stage pipeline, quality gates, genre
rules, concurrency caps) lives on the server and changes there first. A
bundled copy here would just go stale and need re-syncing forever, which is
exactly what kept happening before this repo was trimmed down. So: this repo
is just the bootstrap + reusable tooling; the rules always come from
`GET $AQ_BASE/guide` and `GET $AQ_BASE/qc`, fetched fresh every session.

## Start here

**`CLAUDE.md` is the universal entrypoint** for every runtime (Claude Code,
Antigravity CLI, Cursor, any agent that reads the repo root). To start a new
agent you only need to tell it: *"pull `txhieu198/public-write`, read its
instructions, you are `<runtime>`, here is the AQ key."* `CLAUDE.md` then has
it (1) identify its role, (2) fetch its role-specific kickoff prompt from the
server, (3) follow it.

The kickoff prompts are served per-role from the WebApp — no copy is bundled
here, so they never go stale:

```bash
export AQ_BASE="https://hlagency.net/api/n8n/agent-queue"
export AQ_KEY="sk_ag_..."          # Settings → Agent API Keys on hlagency.net
export AQ_AGENT="<MACHINE_ID>-<runtime>-orchestrator-1"
mkdir -p /tmp/agy_scratch

# role ∈ claude-code | antigravity-cli | cursor-ide | revision (omit for an index)
curl -s "$AQ_BASE/kickoff/<role>" -H "X-Automation-Key: $AQ_KEY" > /tmp/agy_scratch/KICKOFF.md
curl -s "$AQ_BASE/guide"          -H "X-Automation-Key: $AQ_KEY" > /tmp/agy_scratch/GUIDE.md
curl -s "$AQ_BASE/qc"             -H "X-Automation-Key: $AQ_KEY" > /tmp/agy_scratch/cinematic_qc.py
```

Every entrypoint's first instruction is the same: fetch the live kickoff +
guide + QC tool before doing anything else, and treat them as authoritative
over anything in this repo. (Cursor IDE: `.cursorrules` is auto-loaded and
points at the same flow.)

## Layout

```
CLAUDE.md                        orchestrator bootstrap — Claude Code (fetch-guide-first)
.cursorrules                     orchestrator bootstrap — Cursor IDE (fetch-guide-first)
.claude/agents/CD_Writer.md      Writer subagent definition (Claude Code Task tool)
.claude/agents/CD_Critic.md      Critic subagent definition (Claude Code Task tool)
scripts/agent-worker/            claim → write → qc → submit helper scripts
```

There is no `docs/guides/` mirror and no bundled kickoff prompts — both are
served fresh from the WebApp (`$AQ_BASE/guide`, `$AQ_BASE/kickoff/<role>`).
The only things that live in this repo are things with **no server-side
equivalent**: subagent definitions and workspace tooling scripts. Update them
when the *mechanics* of calling the API change, not when writing/quality
rules change (those live entirely on the server).

`task_<id>/` scratch directories created while writing are local-only
(git-ignored) — never commit story drafts or API keys to this repo.

## Security

**Never commit a real `AQ_KEY` / automation key to this repo.** Keys are
per-agent (`sk_ag_...`), issued from `/settings/agent-keys` on the WebApp, and
belong in your shell environment only.
