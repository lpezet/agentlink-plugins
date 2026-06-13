---
name: roll-slots
description: >
  Roll this month's creative slot values from the AgentLink vocabulary using
  constraint-satisfaction rules (no recent repeats, tactile anchor). Writes
  rolled-slots.json to the current directory. Optionally accepts a history
  file to enforce no_repeat_within_months.
  Use when asked to "roll slots", "pick a theme", or before running /gen-prompt-seed.
argument-hint: "[period e.g. 2026-06] [history-file e.g. history.json]"
allowed-tools:
  - Read
  - Write
  - Bash
---

# Roll Slots

Read the slot vocabulary from `$CLAUDE_SKILL_DIR/slots.yaml`, apply constraint
rules, and write the chosen values to `rolled-slots.json` in the current
working directory.

This skill is purely deterministic — no LLM narration, no MCP calls, no
publishing. It is safe to run at any time without affecting the server.

---

## Step 0 — Parse arguments

From `$ARGUMENTS`, extract:

- **period** — first token that matches `YYYY-MM`. If absent, derive from today:
  `PERIOD=$(date +%Y-%m)` and `MONTH_HUMAN=$(date +"%B %Y")`.
- **history-file** — first token that ends in `.json`. If absent, assume no
  history (all slot values are eligible).

---

## Step 1 — Load vocabulary

Read `$CLAUDE_SKILL_DIR/slots.yaml`. Validate:

- `version` must equal `1`. If not, stop with:
  `ERROR: slots.yaml version mismatch — expected 1, got <N>. Update the skill.`
- `slots` must contain at least the keys: `medium`, `process`, `subject`, `mood`.
- `constraints` must be a list.

Parse the full `slots` map and `constraints` list into working memory.

---

## Step 2 — Load history

If a history file was provided, read it. Expected format:

```json
[
  {
    "period": "2026-05",
    "medium": "risograph two-color",
    "process": "asymmetric crop",
    "subject": "public transit",
    "mood": "2-color palette only"
  }
]
```

Each entry's slot values are **labels** (matching the `label` field in
`slots.yaml`). Keep the list in memory as the exclusion reference.

If no history file was provided, treat history as an empty list.

---

## Step 3 — Roll with constraints

Apply the constraints from `slots.yaml` using this algorithm:

### Constraint types

| `type` | Rule |
|---|---|
| `no_repeat_within_months` | For each slot, exclude any value whose `label` appears in a history entry within the last N `months`. Compare `period` strings lexicographically (e.g. `"2026-05" >= "2025-11"` for a 6-month window). |
| `at_least_one_tag` | After all slots are drawn, check that at least one chosen value across the named `slots` carries the required `tag`. |
| `roll_budget` | Track total re-roll attempts. If the `at_least_one_tag` check keeps failing after `attempts` total rolls, stop — do not output partial results. |

### Algorithm

```
attempt = 0
budget  = <roll_budget.attempts from constraints, default 50>

loop:
  attempt += 1
  if attempt > budget: FAIL (see Step 4 — failure)

  for each slot:
    pool = all values in slot.values
           minus any value whose label is in history within no_repeat_within_months window

    if pool is empty:
      FAIL with message: "no eligible values remain for slot '<name>' — history window too wide or vocabulary too small"

    draw = pick one value from pool at random (uniform unless weights provided)
    chosen[slot.name] = draw

  for each at_least_one_tag constraint:
    tagged_slots = constraint.slots  (e.g. [medium, process])
    required_tag = constraint.tag    (e.g. "tactile")
    if none of chosen[tagged_slots] carry required_tag:
      continue loop  (re-roll)

  break  (all constraints satisfied)
```

---

## Step 4 — Handle failure

If the roll budget is exhausted, write nothing and report:

```
ROLL FAILED after <N> attempts.

Blocking constraint: <constraint.id>
  <constraint.description>

Excluded values for each slot (due to history):
  medium:  <list of excluded labels>
  process: <list of excluded labels>
  ...

Suggestions:
  - Add new values to slots.yaml for the blocked slots.
  - Reduce no_repeat_within_months from <N> to <N-1> months.
  - Provide a shorter history file that covers fewer periods.
```

Do not write `rolled-slots.json`. Stop here.

---

## Step 5 — Build theme_id and write output

Construct:

```
theme_id = <period>-<medium.id>-<subject.id>
           e.g. "2026-06-cyanotype-pantry_staples"
```

Write `rolled-slots.json` to the current working directory:

```json
{
  "period": "<PERIOD>",
  "month_human": "<MONTH_HUMAN>",
  "theme_id": "<theme_id>",
  "medium":  { "id": "<id>", "label": "<label>" },
  "process": { "id": "<id>", "label": "<label>" },
  "subject": { "id": "<id>", "label": "<label>" },
  "mood":    { "id": "<id>", "label": "<label>" }
}
```

---

## Step 6 — Report

Print a summary to stdout:

```
Rolled theme for <MONTH_HUMAN>
  theme_id : <theme_id>
  medium   : <label>
  process  : <label>
  subject  : <label>
  mood     : <label>

Roll attempts: <N> / <budget>
Written: rolled-slots.json
```
