#!/usr/bin/env python3
"""
Bootstrap Botcha.ai agent identity and per-app registration.
Usage: python3 botcha_setup.py <app_id> [--agent-name NAME] [--operator ORG]

Steps:
  1. Load or create ~/.config/botcha-ai/agent.yaml (keypair + identity).
  2. Load or create the app_id section in ~/.config/botcha-ai/config.yaml,
     registering the agent with Botcha.ai TAP if the section is absent.

Output JSON fields:
  success     bool
  agent_id    str   — the agent's ID for this app
  registered  bool  — true if a new TAP registration was performed this run
  missing     list  — when agent_name/operator are needed; re-run with flags
  error       str   — on failure
  raw_response obj  — on registration failure
"""
import sys
import json
import argparse
import pathlib
import os
import http.client
import ssl

try:
    import yaml
except ImportError:
    print(json.dumps({"success": False, "error": "pyyaml not installed. Run: pip install pyyaml"}))
    sys.exit(1)

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption,
    )
except ImportError:
    print(json.dumps({"success": False, "error": "cryptography not installed. Run: pip install cryptography"}))
    sys.exit(1)

parser = argparse.ArgumentParser()
parser.add_argument("app_id")
parser.add_argument("--agent-name", dest="agent_name", default=None)
parser.add_argument("--operator", dest="operator", default=None)
args = parser.parse_args()

CFG_DIR    = pathlib.Path.home() / ".config" / "botcha-ai"
AGENT_FILE = CFG_DIR / "agent.yaml"
CFG_FILE   = CFG_DIR / "config.yaml"

# ── Step 1: agent.yaml ────────────────────────────────────────────────────────

agent_data = yaml.safe_load(AGENT_FILE.read_text()) if AGENT_FILE.exists() else {}
if not agent_data:
    agent_data = {}

if args.agent_name:
    agent_data["agent_name"] = args.agent_name
if args.operator:
    agent_data["operator"] = args.operator

missing = [f for f in ("agent_name", "operator") if not agent_data.get(f)]
if missing:
    print(json.dumps({
        "success": False,
        "missing": missing,
        "hint": "Re-run with: --agent-name NAME --operator ORG",
    }))
    sys.exit(0)

agent_data.setdefault("capabilities", ["token:obtain"])
agent_data.setdefault("trust_level", "verified")

if not agent_data.get("private_key_pem"):
    priv = Ed25519PrivateKey.generate()
    pub  = priv.public_key()
    agent_data["public_key_pem"]  = pub.public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    agent_data["private_key_pem"] = priv.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

CFG_DIR.mkdir(parents=True, exist_ok=True)
AGENT_FILE.write_text(yaml.dump(agent_data, default_flow_style=False))
os.chmod(AGENT_FILE, 0o600)

# ── Step 2: config.yaml ───────────────────────────────────────────────────────

cfg_data = yaml.safe_load(CFG_FILE.read_text()) if CFG_FILE.exists() else {}
if not cfg_data:
    cfg_data = {}
cfg_data.setdefault("apps", {})

agent_id   = cfg_data["apps"].get(args.app_id, {}).get("agent_id")
registered = False

if not agent_id:
    payload = json.dumps({
        "name":                agent_data["agent_name"],
        "operator":            agent_data["operator"],
        "version":             "1.0.0",
        "public_key":          agent_data["public_key_pem"],
        "signature_algorithm": "ed25519",
        "capabilities":        agent_data["capabilities"],
        "trust_level":         agent_data["trust_level"],
        "app_id":              args.app_id,
    }).encode()

    ctx = ssl.create_default_context()
    c   = http.client.HTTPSConnection("api.botcha.ai", context=ctx)
    c.request("POST", f"/v1/agents/register/tap?app_id={args.app_id}", payload,
              {"Content-Type": "application/json"})
    resp     = json.loads(c.getresponse().read().decode())
    agent_id = resp.get("agent_id") or resp.get("id")
    c.close()

    if not agent_id:
        print(json.dumps({
            "success": False,
            "error": "registration_failed",
            "raw_response": resp,
        }))
        sys.exit(0)

    cfg_data["apps"][args.app_id] = {
        "agent_id":      agent_id,
        "app_secret":    "",
        "refresh_token": "",
    }
    CFG_FILE.write_text(yaml.dump(cfg_data, default_flow_style=False))
    os.chmod(CFG_FILE, 0o600)
    registered = True

print(json.dumps({"success": True, "agent_id": agent_id, "registered": registered}))
