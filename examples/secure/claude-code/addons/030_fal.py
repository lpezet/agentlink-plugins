"""Inject FAL.ai API key for mcp.fal.ai calls."""
import requests
from mitmproxy import http, ctx
from cachetools import TTLCache

_cache = TTLCache(maxsize=1, ttl=300)
BROKER_URL = "http://broker:8080"


def _get_key():
    if "key" not in _cache:
        r = requests.get(f"{BROKER_URL}/fal/key", timeout=5)
        r.raise_for_status()
        _cache["key"] = r.json()["key"]
    return _cache["key"]


def request(flow: http.HTTPFlow) -> None:
    if flow.request.pretty_host != "mcp.fal.ai":
        return

    flow.request.headers["Authorization"] = f"Bearer {_get_key()}"
    ctx.log.info(f"fal: {flow.request.method} {flow.request.path}")


def response(flow: http.HTTPFlow) -> None:
    if flow.request.pretty_host != "mcp.fal.ai":
        return
    if flow.response.status_code == 401:
        _cache.clear()
        ctx.log.warn("fal: 401 received, cleared key cache")
