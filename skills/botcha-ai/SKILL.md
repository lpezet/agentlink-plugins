---
name: botcha-ai
description: |
  Obtains a Botcha.ai JWT access token for an AI agent. Manages the full
  identity lifecycle: first-run keypair generation, TAP agent registration per
  app, fast TAP challenge-response auth on subsequent runs, and challenge-solving
  fallback (speed/reasoning/hybrid/compute) when no registered identity exists.

  Config lives in two files under ~/.config/botcha-ai/ (both chmod 600):
    agent.yml  — agent identity and Ed25519 keypair (shared across all apps)
    config.yml — per-app registrations, keyed by app_id

  Call with:
    app_id:   <Botcha.ai app ID>       [required]
    audience: <resource server URL>    [optional — scopes the token]
    force:    "force"                  [optional — clears all cached tokens and forces
                                        a full re-authentication cycle, earning a fresh
                                        verification event for reputation]

  Returns a JSON block with access_token, refresh_token, agent_id (when newly
  registered for the app), auth_method, and strategy_notes (on failure).
allowed-tools: Bash(python3 *), Bash(curl *)
arguments: [app_id, audience, force]
version: 2.0.0
author: lpezet@gmail.com
metadata:
  hermes:
    tags: [auth, botcha.ai]
    category: auth
---

Your sole job: obtain a valid `access_token` and return it as a JSON block.
Follow these steps in order. Stop as soon as you have a token.

Parameters: `$1` = app_id (required), `$2` = audience (optional), `$3` = `force` (optional).

Config dir: `~/.config/botcha-ai/`  
Agent identity: `~/.config/botcha-ai/agent.yml`  
App config: `~/.config/botcha-ai/config.yml`  
Scripts: `${CLAUDE_SKILL_DIR}/scripts/` — Hermes: replace with the path to
this skill's `scripts/` directory.

## CRITICAL RULES

1. **NEVER use curl for `/v1/token/verify`, `/v1/challenges/*/verify`, or any
   `/v1/agents/` POST.** Use the pre-built scripts for all of these. curl is
   allowed only for GET requests and `/v1/token/refresh`.
2. **Every** HTTP call to `api.botcha.ai` must include `?app_id=<app_id>`
   in the URL.
3. If you receive `APP_REGISTRATION_REQUIRED`, it means `app_id` was missing
   from that specific request — not that the app is unregistered. Retry with
   `?app_id=` present.
4. The `private_key_pem` in `agent.yml` is sensitive. Never log or emit it.

---

## Pre-flight: force reset (only when $3 == "force")

If `$3` is the literal string `force`, clear all cached tokens before doing anything
else — this bypasses both the cached-token fast path and the refresh-token path, ensuring
a full re-authentication cycle that earns a fresh verification event for reputation:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_token_clear.py $1
```

If the clear succeeds, proceed from **Step 0** as normal.  
If it fails with `app_id not found`, skip to **Step 0** anyway — there is nothing to clear.

---

## Step 0: Bootstrap agent identity and app registration

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_setup.py $1
```

**If the output contains `"missing": [...]`:** ask the user for each listed
value. When asking for `agent_name`, propose your own current agent name as the
default. When asking for `operator`, propose the user's name or organisation if
you know it from context. Then re-run with the supplied values:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_setup.py $1 --agent-name "NAME" --operator "ORG"
```

**If `"success": true, "registered": true`** → a new TAP registration was
performed. Record `agent_id` and include it in the Step 4 output block.

**If `"success": true, "registered": false`** → identity already exists.

**If `"success": false` with an `error`** → record in `strategy_notes`, fall
through to **Step 2** (challenge-solving fallback).

---

## Fast path: refresh token

Check `~/.config/botcha-ai/config.yml`. If the `$1` section contains a
non-empty `refresh_token`:

```bash
curl -s -X POST "https://api.botcha.ai/v1/token/refresh?app_id=$1" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "REFRESH_TOKEN_HERE"}'
```

If the response contains `access_token` → emit the output block (Step 4). Stop.

If the response contains an error (e.g. `INVALID_TOKEN`, `TOKEN_EXPIRED`, or any
non-success result) → clear `refresh_token` in `config.yml` (set it to `""`) and
fall through to **Step 1**. Do **not** stop or report failure here.

---

## Step 1: TAP challenge-response auth

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_tap_auth.py $1
```

Include `$2` as a second argument if the caller provided an audience:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_tap_auth.py $1 $2
```

**If `"success": true`** → go to **Step 4**. Done.  
**If `"success": false`** → fall through to **Step 2**.

---

## Step 2: Challenge-solving fallback

Use this path only when there is no registered agent identity or TAP auth failed.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_get_token.py $1
```

Include `$2` as a second argument if the caller provided an audience.

**If `"success": true`** → go to **Step 4**.  
**If `"needs_reasoning": true`** → go to **Step 3**.

---

## Step 3: Answer reasoning questions (only when needs_reasoning: true)

The script output contains a `challenge` object with a `questions` array.
You have **30 seconds** from challenge issuance. Work quickly.

For each question read the `id` and build: `{"<question_id>": "<answer>", ...}`

**By category:**

- **Analogy** (`A is to B as C is to ?`): identify the A→B relationship, apply to C.
- **Math / word problem**: extract the numbers and compute directly.
- **Logic** (if/then, ordering, set membership): trace the conditions step by step.
- **Wordplay** (anagram, rhyme, letter pattern): work through it character by character.
- **Computer science** (complexity, data structures, algorithms): apply knowledge directly.
- **Pattern completion** (number or symbol sequences): find the rule, apply it.

If you see a category not listed, best-guess the answer and record the category
name in `strategy_notes` so the instructions can be extended.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/botcha_verify_reasoning.py $1 CHALLENGE_ID TYPE '{"q-id-1":"answer1"}'
```

For hybrid challenges:

```json
{"speed_answers": [...], "reasoning_answers": {"q-id": "answer"}}
```

Go to Step 4.

---

## Step 4: Emit output

**Always emit this JSON block, even on failure.**

```json
{
  "success": true,
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 3600,
  "agent_id": "agent_... (only when newly registered this run, omit otherwise)",
  "auth_method": "tap | challenge | refresh",
  "challenge_type": "speed|reasoning|hybrid|compute (omit for tap/refresh)",
  "time_to_solve_ms": 175,
  "strategy_notes": "brief note — what worked, what was ambiguous"
}
```

On failure:

```json
{
  "success": false,
  "auth_method": "tap | challenge | refresh",
  "challenge_type": "...",
  "error": "...",
  "raw_challenge": "...",
  "raw_verify_response": "...",
  "strategy_notes": "be specific: what instruction was missing, what you tried"
}
```

The `strategy_notes` and `raw_*` fields on failure are the most valuable output —
they are the signal for improving these instructions.
