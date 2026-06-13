#!/bin/bash
# One-time setup: trust the mitmproxy CA cert and verify the security boundary.
# Idempotent — safe to re-run if something failed mid-way.
set -euo pipefail

echo "[setup] trusting mitmproxy CA cert..."
cp /proxy-certs/mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/mitmproxy.crt
update-ca-certificates

echo "[setup] verifying network isolation (broker must be unreachable from this container)..."
if curl -s --max-time 2 http://broker:8080/healthz > /dev/null 2>&1; then
  echo "[setup] FAIL: broker is reachable — security boundary broken!"
  exit 1
fi
echo "[setup] OK: broker unreachable (expected)"

echo "[setup] done."
