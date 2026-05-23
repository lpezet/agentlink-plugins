---
name: botcha-ai-app
description: |
  Sets up (or retrieves) a Botcha.ai application — the organizational boundary that
  binds a human operator to a set of AI agents, and owns the trust, rate limits,
  and credentials those agents operate under.

  If one or more apps are already saved in ~/.config/botcha-ai/config.yml, returns
  the existing app_id without creating anything new. When multiple apps exist, the
  app matching the app_name argument is used; otherwise the first entry is returned.

  If no app exists and app_name/email arguments are not supplied, returns
  needs_input=true so the calling agent can collect those values and re-invoke.
  When both are present, calls the Botcha.ai API, then returns needs_input=true
  again to request the email verification code from the operator. Once the code is
  supplied the app is activated and saved.

  Returns a JSON block with app_id and created (true when a new app was just made).
context: fork
allowed-tools: Bash(python3 *), Bash(curl *)
arguments:
  - app_name
  - email
arguments_hint: "[<app_name> <email>]"
version: 1.0.0
author: lpezet@gmail.com
metadata:
  hermes:
    tags: [auth, botcha.ai, setup]
    category: auth
---

## Step 0: Check for existing apps

Read `~/.config/botcha-ai/config.yml` and list any saved apps:

```bash
python3 - <<'EOF'
import json, pathlib
try:
    import yaml
    cfg = pathlib.Path.home() / ".config" / "botcha-ai" / "config.yml"
    if cfg.exists():
        data = yaml.safe_load(cfg.read_text()) or {}
        apps = data.get("apps", {})
        print(json.dumps({"success": True, "apps": list(apps.keys())}))
    else:
        print(json.dumps({"success": True, "apps": []}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
EOF
```

- **One app found** → emit the output block (Step 3) with that `app_id` and `"created": false`. Stop.
- **Multiple apps found** → if `app_name` was supplied as an argument, use the matching entry (exact match on key). If no match or no argument, use the first entry. Then go to Step 3.
- **No apps found** → proceed to Step 1.

## Step 1: Create app

Check whether the `app_name` and `email` arguments were supplied. If either is missing,
stop immediately and emit:

```json
{
  "success": false,
  "needs_input": true,
  "required": ["email", "app_name"],
  "prompt": "A Botcha.ai app is required. Please provide the operator email address and a display name for the new app (default: \"My Agent Fleet\"), then re-invoke botcha-ai-app with those arguments."
}
```

The calling agent must collect the missing values and re-invoke this skill before continuing.

Once both are available, create the app:

```bash
curl -s -X POST -H "Content-Type: application/json" \
  "https://botcha.ai/v1/apps" \
  -d '{"email": "<USER_EMAIL>", "name": "<APPNAME>"}' \
  > /tmp/botcha_ai_app.json
cat /tmp/botcha_ai_app.json
```

A verification code will be sent to `<USER_EMAIL>`. Emit the following to the calling
agent so it can relay the request to the operator and wait for the code:

```json
{
  "success": false,
  "needs_input": true,
  "required": ["verification_code"],
  "prompt": "A verification code was sent to <USER_EMAIL> (subject: \"BOTCHA: Your verification code is …\"). Please share the numeric code."
}
```

Once the calling agent supplies the `verification_code`, verify the email and activate the app:

```bash
python3 - <<'EOF'
import json, pathlib
data = json.loads(pathlib.Path("/tmp/botcha_ai_app.json").read_text())
print(json.dumps({"app_id": data.get("app_id"), "app_secret": data.get("app_secret")}))
EOF
```

Use the `app_id` and `app_secret` from that output to confirm verification:

```bash
curl -s -X POST -H "Content-Type: application/json" \
  "https://botcha.ai/v1/apps/<APP_ID>/verify-email" \
  -d '{"code": "<CODE>", "app_secret": "<APP_SECRET>"}'
```

Check the response: if it indicates success, proceed to Step 2. If it indicates failure
(e.g. wrong code, expired), emit a `needs_input` response with `"required": ["verification_code"]`
and a prompt asking the calling agent to obtain the correct code and retry.

## Step 2: Save app to configuration

Merge the new app into `~/.config/botcha-ai/config.yml` without overwriting other
entries. Use the `created_at` timestamp from the API response if present; otherwise
use the current UTC time:

```bash
python3 - <<'EOF'
import json, pathlib, os, datetime
try:
    import yaml
    cfg_dir  = pathlib.Path.home() / ".config" / "botcha-ai"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "config.yml"
    data = (yaml.safe_load(cfg_file.read_text()) if cfg_file.exists() else None) or {}
    data.setdefault("apps", {})
    data["apps"]["<APP_ID>"] = {
        "created_at": "<CREATED_AT_OR_NOW>",
        "rate_limit":  100,
    }
    cfg_file.write_text(yaml.dump(data, default_flow_style=False))
    os.chmod(cfg_file, 0o600)
    print(json.dumps({"success": True}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
EOF
```

Replace `<APP_ID>` with the actual app_id and `<CREATED_AT_OR_NOW>` with the
timestamp from the API or `datetime.datetime.utcnow().isoformat() + "Z"`.

## Step 3: Emit output

```json
{
  "success": true,
  "app_id": "...",
  "created": false
}
```

Set `"created": true` when a new app was made in Step 1–2, `false` when an existing
app was returned from Step 0.

On failure:

```json
{
  "success": false,
  "error": "<error message>",
  "strategy_notes": "<what failed and at which step>"
}
```
