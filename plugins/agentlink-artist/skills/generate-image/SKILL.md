---
name: generate-image
description: >
  Generate an image from a prompt_seed using FAL.ai. Reads narration.json produced
  by /agentlink-director:gen-prompt-seed by default, or accepts a prompt directly
  via --prompt. Supports model override (default: fal-ai/flux/dev). Handles both
  synchronous and async FAL jobs (polls until complete). Writes image-result.json
  to the current directory with the output URL, model used, and criteria for review.
  Use after /agentlink-director:gen-prompt-seed, or standalone with --prompt.
argument-hint: "[narration-file] [--model <fal-model-id>] [--prompt <text>] [--out <file>]"
allowed-tools:
  - Read
  - Write
  - mcp__fal-ai__run_model
  - mcp__fal-ai__submit_job
  - mcp__fal-ai__check_job_status
---

# Generate Image

Generate an image via FAL.ai from a prompt_seed and write the result locally.
If the brief came from the director pipeline, the narration.json already contains
everything needed: prompt_seed, period, theme_id, and evaluation criteria.

This skill does **not** publish or upload the image anywhere — it only writes
`image-result.json` to the current directory.

---

## Step 0 — Parse arguments

From `$ARGUMENTS`, extract:

- **narration-file** — first `.json` argument, or default to `narration.json` in the cwd.
- **--model `<id>`** — FAL model ID to use. Default: `fal-ai/flux/dev`.
- **--prompt `<text>`** — inline prompt string. Skips loading a narration file entirely.
- **--out `<file>`** — output path. Default: `image-result.json` in the cwd.

---

## Step 1 — Load the prompt

**If `--prompt` was given**, use it directly as the prompt. Set `criteria` to `[]`,
`period` and `theme_id` to `null`.

**Otherwise**, read the narration file. If it does not exist, stop:

```
ERROR: narration.json not found. Run /agentlink-director:gen-prompt-seed first,
or provide a path or --prompt.
```

Expected shape:

```json
{
  "period": "2026-06",
  "theme_id": "2026-06-cyanotype-pantry_staples",
  "prompt_seed": "A cyanotype photogram of pantry staples...",
  "rationale": "...",
  "criteria": [
    { "id": "medium_fidelity", "description": "...", "weight": 0.35 },
    { "id": "annotation_present", "description": "...", "weight": 0.20 }
  ]
}
```

Extract `prompt_seed` as the generation prompt, and keep `period`, `theme_id`,
and `criteria` for the output record.

---

## Step 2 — Generate the image

Call `mcp__fal-ai__run_model` with:

```json
{
  "model_id": "<model>",
  "arguments": {
    "prompt": "<prompt_seed>",
    "image_size": "landscape_4_3",
    "num_inference_steps": 28,
    "num_images": 1
  }
}
```

**If the response contains a `request_id`** (async job), the model queued the job
instead of returning immediately. Move to Step 2a.

**If the response contains `images[0].url`**, the job completed synchronously.
Skip to Step 3.

### Step 2a — Poll the async job

Call `mcp__fal-ai__check_job_status` with `{ "request_id": "<id>" }` and repeat
until `status` is `"COMPLETED"` or `"FAILED"`. Wait a few seconds between polls
— do not hammer the endpoint.

On `"FAILED"`, stop:

```
ERROR: FAL job <request_id> failed.
Details: <error from status response>
```

On `"COMPLETED"`, extract `images[0].url` from the result and continue to Step 3.

---

## Step 3 — Write image-result.json

Write to the output path:

```json
{
  "period": "<period or null>",
  "theme_id": "<theme_id or null>",
  "model": "<model-id used>",
  "prompt": "<prompt_seed used>",
  "image_url": "<url>",
  "criteria": [
    { "id": "medium_fidelity", "description": "...", "weight": 0.35 }
  ]
}
```

---

## Step 4 — Report

Print to stdout:

```
Image generated for <theme_id or "standalone prompt">

  model    : <model-id>
  image_url: <url>
  out      : <output file path>

Evaluation criteria (review manually against the image):
  [0.35] medium_fidelity     — Image reads as a true cyanotype: monochrome Prussian blue, soft halated edges, no shading.
  [0.20] annotation_present  — Handwritten ink annotations naming items are visible and legible.
  ...
  Total weight: 1.00
```

If `criteria` is empty (standalone `--prompt` run), omit the criteria block.

---

## Model reference

| Model ID | Characteristic |
|---|---|
| `fal-ai/flux/dev` | Default. High quality, artistic range, ~10 s |
| `fal-ai/flux/schnell` | Faster, slightly lower fidelity, ~3 s |
| `fal-ai/flux-pro` | Best quality, slower, higher cost |
| `fal-ai/recraft-v3` | Strong artistic style control; good for craft/print aesthetics |

If the brief involves a specific physical medium (cyanotype, risograph, lino-cut),
`fal-ai/recraft-v3` is often a better fit than FLUX. To try a different model
without editing the narration file, pass `--model fal-ai/recraft-v3` at invocation.

---

## Prerequisites

The FAL.ai MCP server is bundled with this plugin (`.mcp.json`). It requires
`FAL_KEY` to be set in the environment:

```bash
export FAL_KEY=your_key_here   # from fal.ai/dashboard/keys
```

If the MCP tools are unavailable, confirm the key is exported and reload plugins
with `/reload-plugins`.
