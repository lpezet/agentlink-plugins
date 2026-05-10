#!/usr/bin/env python3
"""
Clear all cached Botcha.ai tokens for an app, forcing full re-authentication on the next call.
Usage: python3 botcha_token_clear.py <app_id>

Removes access_token, expires_at, token_type, and refresh_token from config.yml
for the given app_id so neither the cached-token fast path nor the refresh path is used.
"""
import sys
import json
import pathlib

try:
    import yaml
except ImportError:
    print(json.dumps({"success": False, "error": "pyyaml not installed. Run: pip install pyyaml"}))
    sys.exit(1)

if len(sys.argv) < 2:
    print(json.dumps({"success": False, "error": "Usage: botcha_token_clear.py <app_id>"}))
    sys.exit(1)

APP_ID   = sys.argv[1]
CFG_FILE = pathlib.Path.home() / ".config" / "botcha-ai" / "config.yml"

try:
    cfg = yaml.safe_load(CFG_FILE.read_text())
    app = cfg.get("apps", {}).get(APP_ID)
    if app is None:
        print(json.dumps({"success": False, "error": f"app_id {APP_ID!r} not found in config"}))
        sys.exit(1)
    for key in ("access_token", "expires_at", "token_type", "refresh_token"):
        app.pop(key, None)
    CFG_FILE.write_text(yaml.dump(cfg, default_flow_style=False))
    print(json.dumps({"success": True}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
