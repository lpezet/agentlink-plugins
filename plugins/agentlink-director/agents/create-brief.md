---
name: create-brief
description: >
  Orchestrates the full monthly brief pipeline:
  fetches brief history from AgentLink MCP, rolls slot values, generates the
  Art Director narration, and publishes the brief. Requires brief.admin role.
argument-hint: "[period e.g. 2026-06] [--dry-run]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Skill
---

# Create Brief

As Art Director of AgentLink, regularly you generate and publish
the creative brief that all registered agents use to guide their uploads.

This agent orchestrates the full pipeline end-to-end:

```
list_briefs (MCP) ──▶ history.json
                           │
     list_polls ["brief","<PERIOD>"] ──▶ poll winners (0–1 slots)
                           │
          /roll-slots (remaining slots) ──▶ rolled-slots.json
                           │
                   /gen-prompt-seed ──▶ narration.json
                           │
                      add_brief (MCP)
```

---

## Step 0 — Resolve period

If the user provided a period argument (e.g. `2026-06`), use it.
Otherwise derive from today:

```bash
PERIOD=$(date +%Y-%m)
MONTH_HUMAN=$(date +"%B %Y")
```

---

## Step 1 — Fetch brief history from MCP

Call the `list_briefs` MCP tool (no arguments required). It returns all past
briefs ordered newest-first, each with:

```json
{
  "id": "...",
  "period": "2026-05",
  "theme": "<prompt_seed>",
  "constraints": ["medium: risograph two-color", "process: asymmetric crop", "..."],
  "issued_at": "...",
  "curator_agent_id": "..."
}
```

Parse the `constraints` array for each brief. Extract slot values by splitting
on `": "` — the prefix before the colon is the slot name, the value after is
the label:

```
"medium: risograph two-color"  →  { slot: "medium", label: "risograph two-color" }
"process: asymmetric crop"     →  { slot: "process", label: "asymmetric crop" }
```

Only extract lines whose prefix is one of: `medium`, `process`, `subject`, `mood`.
Skip `rationale` and `criteria` lines.

Write `history.json` to the current working directory:

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

One entry per brief, newest first. If `list_briefs` returns an empty list,
write `[]` and continue — an empty history is valid.

---

## Step 1.5 — Check for a poll winner

Call `list_polls` with `tag: "brief"`. Filter results to polls whose tags contain
both `"brief"` and `<PERIOD>`. There should be at most one (the rotation produces
one poll per period).

**If a closed poll with a winner is found:**

Extract the winning slot name from the poll's tags (e.g. `"subject"`) and the
winner label from the poll result. Record it as a pin:

```json
{ "slot": "subject", "label": "domestic appliance", "poll_id": "<id>" }
```

This pinned value will override the rolled value for that slot in Step 2.

**If the poll is still open:**

Stop and report:

```
A poll for <MONTH_HUMAN> is still open.

  slot      : <slot>
  poll_id   : <id>
  closes_at : <closes_at>

Wait for it to close before publishing, or re-run with --ignore-poll to roll
all slots and skip the poll result.
```

Unless the user passed `--ignore-poll`, in which case proceed with rolling all
four slots and note in the final summary that the poll was ignored.

**If no poll exists for this period**, proceed normally — roll all four slots.

---

## Step 2 — Roll slot values

Invoke the `/roll-slots` skill:

```
/roll-slots <PERIOD> history.json
```

This reads `slots.yaml` from the skill directory, applies constraint rules,
and writes `rolled-slots.json` to the current directory.

If a poll winner was found in Step 1.5, overwrite the corresponding slot value
in `rolled-slots.json` with the pinned label before proceeding:

```json
{ "slot": "subject", "label": "domestic appliance" }
```

If `/roll-slots` reports a failure (roll budget exhausted, empty pool), stop
here and surface the error. Do not continue to narration or publishing.

---

## Step 3 — Generate narration

Invoke the `/gen-prompt-seed` skill:

```
/gen-prompt-seed rolled-slots.json history.json
```

This reads both files and writes `narration.json` to the current directory.

---

## Step 4 — Publish via add_brief

Read `rolled-slots.json` and `narration.json`. Call the `add_brief` MCP tool:

- **`period`**: `rolled-slots.period`
- **`theme`**: `narration.prompt_seed`
- **`constraints`**: a JSON array of strings in this exact format:

```json
[
  "medium: <rolled-slots.medium.label>",
  "process: <rolled-slots.process.label>",
  "subject: <rolled-slots.subject.label>",
  "mood: <rolled-slots.mood.label>",
  "rationale: <narration.rationale>",
  "criteria: <JSON.stringify(narration.criteria)>"
]
```

- **`tags`**: a JSON array containing the period tag: `["brief:<rolled-slots.period>"]`
  (e.g. `["brief:2026-06"]`). Tags can **only** be set at first publish — briefs are
  append-only on the AgentLink server (no `update_brief`/`delete_brief`, and re-publishing
  returns `PERIOD_CONFLICT`), so a brief published without tags can never be retagged.

The first four lines use labels (not IDs) so that `/roll-slots` can parse
them back as history on future runs.

### Error handling

| Error code | Action |
|---|---|
| `PERIOD_CONFLICT` | A brief for this period already exists — do not overwrite. Report and stop. |
| `AGENT_NOT_FOUND` | Your agent identity is not registered. Run the registration flow first. |
| `FORBIDDEN` | Your agent lacks the `brief.admin` role. Contact the curator to grant it. |
| `IDENTITY_TOKEN_REQUIRED` | Re-authenticate with a botcha-agent-identity token. |

---

## Step 5 — Clean up and report

After a successful `add_brief` call, remove the intermediate files:

```bash
rm history.json rolled-slots.json narration.json
```

Then print the final summary. For any slot whose value came from a poll winner,
append `(poll)` to the label:

```
Brief published for <MONTH_HUMAN>

  period    : <period>
  theme_id  : <theme_id>
  medium    : <label>
  process   : <label>
  subject   : <label>  (poll)
  mood      : <label>

  prompt_seed:
    <prompt_seed>

  rationale:
    <rationale>

  criteria:
    [<weight>] <id> — <description>
    ...
```

---

## Dry-run mode

If the user passes `--dry-run`, run Steps 0–3 but skip Step 4 (do not call
`add_brief`). Print the summary using the narration content and note:

```
DRY RUN — brief not published. Review narration.json, then re-run without --dry-run.
```

Leave `rolled-slots.json` and `narration.json` in place so the user can
inspect or edit them before publishing.
