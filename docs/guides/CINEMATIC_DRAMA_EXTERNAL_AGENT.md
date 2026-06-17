# Cinematic Drama — Self-Contained External Agent Guide

> Mirrored from `happykitemedia/docs/guides/CINEMATIC_DRAMA_EXTERNAL_AGENT.md`
> so any agent cloning **this** repo has the full spec offline. This file is
> a **mirror, not the source** — the WebApp repo (and the live
> `GET $AQ_BASE/guide` endpoint) is authoritative. Re-sync when the source
> changes; do not hand-edit the pipeline rules here.

> Tài liệu này chứa TẤT CẢ thông tin cần thiết cho bất kỳ AI agent (Antigravity CLI, Claude Code, hay script) trên **bất kỳ server nào** để claim, viết, và submit Cinematic Drama stories qua API.
> 
> **KHÔNG cần access database, KHÔNG cần file local, KHÔNG cần SSH vào server.**
>
> Người vận hành: prompt khởi động mẫu (copy/paste khi mở agent CLI / Cursor IDE / Claude Code mới)
> ở `docs/guides/AGENT_KICKOFF_PROMPTS.md`.

---

## Runtime variants

Quy trình viết (Writer + Critic, rubric, API) giống nhau ở mọi runtime — chỉ khác cơ chế spawn
subagent và polling. Prompt khởi động đầy đủ ở `docs/guides/AGENT_KICKOFF_PROMPTS.md`.

| Runtime | Spawn subagent | Poll queue | Parallel | Agent id |
|---------|----------------|------------|----------|----------|
| Antigravity CLI (§1) | `define_subagent` | `schedule` cron `* * * * *` | ≤5 stories | `{MACHINE}-cli-orchestrator-N` |
| Claude Code (§4) | Task tool / `.claude/agents/CD_Writer.md` + `CD_Critic.md` | `/loop 1m` hoặc bash while-loop | ≤5 stories | `{MACHINE}-claude-orchestrator-N` |
| Cursor IDE (§2) | — (2 role tuần tự) | thủ công | 1 story/lần | `{MACHINE}-Cursor-orchestrator-N` |

Agent id quyết định badge UI (`AgentQueueService::agentLabel()`): `cli` → CLI Agent, `claude` →
Claude Agent, `cursor`/`ide` → IDE Agent.

---

## Agent Lanes & API Keys

Per-agent keys (`sk_ag_*`) route task claims in three tiers when mode is **own_first**:

1. **Own** — tasks where `created_by` = Lane User on the key
2. **Group** — tasks from Click Tracker group peers (leader + members, same `/settings/click-tracker-groups`)
3. **Shared pool** — any remaining queued task

| Lane mode | Behavior |
|-----------|----------|
| `own_first` | Own → group → shared (recommended for **leaders and members**) |
| `own_only` | Own tasks only (isolation; not default) |
| `shared_only` | Shared pool only (pool fillers) |

Legacy shared `ENGINE_STORY_AUTOMATION_API_KEY` still works but skips lanes (global pool).

Headers unchanged: `X-Automation-Key`, `X-Agent-Id`. `/next` response includes `data.lane` and `data.created_by`.

Manual `/enqueue` requires a creator: per-agent key with `lane_user_id`, or legacy key + `ENGINE_STORY_AUTOMATION_USER_ID`.

---

## Quick Start

```bash
# 1. Set credentials (per-agent key recommended)
export AQ_BASE="https://hlagency.net/api/n8n/agent-queue"
export AQ_KEY="sk_ag_..."   # Settings → Agent API Keys (/settings/agent-keys)
export AQ_AGENT="HLA01-cli-orchestrator-1"
export SCRATCH="/tmp/agy_scratch"
mkdir -p "$SCRATCH"

# 2. Claim a task — SAVE TO FILE, do NOT print to terminal (large JSON will be truncated!)
curl -s "$AQ_BASE/next?agent_id=$AQ_AGENT" \
  -H "X-Automation-Key: $AQ_KEY" \
  -H "X-Agent-Id: $AQ_AGENT" \
  -H "Accept: application/json" > $SCRATCH/task.json

# 3. Extract task ID from file
TASK_ID=$(python3 -c "import json; d=json.load(open('$SCRATCH/task.json')); print(d['data']['task_id'] if d.get('data') else '')" 2>/dev/null)

# 4. Start → Write → Submit (see full guide below)
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  WebApp (hlagency.net)                                   │
│                                                          │
│  User → Source2Draft → Cinematic Drama + Agent Queue      │
│                              │                           │
│                        es_agent_queue                    │
│                              ▲                           │
└──────────────────────────────┼───────────────────────────┘
                               │ HTTPS API
┌──────────────────────────────┼───────────────────────────┐
│  External Agent (ANY server) │                           │
│                              │                           │
│  GET  /next          ← claim task + source material      │
│  POST /{id}/start    ← mark as running                   │
│  POST /{id}/heartbeat ← keep-alive during writing        │
│  POST /{id}/complete ← submit final story                │
│  POST /{id}/fail     ← report failure                    │
└──────────────────────────────────────────────────────────┘
```

---

## API Reference

### Authentication

All requests require these headers:

```
X-Automation-Key: <your-key>
X-Agent-Id: <unique-agent-name>
Accept: application/json
```

### Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/next?agent_id=X` | Claim next available task |
| `POST` | `/{id}/start` | Mark task as running |
| `POST` | `/{id}/heartbeat` | Send keep-alive signal |
| `POST` | `/{id}/image` | *(optional)* Upload a self-generated hero image (saves an API call) |
| `POST` | `/{id}/complete` | Submit completed story |
| `POST` | `/{id}/fail` | Report failure |

Base URL: `https://hlagency.net/api/n8n/agent-queue`

---

## Revision Mode — fix an existing draft

Some tasks are **revisions**, not fresh stories. A revision task carries, inside
`data.input.options`:

- `revision_note` — free text describing exactly what the user wants fixed
  (e.g. *"Part 1 chưa mobile friendly"*, *"tên nhân vật đổi giữa chừng"*).
- `current_draft` — the previously written draft (`title`, `chapters`
  [Facebook Post, Comment, Website], `image_prompt`) that has the problem.

The task's `instructions` already begin with a `REVISION MODE` block. When you
see `revision_note` present:

1. Read the note carefully — it is the only thing you must change.
2. Start from `current_draft`. Apply **only** the requested fix.
3. Keep everything else **verbatim** — do not rewrite from scratch, do not invent
   new events.
4. Submit the **full** corrected story in the normal `/complete` JSON shape
   (`analysis.genre`, `analysis.genre_note`, `title`, `facebook_post`, `comment`,
   `website_full`, `image_prompt`, `word_counts`) — not a diff, not a summary.
5. **Genre**: still send `analysis.genre`. `options.prior_genre` carries the genre
   this story was classified as before — reuse it unless your fix genuinely
   changes the dominant emotional engine.
6. All normal quality gates still apply (word counts, `THE END`, one sentence per
   line, no cliché names).

The server upserts: completing a revision **updates the existing story in place**
(same `s2d_job_id`), it does not create a duplicate.

### Revision Batch — mechanical fixes (bulk QC cohort)

Most bulk-revision tasks fix **one or two mechanical issues** without rewriting
the story. Bootstrap from `current_draft` (see repo scripts
`scripts/agent-worker/bootstrap_revision.py`), apply **only** what
`revision_note` asks, then run `cinematic_qc.py` until exit 0.

| Issue code | What to do | Do NOT |
|------------|------------|--------|
| `mobile_format` | Split every line to **one sentence per line**; blank line between beats | Change events, names, or wording except where splitting requires it |
| `cliche_name` | Replace forbidden names (Julian, Chloe, Sterling, Thorne, Marcus, Vance, Elara, Liam) with everyday names **consistently** across FB, Comment, Website | Rewrite plot or add new characters |
| `duplicate_line` | Remove verbatim duplicate sentences; keep one copy | Merge different sentences that happen to share words |
| `boilerplate_duplicate` | Delete repeated template openers (e.g. "I turned back to the television screen…") | Remove unique story content |
| `missing_the_end` | Add `THE END` on its own line at website end | Change the ending |
| `short_layer` | Expand only the under-length layer to meet word floors | Rewrite other layers |
| `mojibake` | Fix garbled UTF-8 / encoding artifacts | Guess missing words — restore clean English |
| `name_consistency` | Audit one person = one name throughout | Rename without narrative reason |

For mechanical revisions: **skip genre rubric soft-scoring**. The Critic step is
`cinematic_qc.py` only + confirm the revision note is addressed. Do **not** run
the full 7-step pipeline. Keep `image_prompt.txt` from the original draft unless
the note explicitly asks to change it. Skip hero image upload.

Helper scripts (on the agent machine or this repo):

```bash
python3 scripts/agent-worker/bootstrap_revision.py /tmp/agy_scratch/task.json
python3 scripts/agent-worker/build_payload.py /tmp/agy_scratch/task_<id>/
bash scripts/agent-worker/revision_progress.sh   # requires AUTOMATION_KEY
```

---

## Social Kit Mode — title + caption + comment + image_prompt

Some tasks are **social kits**: the website story is finished and LOCKED; you
write a full package for a **different FB page** — new title, Facebook Post
(Part 1), Comment (Part 2), and `image_prompt` (text only, no image upload).
Recognise by `data.input.options.repurpose_scope = "social_kit"` (legacy alias
`"p1p2"`) and `pipeline_mode = "repurpose_social_kit"`. Instructions begin
with a `SOCIAL KIT MODE` block.

Task payload:

- `source_material[0].content` — the locked website text. **Canonical truth.**
- `options.original_part1` / `original_part2` — previous P1/P2 for contrast.
- `options.repurpose_note` — optional angle directive.
- `options.website_locked_sha1` — server verifies echoed website against this hash.

Rules (differences vs a normal task):

1. Do **NOT** run the 7-step pipeline. No analyze/plan/website stages.
2. Every event, name, fact, twist and ending must match the website exactly.
3. **NEW title** (12–500 chars) for the alternate FB page — do not copy the
   original story title verbatim.
4. New Part 1 (700–1,000 w) + Part 2 (300–500 w) with a different angle; no recap.
5. **image_prompt** (40+ chars): photorealistic hero scene description — text only.
6. `/complete` JSON shape (5 required fields):

```json
{
  "title": "New clickbait headline for Page B",
  "facebook_post": "...",
  "comment": "...",
  "image_prompt": "Photorealistic scene description...",
  "website_full": "<EXACT verbatim copy of source_material[0].content>",
  "angle_summary": "1 sentence on how the angle differs",
  "word_counts": { "facebook": 850, "comment": 400 }
}
```

`website_full` must be **byte-identical** to the locked text — any edit fails
with `QUALITY_CHECK_FAILED`. Missing `title` or `image_prompt` also fails.
On success the server stages a preview variant on the S2D job; the user posts
to SO9 from the UI (title prepended to FB caption). Prose is cleared from the
job after SO9 post unless the user opts to keep the variant.

---

## Step-by-Step Workflow

### Step 1: Claim a task

```bash
# ⚠️ CRITICAL: Save to file — do NOT pipe to terminal!
# Large source material transcripts will be silently truncated by sandbox terminals.
curl -s "$AQ_BASE/next?agent_id=$AQ_AGENT" \
  -H "X-Automation-Key: $AQ_KEY" \
  -H "X-Agent-Id: $AQ_AGENT" \
  -H "Accept: application/json" > /tmp/agy_scratch/task.json

# Then read from the file:
TASK_ID=$(python3 -c "import json; d=json.load(open('/tmp/agy_scratch/task.json')); print(d['data']['task_id'] if d.get('data') else '')")
```

**Response shape (task.json):**
```json
{
  "success": true,
  "data": {
    "task_id": 15,
    "task_type": "cinematic_drama",
    "input": {
      "source_material": [
        {
          "type": "youtube",
          "title": "My Wife's Secret...",
          "text": "full transcript text here..."
        }
      ],
      "instructions": "# CINEMATIC DRAMA — AGENT PIPELINE RULES\n...",
      "pipeline_mode": "single_task_7step"
    }
  }
}
```

**Response (no tasks):**
```json
{ "success": true, "data": null, "message": "No tasks available." }
```

> ⏳ If no tasks, wait 30 seconds before trying again. Do NOT spam the API.

### Step 2: Start the task

```bash
curl -s -X POST "$AQ_BASE/$TASK_ID/start" \
  -H "X-Automation-Key: $AQ_KEY" \
  -H "X-Agent-Id: $AQ_AGENT" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json"
```

### Step 3: Read source material from file

```bash
# Extract source text from saved file
python3 -c "
import json
d = json.load(open('/tmp/agy_scratch/task.json'))
src = d['data']['input']['source_material'][0]
with open('/tmp/agy_scratch/source.txt', 'w') as f:
    f.write(src.get('text', ''))
print(f'Source: {src.get(\"title\", \"?\")} ({len(src.get(\"text\", \"\"))} chars)')
"
```

Read `/tmp/agy_scratch/source.txt` fully before writing. Never truncate or summarize the source.

### Step 4: Execute the 7-Stage Pipeline

Follow these stages IN ORDER. Each stage's output feeds the next.

---

#### Stage 1: ANALYZE (temp=0)

Read the entire source material. **FIRST classify the genre** (read the
`## GENRE CATALOG` block in `data.input.instructions`, pick exactly ONE slug),
then extract the story spine:
- **`genre`** (REQUIRED): one catalog slug — `betrayal_revenge` | `heartwarming` | `justice_exposure` | `redemption` | `mystery_reveal` | `neutral`
- **`genre_note`** (REQUIRED): short phrase naming the dominant emotional engine (load-bearing when `genre = neutral`, e.g. "survival / man-vs-nature")
- **Protagonist**: Name + age + traits (**CHANGE the real name**)
- **Antagonist**: Name + role + motivation (**CHANGE the real name**)
- **Supporting characters**: Names + relationships
- **Setting**: Time, place, social context
- **Inciting incident**: The event that starts the conflict
- **Rising action**: Key escalation points in order
- **Climax**: The peak confrontation or revelation
- **Resolution**: How it ends
- **Emotional arc**: From what → through what → to what
- **Themes**: Core themes (betrayal, resilience, justice, etc.)
- **Timeline**: Duration of events
- **First-person voice**: Brief description of narrator's personality

The `genre` you pick here is BINDING for Stages 2–7 (apply its WRITING EMPHASIS +
FORBIDDEN from the catalog) and **MUST be echoed back in the `/complete` payload
as `analysis.genre`** — the server rejects (422) a submission without it. Persist
both fields into `character_sheet.json` (or a sibling `analysis.json`) so your
payload builder can read them at submit time.

> **CRITICAL NAME RULE**: Do NOT use cliché AI-sounding names (Chloe, Julian, Sterling, Thorne, Marcus, Vance, Elara, Liam, Elena). Use extremely common, everyday names (Greg, Brian, Tyler, Megan, Heather, Dan, Craig, Brenda, Patel, Nguyen, Robinson, Miller).

---

#### Stage 2: PLAN (temp=0)

Design the 3-layer continuity:

- **Facebook Post plan**: 700-1,000 words, cliffhanger ending
- **Comment plan**: 300-500 words, open question ending  
- **Website plan**: 3,500-5,000 words, full literary story
- Define `part1_cliff_end`: exact last line of FB post (verbatim contract)
- Define `part2_question_end`: exact question ending the comment (verbatim contract)
- Name mapping: `{RealName → FictionalName}`
- Continuity notes: critical details that must stay consistent

---

#### Stage 3: HEADLINE (temp=0.7)

Choose **TITLE** or **HOOK** format:

- **TITLE**: Max 20 words. Pattern: `My [Person] Did [Shocking Thing] — [Twist]`
- **HOOK**: 2-4 sentences, in medias res, makes reader NEED to continue

Choose TITLE if the situation itself is shocking. Choose HOOK if the story needs scene-setting.

---

#### Stage 4: WRITE FACEBOOK POST (temp=1.0)

Write 700-1,000 words in **FIRST PERSON**.

Requirements:
- If hook: open with hook text, then continue into story
- If title: open with a powerful first line that drops reader into a scene
- Build tension, show don't tell, use dialogue
- Mobile format: ONE sentence per line; blank line only at beat shifts (see rule 6)
- End EXACTLY with `part1_cliff_end` — a concrete cliffhanger, not vague "what happened next"
- NO resolution — reader must feel compelled to continue

---

#### Stage 5: WRITE COMMENT (temp=1.0)

Write 300-500 words in **FIRST PERSON**.

Requirements:
- Continue IMMEDIATELY from where Part 1 ended. **NO RECAP.**
- First sentence flows naturally from `part1_cliff_end`
- Advance the story through next major arc beats
- End with `part2_question_end` — an emotional open question
- Same narrator voice as Part 1

---

#### Stage 6: WRITE WEBSITE (temp=1.0)

Write 3,500-5,000 words in **THIRD PERSON**. This is a FULL literary story.

Requirements:
- Switch to THIRD PERSON. Protagonist gets a name from name_mapping.
- Open by resolving `part2_question_end` in first 1-2 paragraphs
- **Part A (~2,000-2,500 words)**: Setup, backstory, rising tension, scene-by-scene
- **Part B (~1,500-2,500 words)**: Climax, confrontation, resolution, epilogue
- Rich sensory detail, dialogue, internal monologue
- End with a powerful final image, then `THE END` on its own line
- NO recapping Parts 1-2 — this retells the FULL story cinematically

---

#### Stage 7: HERO IMAGE PROMPT (temp=0.4)

Create ONE hero image prompt:
- Scene-first: describe the visual scene, not abstract concepts
- Include: lighting, composition, camera angle, color palette
- Character descriptions (clothing, expressions, body language)
- Style: photorealistic, cinematic, 35mm film grain
- Do NOT include text/words in the image
- One powerful emotional moment from the story

---

### Step 5: Submit the completed story

`analysis.genre` is REQUIRED — it is the genre you classified in Stage 1. Send the
full payload (note the `analysis` object at the top):

```bash
curl -s -X POST "$AQ_BASE/$TASK_ID/complete" \
  -H "X-Automation-Key: $AQ_KEY" \
  -H "X-Agent-Id: $AQ_AGENT" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "analysis": {
      "genre": "betrayal_revenge",
      "genre_note": "humiliation answered with a cold, precise reversal"
    },
    "title": "My CEO Wife Handed Me a Prenup — She Had No Idea Who She Married",
    "facebook_post": "<full FB post text>",
    "comment": "<full comment text>",
    "website_full": "<full website story ending with THE END>",
    "image_prompt": "<cinematic scene description for hero image>",
    "word_counts": {
      "facebook": 850,
      "comment": 420,
      "website": 4200,
      "total": 5470
    }
  }'
```

On submit the server, in order:
- ✅ **Runs the deterministic quality gate** (returns **422 `QUALITY_CHECK_FAILED`** on any failure — see Quality Standards). Fix and resubmit on 422. The gate runs server-side on every submission — it cannot be bypassed.
- ✅ Creates Engine Story blueprint + story + draft post and marks the Source2Draft job `completed` — synchronously, fast.
- ✅ **Queues** hero image generation (Gemini, Grok fallback) as a background job. The `/complete` response returns immediately; the image URL appears on the job shortly after. Image failure is non-fatal — the story is unaffected.

> By default the agent supplies only the `image_prompt` text and the server renders the image. If your agent **can** generate images, you may upload your own instead (see "Hero image — generate it yourself" below) to save the server-side API call. Always still send `image_prompt` as the fallback.

## Hero image — generate it yourself (optional, saves API cost)

If your CLI can produce images (e.g. Antigravity), generate the hero image
locally and upload it — the server then skips its own paid Gemini/Grok call. This
is a pure **override with fallback**: if you don't upload, or the upload is
rejected, the server generates the image from your `image_prompt` as usual.

**Send it BEFORE `/complete`** (while the task is `running`):

```bash
# multipart (jpeg / png / webp, ≤ 8 MB, 512–4096px each side)
curl -s -X POST "$AQ_BASE/$TASK_ID/image" \
  -H "X-Automation-Key: $AQ_KEY" -H "X-Agent-Id: $AQ_AGENT" \
  -F "image=@/tmp/agy_scratch/hero_${TASK_ID}.png"

# or JSON base64
curl -s -X POST "$AQ_BASE/$TASK_ID/image" \
  -H "X-Automation-Key: $AQ_KEY" -H "X-Agent-Id: $AQ_AGENT" \
  -H "Content-Type: application/json" \
  -d "{\"image_b64\":\"<base64-bytes>\"}"
```

Rules the server enforces:
- **Format:** jpeg / png / webp only. SVG/GIF and anything that isn't a real
  raster image are rejected (the bytes are re-decoded server-side).
- **Size:** ≤ 8 MB; dimensions 512–4096px per side. Match the normal hero ratio
  (1:1 square) for consistent rendering.
- The server **re-encodes** the image, applies the **AI-disclosure watermark**,
  converts to WebP and stores it — exactly like a server-generated image. You
  cannot bypass the watermark.
- Response: `{ "success": true, "data": { "illustration_url": "...", "source": "agent_upload" } }`.
- **Do NOT retry these** — they mean the task is no longer writable, so stop working it:
  `409 TASK_TERMINAL` (the 60-min reaper already failed the task) and
  `410 JOB_GONE` (a user deleted the source job). Move on to the next task.
- `500 STORE_FAILED` now means exactly one thing: a server-side disk/watermark
  write error. It is retryable once; if it persists, report failure and move on.
- Even if the source job was deleted mid-run, your `/complete` payload is **not
  wasted**: the server still bridges the story into Engine Story and records
  `bridge_meta.skip_reason = "job_missing"` on the task. Only the Source2Draft
  job status update is skipped.

You **still include `image_prompt`** in the `/complete` payload — it is the
fallback if the upload never arrives or fails validation.

> The API tolerates the two most common client mistakes: `/next` accepts **POST**
> as well as GET, and the automation key is read from `X-Automation-Key`,
> `X-Api-Key`, or `Authorization: Bearer`. The canonical form is still
> `GET /next` with `X-Automation-Key`.

> ⚠️ **The server gate is a backstop, not your QA.** It only catches *objective floors* (too short, missing `THE END`, walls of text, duplicate lines, the 8 hard-blocked cliché names). It does **not** catch character-name drift, weak emotional charge, padding, or tell-not-show. Those are caught by your **independent Red Team Critic + `cinematic_qc.py`** before you submit (see "Red Team — Two-Subagent Pattern" below). Do not lean on the 422 to find quality problems for you.

### Step 6: Verify (optional)

```bash
curl -s "https://hlagency.net/api/n8n/source2draft/jobs" \
  -H "X-Automation-Key: $AQ_KEY" | python3 -c "
import json,sys
for j in json.load(sys.stdin).get('data',{}).get('jobs',[])[:5]:
    print(f'#{j[\"id\"]} | {j[\"status\"]:10} | {j.get(\"title\",\"?\")[:60]}')
"
```

---

## Genre classification — YOU decide it in Stage 1 (changed 2026-06-17)

**You classify the genre yourself.** Fresh `single_task_7step` tasks are no longer
pre-classified server-side. The task ships a full **GENRE CATALOG** and you pick
exactly one slug in Stage 1 ANALYZE, then apply it for the rest of the run.

- `input_json.instructions` contains a `## GENRE CATALOG` block listing every
  genre (betrayal_revenge, heartwarming, justice_exposure, redemption,
  mystery_reveal, and the adaptive `neutral`) with its WHEN-TO-PICK hint, WRITING
  EMPHASIS, FORBIDDEN patterns and EMOTIONAL-CHARGE AXIS guidance.
- In **Stage 1 ANALYZE**, return `genre` (one catalog slug) and `genre_note`
  (the dominant emotional engine, required — load-bearing when `genre = neutral`).
- Apply the WRITING EMPHASIS + FORBIDDEN of the genre you chose across Stages 2–7.
- The `## GENRE SCORING PROFILE` block is **universal** (identical dimensions,
  weights, floors and pass thresholds for every genre); only the `emotional_charge`
  axis guidance adapts to the genre you selected.

**On POST /complete you MUST send `analysis.genre`** (and `analysis.genre_note`):

```json
{ "analysis": { "genre": "heartwarming", "genre_note": "kindness repaid unexpectedly" }, "title": "...", "facebook_post": "...", "comment": "...", "website_full": "...", "image_prompt": "...", "word_counts": { } }
```

The server rejects a submission (HTTP 422) whose `analysis.genre` is missing or
not a valid catalog slug. The chosen genre is persisted onto the S2D job and the
task's `engine_slug` only when the job completes (it drives the UI badge + Jobs
Manager filter — a job in progress shows no badge).

Rules:

1. Pick the ONE genre whose engine best fits the source; if none dominates, use
   `neutral` and name the real engine in `genre_note`.
2. Do not force a betrayal/revenge frame onto a source that is not one — a
   `heartwarming` story earns its payoff through warmth and restraint, never rage.
3. **Revision tasks**: reuse `input.options.prior_genre` unless your fix genuinely
   changes the dominant engine; still return `analysis.genre`.
4. Legacy in-flight tasks (enqueued before this change) may carry a pre-tagged
   `options.genre` and two baked genre blocks (`## GENRE PROFILE` /
   `## GENRE SCORING PROFILE`). If your task has those, follow them as written —
   the server falls back to the pre-tagged genre when `analysis.genre` is absent.

---

## Quality Standards

| Part | Words | Min | Voice | Key Rule |
|------|-------|-----|-------|----------|
| Facebook Post | 700-1,000 | 700 | First person | Must end with concrete cliffhanger |
| Comment | 300-500 | 300 | First person | Must end with emotional open question |
| Website | 3,500-5,000 | 3,500 | Third person | Must end with "THE END" |
| **Total** | **4,500-6,500** | **4,500** | — | — |

> **Server-enforced gate (returns 422 from `/complete`).** Aim for the targets above. The hard rejections are:
> - Facebook **< 650**, Comment **< 250**, Website **< 3,000** words.
> - Website not ending in `THE END`.
> - **Walls of text** — any line cramming 3+ sentences (mobile format: one sentence per line).
> - **Verbatim duplicate lines** (40+ chars repeated — a generation glitch).
> - Any of these **8 hard-blocked cliché names**: `Julian, Chloe, Sterling, Thorne, Marcus, Vance, Elara, Liam`.
>
> The gate does **not** check name-drift, subtext, or padding — those are your Critic's job. Write to the targets, not the floor.

### Absolute Rules

1. **CHANGE ALL NAMES** from source material.
2. **No AI-cliché names** (Julian, Chloe, Sterling, Thorne, Marcus, Vance, Elara, Liam, Elena). Use extremely common real-life names (Greg, Brian, Heather, Nguyen).
3. **No recap between parts** — each continues where previous left off.
4. **First person** for FB + Comment, **Third person** for Website.
5. **No emojis, hashtags, or meta-commentary**.
6. **Mobile format (mandatory)** — Write **ONE sentence per line**. Insert ONE blank line **only** at scene/beat shifts — never after every line, and never group 3+ sentences into a block. Stories are read on phones; a wall of text loses the reader. Applies to **all three** sections (FB, Comment, Website).
7. **Website ends with "THE END"** on its own line.
8. **FB cliffhanger is mandatory** — reader must feel compelled to read comment.
9. **Comment open question is mandatory** — reader must visit website.
10. **Action Beats & Subtext** — Do not use dialogue tags like "he said". Use gestures and breathing. Hide true emotions behind silence or deflections.
11. **Anti-Padding Rule** — Vary your sentence structures. Do not start consecutive sentences with the same pronoun or "-ing" clauses.

---

## Error Handling

### Report failure

```bash
curl -s -X POST "$AQ_BASE/$TASK_ID/fail" \
  -H "X-Automation-Key: $AQ_KEY" \
  -H "X-Agent-Id: $AQ_AGENT" \
  -H "Content-Type: application/json" \
  -d '{"error_message": "Source material too short to write a full story"}'
```

System auto-retries up to 3 times.

### Send heartbeat (long tasks)

```bash
curl -s -X POST "$AQ_BASE/$TASK_ID/heartbeat" \
  -H "X-Automation-Key: $AQ_KEY" \
  -H "X-Agent-Id: $AQ_AGENT" \
  -H "Content-Type: application/json" \
  -d '{"progress": "Writing website section A..."}'
```

> ⏱️ **Hard 60-minute timeout.** A reaper runs every 5 minutes and **auto-fails**
> any task — and its linked Source2Draft job — that has not finished within
> **60 minutes of being claimed**. This is anchored on claim time, **not** idle
> time, so heartbeats do **not** extend it: a task stuck in an endless revision
> loop is failed at 60 min just like a disconnected agent. Budget your whole
> Actor–Critic loop (write + all review rounds) to finish well under 60 minutes,
> or the story is dropped and must be retried from the UI. Heartbeats still
> matter for progress visibility, but they will not buy you past the hard cap.

---

## Worker Loop Script

See `scripts/agent-worker/` in this repo for runnable versions of the loop
below (`process_one_revision.sh`, `process_revision_batch.sh`,
`bootstrap_revision.py`, `build_payload.py`, `apply_mechanical_fix.py`).

```bash
#!/bin/bash
# === Cinematic Drama Worker Loop ===

AQ_BASE="https://hlagency.net/api/n8n/agent-queue"
AQ_KEY="<your-key>"
AQ_AGENT="worker-$(hostname)-1"
POLL_INTERVAL=30
SCRATCH="/tmp/agy_scratch"
mkdir -p "$SCRATCH"

echo "🎬 Cinematic Drama Worker started (agent=$AQ_AGENT)"

while true; do
  # ⚠️ Save to file — never pipe large JSON to terminal (truncation risk!)
  curl -s "$AQ_BASE/next?agent_id=$AQ_AGENT" \
    -H "X-Automation-Key: $AQ_KEY" \
    -H "X-Agent-Id: $AQ_AGENT" \
    -H "Accept: application/json" > $SCRATCH/task.json

  TASK_ID=$(python3 -c \
    "import json; d=json.load(open('$SCRATCH/task.json')); print(d['data']['task_id'] if d.get('data') else '')" 2>/dev/null)

  if [ -z "$TASK_ID" ]; then
    echo "$(date +%H:%M:%S) No tasks. Sleeping ${POLL_INTERVAL}s..."
    sleep $POLL_INTERVAL
    continue
  fi

  echo "$(date +%H:%M:%S) Claimed task #$TASK_ID"

  # Start
  curl -s -X POST "$AQ_BASE/$TASK_ID/start" \
    -H "X-Automation-Key: $AQ_KEY" \
    -H "X-Agent-Id: $AQ_AGENT" \
    -H "Content-Type: application/json" > /dev/null

  # Extract source to dedicated file (avoid any stdout truncation)
  python3 -c "
import json
d = json.load(open('$SCRATCH/task.json'))
src = d['data']['input']['source_material'][0]
with open('$SCRATCH/source_${TASK_ID}.txt', 'w') as f:
    f.write(src.get('text',''))
print(f'Source: {src.get(\"title\",\"?\")} ({len(src.get(\"text\",\"\"))} chars)')
"

  # Heartbeat — progress visibility only. NOTE: there is a HARD 60-min timeout
  # from claim (reaper every 5 min) that heartbeats do NOT extend; finish the
  # whole story well under 60 min or it is auto-failed.
  curl -s -X POST "$AQ_BASE/$TASK_ID/heartbeat" \
    -H "X-Automation-Key: $AQ_KEY" -H "X-Agent-Id: $AQ_AGENT" \
    -H "Content-Type: application/json" \
    -d '{"progress":"writing"}' > /dev/null

  # >>> YOUR AI WRITING LOGIC HERE <<<
  # Feed $SCRATCH/source_${TASK_ID}.txt to your AI model.
  # Generate title, facebook_post, comment, website_full, image_prompt.
  # Save result to $SCRATCH/payload_${TASK_ID}.json
  # NOTE: image_prompt is TEXT only. The hero image is generated server-side
  #       ASYNCHRONOUSLY after you submit — you never see or validate it, and
  #       it no longer delays the /complete response.

  # Submit — capture the HTTP status so quality failures are not lost silently.
  HTTP=$(curl -s -o $SCRATCH/resp_${TASK_ID}.json -w "%{http_code}" \
    -X POST "$AQ_BASE/$TASK_ID/complete" \
    -H "X-Automation-Key: $AQ_KEY" \
    -H "X-Agent-Id: $AQ_AGENT" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d @$SCRATCH/payload_${TASK_ID}.json)

  case "$HTTP" in
    2*)  echo "$(date +%H:%M:%S) ✅ Task #$TASK_ID completed" ;;
    422) # QUALITY_CHECK_FAILED — read the error, FIX the draft, resubmit. Do NOT skip.
         echo "$(date +%H:%M:%S) ⚠️ Task #$TASK_ID rejected (422):"; cat $SCRATCH/resp_${TASK_ID}.json
         # → regenerate the failing part and POST /complete again,
         #   or POST /$TASK_ID/fail if genuinely unfixable.
         ;;
    000|5*) # Network/timeout (incl. Cloudflare 522). Image gen is async now, so
            # /complete returns fast and a 5xx usually means it did NOT commit.
            # completeTask is idempotent: verify via /list, then retry safely
            # (a real success returns 409 "already terminal" on retry).
            echo "$(date +%H:%M:%S) ⚠️ Task #$TASK_ID submit error ($HTTP) — verify via /list, then retry" ;;
    *)   echo "$(date +%H:%M:%S) ⚠️ Task #$TASK_ID unexpected status $HTTP"; cat $SCRATCH/resp_${TASK_ID}.json ;;
  esac

  # Cleanup
  rm -f $SCRATCH/source_${TASK_ID}.txt $SCRATCH/payload_${TASK_ID}.json $SCRATCH/resp_${TASK_ID}.json
done
```

---

## Red Team — Two-Subagent Pattern (REQUIRED for orchestrated runs)

The writer must **not** review its own work. An LLM that produced a flaw
(name drift, padding, a wall of text) shares the exact blind spot when it
re-reads its own draft — self-grading is theatre. Use **two independent
subagents per story**, gated by the Orchestrator:

```
Orchestrator
  ├─ spawns  CD_Writer  (one per story, lives until PASS) ──► writes draft FILES
  └─ spawns  CD_Critic  (fresh per review round, CLEAN context) ──► verdict
        Orchestrator holds the gate: submit ONLY when Critic returns PASS.
```

**Hard rules that make this real (not self-grading):**

1. **Separate subagent TYPES, not `TypeName: "self"`.** The Critic has its own
   adversarial system prompt ("find faults, default to FAIL"). It is **not** a
   clone of the Writer.
2. **Critic gets CLEAN context** — only the draft files + this rubric. Never
   pass it the Writer's reasoning or justifications, or you reintroduce the bias.
3. **The Orchestrator owns the gate**, not the Writer. The Writer cannot decide
   "good enough" and submit. Only a Critic `PASS` unlocks `/complete`.
4. **The Critic measures, it does not eyeball.** It runs `cinematic_qc.py`
   (below) first, then judges the subjective items. Max 4 revision rounds,
   then `POST /<id>/fail`.

### Draft file layout (Writer writes these into `task_<id>/`)

```
character_sheet.json   Stage-1 sheet: [{"role":"...","assigned_name":"...","traits":"..."}]
title.txt              the Stage-3 headline (becomes the payload `title` — REQUIRED)
fb.txt                 facebook_post
comment.txt            comment
website.txt            website_full (ends with THE END)
image_prompt.txt       image_prompt (text only)
```

> The Orchestrator builds `payload.json` from these files. `title.txt` is
> **mandatory** — without it there is no real title and the Orchestrator would
> have to invent a bad placeholder (e.g. "viral cinematic story"). Always read
> the title from `title.txt`, never improvise one.

### Critic step 1 — run the deterministic gate

```bash
python3 cinematic_qc.py task_<id>
```

`cinematic_qc.py` is the strict client twin of the server gate. It checks word
floors, `THE END`, mobile walls (one sentence per line), duplicate lines,
cliché names, **and surfaces character-name-drift candidates** by comparing
capitalised mid-sentence names against `character_sheet.json`. For each drift
candidate the Critic decides: a **person** name not in the sheet = real drift
(FAIL, e.g. `Brenda` → `Eleanor`); a **place/company** (Boston, Henderson) =
ignore. Any non-zero exit = the draft is not ready.

> Fetch the script once at session start (single source of truth, kept in sync
> with the server gate):
> ```bash
> curl -s "$AQ_BASE/qc" -H "X-Automation-Key: $AQ_KEY" > cinematic_qc.py
> ```
> Canonical copy lives in the repo at `docs/guides/cinematic_qc.py`.

### Critic step 2 — score the quality rubric (NOT binary)

> **ONE RUBRIC FOR ALL GENRES (authoritative):** each task's `input_json.instructions` carries a
> universal `## GENRE SCORING PROFILE` block. The dimensions, weights, floors and pass thresholds are
> IDENTICAL for every genre — `emotional_charge` permanently replaces `rage_bait` as the genre
> axis. What changes is only the one-line guidance defining what `emotional_charge` means for the
> **genre the Writer selected in Stage 1** (e.g. Heartwarming = earned tears via restraint, NOT rage;
> Betrayal = injustice + cold reversal). The Critic reads that genre from the Writer's
> `character_sheet.json` / `analysis.json` (`genre` + `genre_note`) and scores `emotional_charge`
> against the matching `## GENRE CATALOG` entry's EMOTIONAL-CHARGE AXIS line. **Use the embedded
> catalog + the Writer's chosen genre**; if a task instead carries an older baked per-genre block
> (`## GENRE PROFILE` + a different axis name, legacy in-flight tasks), follow that embedded block
> as written. The chosen genre swaps the WRITING emphasis + forbidden patterns — but never the
> scoring yardstick.

Binary pass/fail loops forever — no draft is ever perfect, so one subjective nit
would reject 16 attempts in a row. Instead, **score a weighted rubric (0–100)**
and pass at a threshold. The hard gate (step 1) stays binary; quality is scored.

**Viral-first weighting** — this is Facebook content, so the FB post and the
comment (the layers that actually drive reach) carry the most weight and have
their own minimum floors:

| Dimension | Pts | Viral-critical floor |
|---|---|---|
| **FB hook & cliffhanger** | 20 | **≥ 17/20** |
| **Comment open-question pull** | 15 | **≥ 13/15** |
| Emotional charge (the source's dominant pull, FB+comment) | 15 | ≥ 10/15 |
| Prose variety / anti-padding | 12 | — |
| Action beats & subtext (show-don't-tell) | 12 | — |
| Continuity & logic (names/timeline/distances) | 13 | — |
| Website pacing & 3-layer structure (no recap) | 13 | — |
| **TOTAL** | **100** | |

**PASS condition (all three must hold):**
1. Step 1 hard gate is all-green (`cinematic_qc.py` exit 0), AND
2. TOTAL ≥ **80**, AND
3. FB hook ≥ **17/20** AND Comment ≥ **13/15** (the viral layer must be near-perfect).

If TOTAL ≥ 80 but a viral-critical floor is missed → still FAIL, and the FIXES
must target the FB/comment layer first.

### Loop control — guaranteed termination (the anti-16-attempts fix)

The **Orchestrator** owns this loop and tracks the best draft seen so far:

- **Hard-gate fail** (step 1) → Writer fixes the exact items. Deterministic, so it
  converges. Cap **4** hard rounds; still failing → `POST /<id>/fail`.
- **Score ≥ threshold** → submit immediately.
- **Score < threshold** → Writer revises only the **2 lowest-scoring dimensions**
  (targeted, never a full rewrite), prioritising FB/comment. Cap **3** soft rounds.
- **Best-of fallback (key):** after 3 soft rounds without a PASS, submit the draft
  with the highest **(FB hook + Comment)** subtotal, provided TOTAL ≥ **70** and the
  hard gate passes. Only `POST /<id>/fail` if even the best draft has TOTAL < 70
  (genuinely weak source — rare).

This caps each story at ~4 hard + 3 soft rounds and **always ends in a submission**
unless the source is unwritable. No infinite loops.

### Critic verdict format (return this, then terminate)

```
VERDICT: PASS | FAIL
HARD_GATE: <paste cinematic_qc.py output — must be exit 0 to score>
SCORES:
  fb_hook: N/20        (floor 17)
  comment_pull: N/15   (floor 13)
  emotional_charge: N/15 (floor 10)
  prose_variety: N/12
  action_subtext: N/12
  continuity: N/13
  website_pacing: N/13
  TOTAL: N/100
FB_COMMENT_SUBTOTAL: N/35   (used for best-of selection)
FIXES: <file:line fixes for the 2 lowest dims, FB/comment first — empty when PASS>
```

> ⚠️ **CONTEXT CONTAMINATION:** 1 Writer = 1 story (it may live across revision
> rounds of *that* story). Never let one Writer process multiple stories in a
> loop — it will mix up characters and plots. Spawn a fresh Writer per task, and
> a fresh Critic per review round.

### Ready-to-use subagent system prompts

These are also kept as standalone files in this repo, ready to paste into
`define_subagent` (Antigravity) or use as Claude Code Task subagent prompts:
`.claude/agents/CD_Writer.md` and `.claude/agents/CD_Critic.md`.

**`CD_Writer`** — `enable_write_tools: true`, `enable_subagent_tools: false`:

```text
Bạn là chuyên gia viết Cinematic Drama. Bạn chỉ VIẾT, không tự duyệt, không tự nộp.
- Đọc source bằng tool file (KHÔNG in terminal). Theo ĐÚNG data.input.instructions (7-stage).
- Stage 1 BẮT BUỘC ghi character_sheet.json gồm mọi nhân vật + assigned_name. Sau đó
  KHÔNG dùng tên người nào ngoài danh sách này — khế ước tên, vi phạm = lỗi nặng.
- Tránh tên cliché server chặn: Julian, Chloe, Sterling, Thorne, Marcus, Vance, Elara, Liam.
  Dùng tên đời thường: Greg, Brian, Tyler, Megan, Heather, Dan, Craig, Brenda, Nguyen...
- Ghi ra file riêng trong task_<id>/: title.txt (headline Stage 3 — BẮT BUỘC),
  fb.txt, comment.txt, website.txt, image_prompt.txt. KHÔNG được thiếu title.txt
  (thiếu → Orchestrator phải bịa tiêu đề rác như "viral cinematic story").
- (Tuỳ chọn) Nếu bạn TẠO ẢNH được: tạo hero image 1:1 lưu hero.png trong task_<id>/ để
  Orchestrator upload qua POST /<id>/image (tiết kiệm API). VẪN phải ghi image_prompt.txt làm fallback.
- MOBILE FORMAT: một câu một dòng; dòng trống chỉ ở chuyển cảnh, không sau mỗi câu.
- Ngôi: FB + Comment ngôi 1; Website ngôi 3, kết "THE END" trên dòng riêng.
- Action beats thay tag thoại; subtext; KHÔNG kể thẳng cảm xúc ("máu tôi sôi" = cấm).
- Anti-padding: không mở nhiều câu liên tiếp bằng cùng đại từ/danh từ.
- Heartbeat "$AQ_BASE/<id>/heartbeat" ≥1 lần/<30 phút khi viết dài.
- VIRAL-FIRST: đây là nội dung Facebook — fb.txt (hook+cliffhanger) và comment.txt
  (câu hỏi mở) là quan trọng NHẤT, phải mạnh nhất. Dồn công nhiều nhất cho 2 file này.
- Viết xong báo "DRAFT_READY" + liệt kê file. KHÔNG tự đánh giá chất lượng.
- Khi Orchestrator gửi FIXES từ Critic: sửa ĐÚNG các mục đó (ưu tiên FB/comment trước),
  KHÔNG viết lại từ đầu các phần đang ổn, báo "REVISED". Lặp lại.
- Chỉ terminate khi Orchestrator báo PASS/ACCEPT.
```

**`CD_Critic`** — `enable_write_tools: false` (read-only + shell to run qc.py):

```text
Bạn là Red Team Critic ĐỘC LẬP. Bạn KHÔNG viết, KHÔNG sửa, KHÔNG khen. Việc của bạn là
TÌM LỖI để đánh trượt. Mặc định bài LỖI tới khi qua hết gate. Bạn không biết gì về quá
trình viết — chỉ có file draft + character_sheet.json + rubric này.

BƯỚC 1 — Chạy gate deterministic (BẮT BUỘC, không đoán bằng mắt):
    python3 /tmp/agy_scratch/cinematic_qc.py /tmp/agy_scratch/task_<id>
  Nó kiểm: word floor (FB≥700/Cmt≥300/Web≥3500), "THE END", mobile walls (dòng ≥2 câu),
  dup-line, tên cliché, và LIỆT KÊ name-drift candidates (tên viết hoa giữa câu không có
  trong character_sheet). Với mỗi candidate: tên NGƯỜI không có trong sheet = drift thật
  → FAIL (vd Brenda→Eleanor); tên ĐỊA DANH/CÔNG TY (Boston, Henderson) = bỏ qua.
  Exit khác 0 → có lỗi deterministic → VERDICT FAIL.

BƯỚC 2 — CHẤM ĐIỂM rubric (KHÔNG nhị phân — tránh loop vô tận). Chỉ chấm khi BƯỚC 1 sạch.
  Đây là nội dung Facebook → ưu tiên VIRAL: FB post + Comment nặng điểm nhất và có sàn riêng.
  Chấm từng mục (tổng 100):
    - fb_hook (hook & cliffhanger FB) ............. /20   (sàn ≥17)
    - comment_pull (câu hỏi mở của Comment) ....... /15   (sàn ≥13)
    - emotional_charge (cảm xúc chủ đạo của nguồn, FB+comment) /15  (sàn ≥10)
    - prose_variety (anti-padding) ................ /12
    - action_subtext (show-don't-tell) ............ /12
    - continuity (tên/timeline/logic) ............. /13
    - website_pacing (cấu trúc 3 lớp, no recap) ... /13
  PASS khi: BƯỚC 1 sạch VÀ TOTAL≥80 VÀ fb_hook≥17 VÀ comment_pull≥13.
  Nếu TOTAL≥80 nhưng FB/Comment dưới sàn → vẫn FAIL, FIXES nhắm lớp FB/comment TRƯỚC.
  FIXES chỉ ghi cho 2 mục điểm thấp nhất (sửa trúng, không viết lại từ đầu).

TRẢ VỀ ĐÚNG ĐỊNH DẠNG rồi terminate:
  VERDICT: PASS | FAIL
  HARD_GATE: <dán nguyên output cinematic_qc.py — phải exit 0 mới chấm điểm>
  SCORES: fb_hook N/20 | comment_pull N/15 | emotional_charge N/15 | prose_variety N/12 |
          action_subtext N/12 | continuity N/13 | website_pacing N/13 | TOTAL N/100
  FB_COMMENT_SUBTOTAL: N/35
  FIXES: <sửa cụ thể file:dòng cho 2 mục thấp nhất, FB/comment trước — rỗng nếu PASS>
```

---

## FAQ

**Q: Do I need SSH access to the WebApp server?**
A: No. Everything works via HTTPS API. Only need the automation key.

**Q: Can multiple agents run simultaneously?**
A: Yes. Each agent claims different tasks. Use unique `agent_id` per agent.

**Q: Who creates tasks in the queue?**
A: Users on WebApp submit YouTube links to Source2Draft → select Cinematic Drama + Agent Queue mode → system extracts transcript and creates task.

**Q: What happens after I submit?**
A: System auto-generates hero image, creates Engine Story records, and marks the Source2Draft job as completed. Result visible at `/source2draft`.

**Q: What if Supadata transcript extraction fails?**
A: The task stays in failed state. Admin can retry from the Source2Draft UI or reset via command line.

**Q: Can I use any AI model?**
A: Yes. The API doesn't care what model you use — only the output quality matters. The `instructions` field in the task tells you exactly what to produce.
