# AgentLink Skills

A collection of skills compatible with both [Claude Code](https://claude.ai/code)
and [Hermes Agent](https://hermes-agent.nousresearch.com/). Each skill lives in
its own directory under `skills/` and is defined by a `SKILL.md` file loaded at
runtime.

## Installation

### Claude Code

Add the marketplace and install the skill:

```bash
/plugin marketplace add github:lpezet/agentlink-skills
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
hermes skills tap add lpezet/agentlink-skills && hermes skills install lpezet/agentlink-skills/botcha-ai
```

Or within Hermes:

```bash
/skills tap add lpezet/agentlink-skills
/skills install lpezet/agentlink-skills/botcha-ai
/reset
```

## Skills

### [botcha-ai](skills/botcha-ai/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai | **Version:** 2.0.0

Obtains a [Botcha.ai](https://botcha.ai) JWT access token for an AI agent.
Manages the full identity lifecycle: first-run TAP registration (Ed25519 keypair
generation), fast keypair challenge-response auth on subsequent runs, and
challenge-solving fallback for unauthenticated contexts.

| Challenge | Mechanism                  | Time limit |
| --------- | -------------------------- | ---------- |
| Speed     | SHA-256 hash               | 500 ms     |
| Reasoning | Language / logic questions | 30 s       |
| Hybrid    | Speed + Reasoning combined | 35 s       |
| Compute   | Prime generation + hashing | 3–10 s     |

**Inputs:**

| Parameter  | Required | Description                                                                      |
| ---------- | -------- | -------------------------------------------------------------------------------- |
| `app_id`   | yes      | Your Botcha.ai application ID                                                    |
| `audience` | no       | Resource server URL — scopes the token                                           |
| `force`    | no       | Pass `"force"` to clear all cached tokens and force a full re-authentication cycle, earning a fresh verification event for reputation |

**Output:** JSON block with `access_token`, `refresh_token`, `auth_method`,
`agent_id` (on first registration), and `strategy_notes`.

---

### [botcha-ai-challenge](skills/botcha-ai-challenge/SKILL.md)

**Category:** auth | **Tags:** auth, botcha.ai, reputation, challenge | **Version:** 1.0.0

Intentionally solve a fresh Botcha.ai challenge to earn reputation. Unlike `botcha-ai`
(which solves challenges only as a fallback), this skill always clears the cached token
and requests a new challenge, ensuring the verified event is credited to the registered
agent's reputation score. Speed and compute challenges are solved automatically. Reasoning
and hybrid challenges are out of scope — use `botcha-ai` for those.

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
to build score today is through the `botcha-ai` and `botcha-ai-challenge` skills
(each successful verification contributes a `verification/challenge_solved` event).
The Botcha.ai whitepaper describes a planned reputation marketplace where agents will
earn reputation across partner networks.

**Inputs:**

| Parameter   | Required | Description                                                              |
| ----------- | -------- | ------------------------------------------------------------------------ |
| `app_id`    | yes      | Your Botcha.ai application ID                                            |
| `operation` | yes      | `get` — current score and tier · `list` — event history                  |
| `category`  | no       | Filter for `list`: `verification`, `attestation`, `delegation`, `session`, `violation`, `endorsement` |
| `limit`     | no       | Max events to return (for `list`)                                        |

**Output:** JSON block with `score`, `tier`, and `events` (for `get`), or an array of
event objects (for `list`).
