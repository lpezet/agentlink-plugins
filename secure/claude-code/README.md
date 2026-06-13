# AgentLink AI Artist — Secure Claude Code Agent

Runs Claude Code as a headless AI Artist inside a secure container stack. The agent uses the
[agentlink-artist](../../plugins/agentlink-artist/) plugin to generate images via FAL.ai.

No credentials are present in the container — the Anthropic API key and FAL.ai key are
injected at the network level by mitmproxy. Claude Code cannot exfiltrate credentials even
if it tries.

## Architecture

```
┌─────────────────────── dev network ───────────────────────┐
│                                                            │
│   ┌───────────┐   HTTPS (proxied)   ┌──────────────────┐  │
│   │    dev    │ ──────────────────► │     proxy        │  │
│   │ (Claude   │                     │  (mitmproxy)     │  │
│   │  Code)    │   http://cred-      │  030_fal.py  ──► │──┼──► mcp.fal.ai
│   │           │   gateway/...       │  020_anthropic ► │──┼──► api.anthropic.com
│   └───────────┘                     └──────┬───────────┘  │
│         │                                  │ secure net    │
│   ┌─────▼──────┐                    ┌──────▼───────────┐  │
│   │cred-gateway│                    │     broker       │  │
│   │(future use)│                    │  /anthropic/key  │  │
│   └────────────┘                    │  /fal/key        │  │
│                                     └──────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

The `broker` holds the real credentials (loaded from `.env`) and serves them only to the
`proxy` over the isolated `secure` network. The `dev` container cannot reach the broker
directly. The `cred-gateway` is present for future credential extensions (e.g. adding a
git provider later) but is not actively used.

## Prerequisites

### API keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cd secure/claude-code
cp .env.example .env
```

Edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...   # from console.anthropic.com/settings/api-keys
FAL_KEY=fal-...                # from fal.ai/dashboard/keys
```

Both keys stay in `.env` on the host and are served to the mitmproxy by the broker — they
never appear inside the agent container.

### AgentLink plugins

The agent needs the agentlink-artist plugin available at runtime. Mount the repo into the
workspace and configure the plugin path in `workspace/CLAUDE.md` (see Workspace section below).

## Quick start

Create the workspace directory and seed the bind-mounted files (Docker creates directories
instead of files if they don't exist before `up`):

```bash
cd secure/claude-code
mkdir -p workspace/.claude workspace/.config
echo '{}' > workspace/.claude.json
touch workspace/CLAUDE.md
```

Edit `workspace/CLAUDE.md` to give the agent its standing instructions as an AI Artist.
For example:

```markdown
You are an AI Artist powered by the agentlink-artist plugin.
Use /generate-image to create images from prompts.
Always write image-result.json to /workspace before reporting completion.
```

Then start the stack:

```bash
docker compose up --build -d
docker compose logs -f dev   # watch setup complete
```

On startup `dev/entrypoint.sh` runs `setup.sh`, which:
1. Trusts the mitmproxy CA cert (so Claude Code's HTTPS calls go through the proxy)
2. Verifies the broker is unreachable from the agent container (security boundary check)

## Workspace

Uncomment the workspace volume in `compose.yaml` and point it at the directory where
the agent should write its output:

```yaml
volumes:
  - /path/to/your/workspace:/workspace
```

## Commands

All commands run from `secure/claude-code/`.

**Logs:**
```bash
docker compose logs -f broker proxy cred-gateway dev
```

**Teardown** (removes volumes including the mitmproxy CA cert):
```bash
docker compose down -v
```

**Open a shell in the agent container** (for debugging):
```bash
docker compose exec dev bash
```

**Re-run setup if it failed mid-way** (idempotent):
```bash
docker compose exec dev /setup.sh
```

**Restart after rotating a credential:**
```bash
# Anthropic key: edit ANTHROPIC_API_KEY in .env, then:
docker compose restart broker proxy    # proxy caches the key for 5 min

# FAL key: edit FAL_KEY in .env, then:
docker compose restart broker proxy    # same — proxy caches FAL key for 5 min
```

**Force-regenerate the mitmproxy CA cert:**
```bash
docker compose down
docker volume rm claude-code-agent_proxy-certs
docker compose up -d
```

## Testing the security boundary

Run these from inside the dev container (`docker compose exec dev bash`):

```bash
# 1. Broker must be unreachable directly from the agent container
curl -s --max-time 2 http://broker:8080/healthz
# → curl: (6) Could not resolve host  OR  (28) Connection timed out

# 2. Proxy must block tunnelled requests to broker (000_policy.py)
curl -s -o /dev/null -w "%{http_code}" --proxy http://proxy:8080 http://broker:8080/healthz
# → 403

# 3. cred-gateway must deny raw credential endpoints
curl -s -o /dev/null -w "%{http_code}" http://cred-gateway/anthropic/key
# → 403

# 4. Anthropic API works through proxy (dummy ANTHROPIC_API_KEY is replaced)
curl -sf https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -d '{"model":"claude-haiku-4-5","max_tokens":16,"messages":[{"role":"user","content":"Say PONG"}]}' \
  | jq -r '.content[0].text'
# → PONG

# 5. Anthropic Admin API is blocked by proxy (020_anthropic.py)
curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com/v1/organizations/api_keys
# → 403

# 6. FAL MCP server is reachable through proxy (dummy FAL_KEY is replaced)
curl -sf https://mcp.fal.ai/mcp \
  -H "Authorization: Bearer $FAL_KEY" \
  -H "content-type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | jq '.result.tools[].name'
# → "run_model", "submit_job", "check_job_status", ...

# 7. Claude Code can reach the Anthropic API
claude -p "Reply with one word: PONG"
```

## Channel integration

`dev/entrypoint.sh` ends with `exec sleep infinity` as a placeholder. Replace that line
with your channel listener, e.g. a Telegram bot that sends image generation tasks to the
agent:

```bash
exec bun run /app/telegram-bot.ts
```

The listener should invoke Claude Code for each incoming task:

```bash
claude -p "$task" --allowedTools "Read,Write,mcp__fal-ai__run_model,mcp__fal-ai__submit_job,mcp__fal-ai__check_job_status" /workspace
```
