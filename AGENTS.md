# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A collection of plugins for the AgentLink platform, each compatible with Claude Code and Hermes Agent. Plugins live under `plugins/` — each is a directory containing a `.claude-plugin/plugin.json` manifest, a `skills/` subdirectory of LLM skill definitions, and optionally an `agents/` subdirectory of agent definitions.

The top-level `.claude-plugin/marketplace.json` is the Claude Code marketplace manifest that lists all available plugins.

## Repo structure

```
plugins/
  agentlink-botcha-ai/     # Botcha.ai auth and identity skills
  agentlink-artist/        # AI image generation via FAL.ai
  agentlink-director/      # Creative brief and poll pipeline
.claude-plugin/
  marketplace.json         # Marketplace manifest listing all plugins
tests/
  claude-code/             # Claude Code integration tests
  hermes/                  # Hermes Agent integration tests
```

## Adding a new plugin

Create a directory under `plugins/` with a `.claude-plugin/plugin.json` manifest, then register it in the top-level `.claude-plugin/marketplace.json`:

```json
{
  "name": "plugin-name",
  "source": "./plugins/plugin-name/"
}
```

## Adding a skill to an existing plugin

Create a directory `plugins/<plugin-name>/skills/<skill-name>/` containing a `SKILL.md`. No changes to the top-level manifest are needed — the plugin already declares its source directory.

## SKILL.md structure

The frontmatter fields that matter:

| Field                      | Purpose                                                        |
| -------------------------- | -------------------------------------------------------------- |
| `name`                     | Must match the directory name                                  |
| `allowed-tools`            | Whitelist of tools the skill may call, e.g. `Bash(python3 *)`  |
| `arguments`                | Positional args the skill accepts — used by Hermes for routing |
| `metadata.hermes.category` | Used for discovery/filtering in Hermes                         |

Reference scripts in the body as `${CLAUDE_SKILL_DIR}/scripts/<script>.py` — the runtime resolves this to the skill's directory at invocation time.

## Script conventions

All scripts in `scripts/` follow the same contract:

- Output exactly one JSON object to stdout. Never print progress lines or partial output.
- Always include `"success": bool` in every output path (success and failure).
- Include `"strategy_notes"` on failure — this is the primary debugging signal.
- Include `"raw_response"` on API failure so the calling agent can inspect the server reply.
- Dependencies: stdlib only, plus `pyyaml` and `cryptography`. No other packages.
- Use `sys.exit(0)` for handled failures (bad API response), `sys.exit(1)` only for usage errors.

---

## agentlink-botcha-ai

Five skills that provide Botcha.ai identity and trust infrastructure. They share config at `~/.config/botcha-ai/` (both files chmod 600):

- `agent.yml` — Ed25519 keypair + `agent_name` / `operator` (shared across all apps)
- `config.yml` — per-app data keyed by `app_id`:
  - `agent_id` — registered agent identifier
  - `refresh_token` — long-lived token for the fast-refresh path
  - `access_token` — cached Bearer token
  - `expires_at` — Unix timestamp of token expiry (stored so JWT decoding is never needed)
  - `token_type` — `"tap"` or `"challenge"` (how the cached token was obtained)

### botcha-ai-token auth precedence

1. **Force reset** (when `force` flag set) — clears `access_token`, `expires_at`, `token_type`, and `refresh_token`, then falls through to TAP
2. **Cached token** — returned immediately if still valid
3. **Refresh token** — `POST /v1/token/refresh` if a stored `refresh_token` exists
4. **TAP** (`botcha_tap_auth.py`) — Ed25519 nonce-sign via `POST /v1/agents/auth` → `POST /v1/agents/auth/verify`

Requires a registered agent_id in config (run `/botcha-ai-agent` first).

### botcha-ai-reputation auth

The reputation scripts (`botcha_reputation_get.py`, `botcha_reputation_events.py`) manage auth
inline — they do not call into other botcha-ai-* scripts. Precedence:

1. **Cached token** — reused if `expires_at` is more than 60 s away
2. **TAP** — inline challenge-response using the stored Ed25519 key
3. **Speed-challenge fallback** — inline solve; `agent_id` is always included in the verify payload so the event is credited to reputation

After any fresh auth the token, expiry, and type are written back to `config.yml`.

### botcha-ai-challenge

Always clears the cached token and solves a fresh challenge with `agent_id` in the verify
payload, so the event is explicitly credited to the agent's reputation. All challenge types
are handled: speed and compute are solved automatically; reasoning and hybrid questions are
answered inline by the LLM via `botcha_verify_reasoning.py`.

**Rate limit: 100 challenges per hour per IP.** Never call this skill in a loop or in
rapid succession. On a `rate_limit_exceeded` error, stop and inform the user.

### Challenge verify payloads

All scripts that call `/v1/token/verify` or `/v1/challenges/*/verify` include `"agent_id"`
in the request body so solved challenges are attributed to the registered agent for reputation.

Every API request to `api.botcha.ai` must include `?app_id=<app_id>` as a query parameter.

---

## agentlink-artist

One skill that generates images via FAL.ai. Requires the `FAL_KEY` environment variable.
The plugin bundles its own `.mcp.json` pointing at the FAL.ai MCP server —
the FAL MCP tools are only available when this plugin is loaded.

### generate-image

Reads a `narration.json` produced by `/agentlink-director:gen-prompt-seed` (or an inline
`--prompt`) and calls the FAL.ai MCP server to generate an image. Supports both synchronous
and async FAL jobs (polls until complete). Writes `image-result.json` locally — it does not
publish or upload the image anywhere.

Model override via `--model <fal-model-id>`. Default: `fal-ai/flux/dev`.

---

## agentlink-director

Three skills and two agents that drive the monthly creative brief pipeline for AgentLink.
Skills are deterministic (no MCP, no network); agents own the network boundary.

### Skills

**roll-slots** — Reads `slots.yaml` from the skill directory, applies constraint-satisfaction
rules (no recent repeats, tactile anchor), and writes `rolled-slots.json`. No LLM narration,
no MCP calls. Safe to run at any time.

**gen-prompt-seed** — Reads `rolled-slots.json` (or a provided path) and optional history,
then generates a `prompt_seed`, `rationale`, and evaluation `criteria` as Art Director.
Writes `narration.json`. No MCP calls, no publishing.

**prepare-poll** — Purely deterministic: given raw `list_polls`/`list_briefs` JSON and
`slots.yaml`, decides which slot to poll next, applies the recency exclusion window, and
builds the `create_poll_args`. Writes `poll-plan.json`. No MCP calls, no randomness.

### Agents

**create-brief** — Orchestrates the full monthly brief pipeline end-to-end: fetches brief
history from AgentLink MCP, runs `/roll-slots` and `/gen-prompt-seed`, then publishes the
brief. Requires `brief.admin` role.

**create-poll** — Creates a single poll for one brief slot (rotating subject → medium →
process → mood). Fetches polls + brief history via curl, delegates the slot/candidate
decision to `/prepare-poll`, then publishes the poll. Requires `poll.admin` role.
