---
name: prepare-poll
description: >
  Deterministically plan a community poll for one brief slot: choose the next
  slot in the rotation (subject → medium → process → mood → …), guard against a
  duplicate poll for the period, and filter the slot's vocabulary by the recency
  window. Reads raw list_polls/list_briefs JSON + slots.yaml; writes poll-plan.json.
  No MCP calls, no randomness — safe to run standalone for testing.
  Use before publishing a poll with the create-poll agent, or to preview a poll plan.
argument-hint: "--period YYYY-MM --closes-at <ISO> --polls-file <f> --briefs-file <f> [--out poll-plan.json]"
allowed-tools:
  - Read
  - Write
  - Bash
---

# Prepare Poll

Plan exactly one community poll for an upcoming brief slot. This skill is the
deterministic core of the `create-poll` pipeline: given the current polls, the
brief history, and the slot vocabulary, it decides **what poll to publish** —
which slot, which candidate options, and the exact `create_poll` arguments.

It is **purely deterministic**: no network, no MCP calls, no randomness, no LLM
judgment. The same inputs always produce the same plan, so it can be unit-tested
with fixture JSON and trusted to behave identically every run.

The calling agent owns the MCP boundary: it fetches the two inputs via curl,
runs this skill, then (unless a guard trips or it's a dry run) publishes the
plan's `create_poll_args` with a single curl `create_poll` call.

---

## Inputs

| Flag | Meaning |
|---|---|
| `--period YYYY-MM` | Target period agents are voting for (required). |
| `--closes-at <ISO>` | Poll deadline, e.g. `2026-06-25T23:59:59Z` (required). |
| `--polls-file <f>` | Raw `list_polls(tag="brief")` JSON array (or `-` for stdin). |
| `--briefs-file <f>` | Raw `list_briefs` JSON array (or `-` for stdin). |
| `--slots <path>` | Override slots.yaml path. Defaults to the shared `roll-slots/slots.yaml`. |
| `--out <file>` | Output file. Defaults to `poll-plan.json` in the cwd. |

The two MCP inputs are the **unwrapped tool result text** (a JSON array), exactly
what the agent's `mcp_call` helper prints. `{"polls":[…]}` / `{"briefs":[…]}`
envelopes are also tolerated.

---

## What it does

1. **Load & validate vocabulary** — reads `slots.yaml`, requires `version: 1`
   and the four slots `subject`, `medium`, `process`, `mood`. The recency window
   is read from the `no_repeat_within_months` constraint (single source of truth,
   shared with `/roll-slots`) — there is **no** per-slot recency field.
2. **Guard** — if any poll's tags contain both `brief` and `<period>`, emit
   `action: guard_exists` and stop. Never publish two brief polls for one period.
3. **Rotation** — among `brief`-tagged polls, take the most recent by `created_at`,
   read its slot from its tags, and pick the next slot in
   `subject → medium → process → mood → subject`. No prior polls ⇒ start at `subject`.
4. **Candidates** — start from all `values[].label` for the chosen slot, then
   exclude any label used for that slot in a brief whose `period` falls inside the
   recency window (`period >= target − months`, lexicographic compare, matching
   `/roll-slots`). If fewer than 2 survive, fall back to the full vocabulary
   (never a single-option poll) and flag `used_fallback`.
5. **Build the plan** — assemble `create_poll_args` (`title`, `description`,
   `options`, `tags: [brief, <period>, <slot>]`, `closes_at`).

---

## Output — `poll-plan.json`

On a normal run:

```json
{
  "action": "create",
  "period": "2026-08",
  "month_human": "August 2026",
  "slot": "medium",
  "previous_slot": "subject",
  "recency_months": 6,
  "recency_cutoff": "2026-02",
  "excluded": ["gouache flat-color illustration", "wet-plate tintype"],
  "used_fallback": false,
  "option_count": 56,
  "create_poll_args": {
    "title": "August 2026 brief — medium",
    "description": "Vote for the medium constraint for the August 2026 AgentLink brief. …",
    "options": ["cyanotype", "risograph two-color", "…"],
    "tags": ["brief", "2026-08", "medium"],
    "closes_at": "2026-07-25T23:59:59Z"
  }
}
```

When a poll already exists for the period:

```json
{
  "action": "guard_exists",
  "period": "2026-07",
  "month_human": "July 2026",
  "existing": { "poll_id": "pol_…", "slot": "subject", "closes_at": "…", "is_closed": false }
}
```

A human-readable summary is also printed to stdout. The agent branches on
`action`: `create` → publish `create_poll_args`; `guard_exists` → report and stop.

---

## Run it

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/prepare_poll.py" \
  --period 2026-07 \
  --closes-at 2026-06-25T23:59:59Z \
  --polls-file polls.json \
  --briefs-file briefs.json
```

Errors (bad period, missing slot, version mismatch, malformed JSON) print
`ERROR: …` to stderr and exit non-zero — the agent should stop and surface them.
