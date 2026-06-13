# Claude Code plugin test harness

Convenience wrapper for running Claude Code against the local plugins checkout.
Mirrors the `tests/hermes/` setup but for Claude Code's `--plugin-dir` flag.

## Prerequisites

| Requirement | Notes |
|---|---|
| `claude` CLI | Install from [claude.ai/code](https://claude.ai/code) |
| `pyyaml` + `cryptography` | `pip install pyyaml cryptography` — required by botcha-ai scripts |
| `FAL_KEY` env var | Required for the artist plugin only. Get a key at [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys) |

Run `./run.sh check` at any time to verify your environment.

## Usage

```bash
./tests/claude-code/run.sh [check|validate|marketplace|all|botcha-ai|director|artist]
```

There are two ways to load plugins — via `--plugin-dir` (fast, no install step) or
via the marketplace (tests the full install flow as an end user would see it):

### `--plugin-dir` mode (development)

Loads plugins directly from the checkout without installing them. Ideal for iterating
on skill content.

| Command | Plugins loaded | Use for |
|---|---|---|
| `check` | — | Verify prerequisites before a session |
| `validate` | — | Validate `marketplace.json` and all plugin manifests |
| `botcha-ai` | agentlink-botcha-ai | Testing registration, token, reputation, challenge |
| `director` | agentlink-botcha-ai + agentlink-director | Testing brief and poll pipeline |
| `artist` | agentlink-botcha-ai + agentlink-artist | Testing image generation (requires `FAL_KEY`) |
| `all` *(default)* | all three | Full stack |

`director` and `artist` always include `agentlink-botcha-ai` because those plugins
call botcha-ai skills for auth.

### `marketplace` mode (end-to-end)

Registers this repo as a local marketplace, then launches Claude Code. Use this to
test the full install flow — marketplace discovery, plugin listing, and installation
— exactly as an end user would experience it.

```bash
./tests/claude-code/run.sh marketplace
```

Then inside Claude Code:

```
/plugin install agentlink-botcha-ai@agentlink-skills
/plugin install agentlink-director@agentlink-skills
/plugin install agentlink-artist@agentlink-skills
```

Skills are then available under their plugin namespace:

```
/agentlink-botcha-ai:botcha-ai-token
/agentlink-director:roll-slots
/agentlink-artist:generate-image
```

To remove the marketplace when done:

```
/plugin marketplace remove agentlink-skills
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `FAL_KEY` | — | FAL.ai API key for the artist plugin |
| `CLAUDE_TEST_WORKDIR` | `~/.claude-agentlink-test` | Working directory where session artifacts land (`rolled-slots.json`, `narration.json`, etc.) |

## Typical workflows

### Test the brief pipeline

```bash
./tests/claude-code/run.sh director
```

Then inside Claude Code:

```
/agentlink-director:roll-slots
/agentlink-director:gen-prompt-seed
```

### Test the full director → artist pipeline

```bash
export FAL_KEY=your_key_here
./tests/claude-code/run.sh all
```

Then inside Claude Code:

```
/agentlink-director:roll-slots
/agentlink-director:gen-prompt-seed
/agentlink-artist:generate-image
```

### Test botcha-ai registration

```bash
./tests/claude-code/run.sh botcha-ai
```

Then inside Claude Code:

```
/agentlink-botcha-ai:botcha-ai-app
/agentlink-botcha-ai:botcha-ai-agent
/agentlink-botcha-ai:botcha-ai-token
```
