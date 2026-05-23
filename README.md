# AgentLink Skills

A collection of skills compatible with both [Claude Code](https://claude.ai/code)
and [Hermes Agent](https://hermes-agent.nousresearch.com/). Each skill lives in
its own directory under `skills/` and is defined by a `SKILL.md` file loaded at
runtime.

## Usage

For the very first time, the typical flow is:

```
/botcha-ai-app
/botcha-ai-agent [<app_id>]
/botcha-ai-token [<app_id>]
```

This will:

1. create an application in Botcha.ai to bind agents to a human,
2. create an identity for the agent inside the application in Botcha.ai,
3. and generate a JWT token to be used in Botcha-protected services or resources

## Installation

### Claude Code

Add the marketplace and install the skill:

```bash
/plugin marketplace add lpezet/agentlink-skills
/plugin install botcha-ai@agentlink-skills
```

Or add it once to your project settings (`.claude/settings.json`):

```json
{
  "extraKnownMarketplaces": ["github:lpezet/agentlink-skills"]
}
```

Then install any skill with `/plugin install <skill-name>@agentlink-skills`.

### Hermes Agent

From the command line:

```bash
hermes skills tap add lpezet/agentlink-skills && hermes skills install lpezet/agentlink-skills/botcha-ai-token
```

Or within Hermes:

```bash
/skills tap add lpezet/agentlink-skills
/skills install lpezet/agentlink-skills/botcha-ai-app
/skills install lpezet/agentlink-skills/botcha-ai-agent
/skills install lpezet/agentlink-skills/botcha-ai-token
/reset
```

## Skills

### [botcha-ai-app](skills/botcha-ai-app/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, setup | **Version:** 1.0.0

Sets up (or retrieves) a Botcha.ai application — the organizational boundary that binds a
human operator to a set of AI agents, owning their trust level, rate limits, and credentials.
If an app already exists in `~/.config/botcha-ai/config.yml` it is returned immediately;
otherwise the skill guides the user through creating one (email + display name, email
verification code) and saves the new `app_id` to config.

**Inputs:** none (interactive)

**Output:** JSON block with `app_id` and `created` (`true` when a new app was just created).

---

### [botcha-ai-agent](skills/botcha-ai-agent/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, registration | **Version:** 1.0.0

Registers (or retrieves) an AI agent identity with a Botcha.ai application. If an
`agent_id` already exists in config for the given `app_id`, it is returned immediately
without any API calls. Otherwise the skill creates an Ed25519 keypair, solves a speed
challenge, registers the agent identity, registers the TAP keypair, and saves the new
`agent_id` to `~/.config/botcha-ai/config.yml`.

**Inputs:**

| Parameter | Required | Description                                                          |
| --------- | -------- | -------------------------------------------------------------------- |
| `app_id`  | no       | Botcha.ai application ID — defaults to the first app found in config |

**Output:** JSON block with `app_id`, `agent_id`, and `registered` (`true` when a new
registration was performed).

---

### [botcha-ai-token](skills/botcha-ai-token/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, token | **Version:** 1.0.0

Obtains a Botcha.ai JWT access token for a registered TAP agent. Auth precedence: cached
token → refresh token → TAP challenge-response (Ed25519 nonce-sign). The `force` flag
clears the cache and forces a fresh TAP flow. Requires a registered agent for the given
`app_id` (run `/botcha-ai-agent` first).

**Inputs:**

| Parameter  | Required | Description                                                          |
| ---------- | -------- | -------------------------------------------------------------------- |
| `app_id`   | no       | Botcha.ai application ID — defaults to the first app found in config |
| `audience` | no       | Resource server URL — scopes the token                               |
| `force`    | no       | Pass `force` to skip cache and refresh, always perform TAP           |

**Output:** JSON block with `access_token`, `refresh_token`, `expires_in`, and `auth_method`
(`cached`, `refresh`, or `tap`).

---

### [botcha-ai-challenge](skills/botcha-ai-challenge/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, reputation, challenge | **Version:** 1.0.0

Intentionally solve a fresh Botcha.ai challenge to earn reputation. Unlike `botcha-ai-token`
(which uses TAP), this skill always clears the cached token and requests a new challenge,
ensuring the verified event is credited to the registered agent's reputation score. All
challenge types are handled: speed and compute are solved automatically; reasoning and hybrid
questions are answered inline by the LLM.

**Inputs:**

| Parameter  | Required | Description                            |
| ---------- | -------- | -------------------------------------- |
| `app_id`   | yes      | Your Botcha.ai application ID          |
| `audience` | no       | Resource server URL — scopes the token |

**Output:** JSON block with `access_token`, `challenge_type`, `time_to_solve_ms`, and `strategy_notes`.

---

### [botcha-ai-reputation](skills/botcha-ai-reputation/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, reputation, trust | **Version:** 1.0.0

Read a [Botcha.ai](https://botcha.ai) agent's reputation score and event history.
Reputation reflects verified behaviour — it cannot be self-reported. The primary way
to build score today is through the `botcha-ai-token` and `botcha-ai-challenge` skills
(each successful verification contributes a `verification/challenge_solved` event).
The Botcha.ai whitepaper describes a planned reputation marketplace where agents will
earn reputation across partner networks.

**Inputs:**

| Parameter   | Required | Description                                                                                           |
| ----------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `app_id`    | yes      | Your Botcha.ai application ID                                                                         |
| `operation` | yes      | `get` — current score and tier · `list` — event history                                               |
| `category`  | no       | Filter for `list`: `verification`, `attestation`, `delegation`, `session`, `violation`, `endorsement` |
| `limit`     | no       | Max events to return (for `list`)                                                                     |

**Output:** JSON block with `score`, `tier`, and `events` (for `get`), or an array of
event objects (for `list`).

# Testing skills

## Claude

```bash
claude --plugin-dir .
```
