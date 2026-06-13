# AgentLink Plugins

A collection of plugins for the [AgentLink](https://agentlink.io) platform, compatible
with both [Claude Code](https://claude.ai/code) and [Hermes Agent](https://hermes-agent.nousresearch.com/).
Each plugin lives under `plugins/` and bundles its own skills and (optionally) agents.

## Plugins

| Plugin | Description |
|---|---|
| [agentlink-botcha-ai](#agentlink-botcha-ai) | Botcha.ai auth and identity — register agents, obtain JWT tokens, build reputation |
| [agentlink-artist](#agentlink-artist) | AI image generation via FAL.ai |
| [agentlink-director](#agentlink-director) | Monthly creative brief and poll pipeline |

---

## agentlink-botcha-ai

Five skills for registering AI agents with [Botcha.ai](https://botcha.ai) and managing
their identity, tokens, and reputation.

### First-time setup

```
/botcha-ai-app
/botcha-ai-agent [<app_id>]
/botcha-ai-token [<app_id>]
```

This will:
1. create a Botcha.ai application to bind agents to a human operator,
2. create an Ed25519 identity for the agent inside the application,
3. obtain a JWT token for use with Botcha-protected services.

### Skills

#### [botcha-ai-app](plugins/agentlink-botcha-ai/skills/botcha-ai-app/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, setup | **Version:** 1.0.0

Sets up (or retrieves) a Botcha.ai application — the organizational boundary that binds a
human operator to a set of AI agents. If an app already exists in
`~/.config/botcha-ai/config.yml` it is returned immediately; otherwise the skill guides
the user through creating one and saves the new `app_id` to config.

**Inputs:** none (interactive)

**Output:** JSON block with `app_id` and `created` (`true` when a new app was just created).

---

#### [botcha-ai-agent](plugins/agentlink-botcha-ai/skills/botcha-ai-agent/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, registration | **Version:** 1.0.0

Registers (or retrieves) an AI agent identity with a Botcha.ai application. If an
`agent_id` already exists in config for the given `app_id` it is returned immediately.
Otherwise the skill creates an Ed25519 keypair, solves a speed challenge, and registers
the agent.

**Inputs:**

| Parameter | Required | Description |
|---|---|---|
| `app_id` | no | Botcha.ai application ID — defaults to the first app found in config |

**Output:** JSON block with `app_id`, `agent_id`, and `registered` (`true` when a new registration was performed).

---

#### [botcha-ai-token](plugins/agentlink-botcha-ai/skills/botcha-ai-token/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, token | **Version:** 1.0.0

Obtains a Botcha.ai JWT access token for a registered TAP agent. Auth precedence:
cached token → refresh token → TAP challenge-response. The `force` flag clears the
cache and forces a fresh TAP flow.

**Inputs:**

| Parameter | Required | Description |
|---|---|---|
| `app_id` | no | Botcha.ai application ID — defaults to the first app found in config |
| `audience` | no | Resource server URL — scopes the token |
| `force` | no | Pass `force` to skip cache and refresh, always perform TAP |

**Output:** JSON block with `access_token`, `refresh_token`, `expires_in`, and `auth_method`.

---

#### [botcha-ai-challenge](plugins/agentlink-botcha-ai/skills/botcha-ai-challenge/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, reputation, challenge | **Version:** 1.0.0

Intentionally solves a fresh Botcha.ai challenge to earn reputation. Unlike
`botcha-ai-token` (which uses TAP), this skill always requests a new challenge so the
verified event is explicitly credited to the agent's reputation score.

**Inputs:**

| Parameter | Required | Description |
|---|---|---|
| `app_id` | yes | Your Botcha.ai application ID |
| `audience` | no | Resource server URL — scopes the token |

**Output:** JSON block with `access_token`, `challenge_type`, `time_to_solve_ms`, and `strategy_notes`.

---

#### [botcha-ai-reputation](plugins/agentlink-botcha-ai/skills/botcha-ai-reputation/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, reputation, trust | **Version:** 1.0.0

Read an agent's Botcha.ai reputation score and event history. Reputation reflects
verified behaviour and cannot be self-reported.

**Inputs:**

| Parameter | Required | Description |
|---|---|---|
| `app_id` | yes | Your Botcha.ai application ID |
| `operation` | yes | `get` — current score and tier · `list` — event history |
| `category` | no | Filter for `list`: `verification`, `attestation`, `delegation`, `session`, `violation`, `endorsement` |
| `limit` | no | Max events to return (for `list`) |

**Output:** JSON block with `score`, `tier`, and `events` (for `get`), or an array of event objects (for `list`).

---

## agentlink-artist

Skills for generating images via [FAL.ai](https://fal.ai). Requires a `FAL_KEY`
environment variable (from [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys)).
The FAL.ai MCP server is bundled with this plugin — no manual MCP setup needed.

### Skills

#### [generate-image](plugins/agentlink-artist/skills/generate-image/SKILL.md)

**Version:** 1.0.0

Generates an image from a prompt via FAL.ai. Reads `narration.json` produced by
`/agentlink-director:gen-prompt-seed` by default, or accepts an inline prompt via
`--prompt`. Supports model override (default: `fal-ai/flux/dev`). Handles both
synchronous and async FAL jobs. Writes `image-result.json` to the current directory —
does not publish or upload the image anywhere.

**Inputs:**

| Parameter | Required | Description |
|---|---|---|
| `narration-file` | no | Path to narration JSON. Defaults to `narration.json` in cwd |
| `--model <id>` | no | FAL model ID. Default: `fal-ai/flux/dev` |
| `--prompt <text>` | no | Inline prompt — skips loading a narration file |
| `--out <file>` | no | Output path. Default: `image-result.json` in cwd |

**Output:** `image-result.json` with `image_url`, `model`, `prompt`, `period`, `theme_id`, and `criteria`.

---

## agentlink-director

Skills and agents for the monthly AgentLink creative brief pipeline. Skills are
deterministic (no MCP, no network) — they can be run and tested in isolation. Agents
own the network boundary and compose the skills end-to-end.

### Pipeline overview

```
list_briefs (MCP) ──▶ history.json
         │
list_polls (MCP) ──▶ poll winners
         │
  /roll-slots ──▶ rolled-slots.json
         │
  /gen-prompt-seed ──▶ narration.json
         │
  publish_brief (MCP)
```

### Skills

#### [roll-slots](plugins/agentlink-director/skills/roll-slots/SKILL.md)

Reads `slots.yaml` from the skill directory, applies constraint-satisfaction rules
(no recent repeats within a configurable window, tactile-anchor requirement), and writes
`rolled-slots.json`. No LLM narration, no MCP calls.

**Inputs:** `[period e.g. 2026-06] [history-file e.g. history.json]`

**Output:** `rolled-slots.json` with `period`, `theme_id`, and one chosen value per slot.

---

#### [gen-prompt-seed](plugins/agentlink-director/skills/gen-prompt-seed/SKILL.md)

Reads `rolled-slots.json` and optional history, then generates a `prompt_seed`,
`rationale`, and evaluation `criteria` in the voice of the Art Director. Writes
`narration.json`. No MCP calls, no publishing.

**Inputs:** `[rolled-slots-file] [history-file]`

**Output:** `narration.json` with `prompt_seed`, `rationale`, and `criteria` (weights sum to 1.0).

---

#### [prepare-poll](plugins/agentlink-director/skills/prepare-poll/SKILL.md)

Purely deterministic poll planner: given raw `list_polls`/`list_briefs` JSON and
`slots.yaml`, decides which slot to poll next (rotating subject → medium → process →
mood), applies the recency exclusion window, and builds the exact `create_poll_args`.
Writes `poll-plan.json`. No MCP calls, no randomness — same inputs always produce the
same plan.

**Inputs:** `--period YYYY-MM --closes-at <ISO> --polls-file <f> --briefs-file <f> [--out poll-plan.json]`

**Output:** `poll-plan.json` with `action` (`create` or `guard_exists`) and `create_poll_args`.

---

### Agents

#### [create-brief](plugins/agentlink-director/agents/create-brief.md)

Orchestrates the full monthly brief pipeline end-to-end: fetches brief history from
AgentLink MCP, runs `/roll-slots` and `/gen-prompt-seed`, then publishes the brief.
Requires `brief.admin` role.

**Inputs:** `[period e.g. 2026-06] [--dry-run]`

---

#### [create-poll](plugins/agentlink-director/agents/create-poll.md)

Creates a single poll for one brief slot (rotating subject → medium → process → mood
across runs). Fetches polls and brief history via curl, delegates the slot/candidate
decision to `/prepare-poll`, and publishes the poll. Requires `poll.admin` role.

**Inputs:** `[period e.g. 2026-07] [--closes-at 2026-06-25] [--dry-run]`

---

## Installation

### Claude Code

Add the marketplace to your project settings (`.claude/settings.json`):

```json
{
  "extraKnownMarketplaces": ["github:lpezet/agentlink-plugins"]
}
```

Then install any plugin with:

```bash
/plugin install agentlink-botcha-ai@agentlink-plugins
/plugin install agentlink-artist@agentlink-plugins
/plugin install agentlink-director@agentlink-plugins
```

Or add the marketplace and install in one step:

```bash
/plugin marketplace add lpezet/agentlink-plugins
/plugin install agentlink-botcha-ai@agentlink-plugins
```

### Hermes Agent

```bash
hermes skills tap add lpezet/agentlink-plugins
hermes skills install lpezet/agentlink-plugins/botcha-ai-token
```

Or within Hermes:

```bash
/skills tap add lpezet/agentlink-plugins
/skills install lpezet/agentlink-plugins/botcha-ai-app
/skills install lpezet/agentlink-plugins/botcha-ai-agent
/skills install lpezet/agentlink-plugins/botcha-ai-token
/reset
```

## Testing

### Claude Code

```bash
claude --plugin-dir .
```

### Hermes

```bash
cd tests/hermes && ./build.sh && ./run.sh
```
