#!/usr/bin/env python3
"""
Authenticate a registered TAP agent via Ed25519 keypair challenge-response.
Usage: python3 botcha_tap_auth.py <app_id> [audience]

Reads identity from ~/.config/botcha-ai/agent.yaml and
                   ~/.config/botcha-ai/config.yaml.
Persists the returned refresh_token back into config.yaml.

Output JSON fields: same envelope as botcha_get_token.py
  success        bool
  access_token   str   (on success)
  refresh_token  str   (on success)
  expires_in     int   (on success)
  auth_method    str   "tap"
  error          str   (on failure)
  raw_response   obj   (on failure)
  strategy_notes str
"""
import sys
import json
import pathlib
import http.client
import ssl
import base64
import os

try:
    import yaml
except ImportError:
    print(json.dumps({"success": False, "error": "pyyaml not installed. Run: pip install pyyaml"}))
    sys.exit(1)

try:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
except ImportError:
    print(json.dumps({"success": False, "error": "cryptography not installed. Run: pip install cryptography"}))
    sys.exit(1)

if len(sys.argv) < 2:
    print(json.dumps({
        "success": False,
        "error": "missing_arg",
        "strategy_notes": "Usage: python3 botcha_tap_auth.py <app_id> [audience]",
    }))
    sys.exit(1)

APP_ID   = sys.argv[1]
AUDIENCE = sys.argv[2] if len(sys.argv) > 2 else None

CFG_DIR    = pathlib.Path.home() / ".config" / "botcha-ai"
AGENT_FILE = CFG_DIR / "agent.yaml"
CFG_FILE   = CFG_DIR / "config.yaml"

try:
    agent_data = yaml.safe_load(AGENT_FILE.read_text())
    cfg_data   = yaml.safe_load(CFG_FILE.read_text())
    agent_id   = cfg_data["apps"][APP_ID]["agent_id"]
    priv       = load_pem_private_key(agent_data["private_key_pem"].encode(), password=None)
except Exception as e:
    print(json.dumps({
        "success": False,
        "error": f"config_load_failed: {e}",
        "strategy_notes": "Run botcha_setup.py first.",
    }))
    sys.exit(1)

ctx = ssl.create_default_context()

try:
    # 1. Request nonce
    c = http.client.HTTPSConnection("api.botcha.ai", context=ctx)
    c.request(
        "POST", f"/v1/agents/auth?app_id={APP_ID}",
        json.dumps({"agent_id": agent_id, "app_id": APP_ID}).encode(),
        {"Content-Type": "application/json"},
    )
    nonce_resp   = json.loads(c.getresponse().read().decode())
    challenge_id = nonce_resp.get("challenge_id")
    nonce        = nonce_resp.get("nonce")
    c.close()

    if not challenge_id or not nonce:
        print(json.dumps({
            "success": False,
            "error": "nonce_request_failed",
            "raw_response": nonce_resp,
            "strategy_notes": "TAP auth nonce request failed. Check agent_id and app_id.",
        }))
        sys.exit(0)

    # 2. Sign nonce
    sig = base64.b64encode(priv.sign(nonce.encode())).decode()

    # 3. Verify → token
    aud_param = f"&audience={AUDIENCE}" if AUDIENCE else ""
    c = http.client.HTTPSConnection("api.botcha.ai", context=ctx)
    c.request(
        "POST", f"/v1/agents/auth/verify?app_id={APP_ID}{aud_param}",
        json.dumps({"challenge_id": challenge_id,
                    "agent_id": agent_id, "signature": sig}).encode(),
        {"Content-Type": "application/json"},
    )
    token_resp    = json.loads(c.getresponse().read().decode())
    access_token  = token_resp.get("access_token")
    refresh_token = token_resp.get("refresh_token")
    c.close()

    if access_token:
        cfg_data["apps"][APP_ID]["refresh_token"] = refresh_token
        CFG_FILE.write_text(yaml.dump(cfg_data, default_flow_style=False))
        print(json.dumps({
            "success":       True,
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "expires_in":    token_resp.get("expires_in", 3600),
            "auth_method":   "tap",
            "strategy_notes": "TAP keypair challenge-response succeeded.",
        }))
    else:
        print(json.dumps({
            "success":        False,
            "error":          token_resp.get("error", "verify_failed"),
            "raw_response":   token_resp,
            "strategy_notes": "TAP verify failed. The keypair may not match the registered public key.",
        }))

except Exception as e:
    print(json.dumps({
        "success":        False,
        "error":          type(e).__name__,
        "strategy_notes": f"Unhandled exception in botcha_tap_auth.py: {e}",
    }))
