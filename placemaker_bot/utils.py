import time
from typing import Optional

import requests

from .config import settings


def discover_external_base_url(max_wait_seconds: int = 60) -> str:
    """
    Attempt to discover the public HTTPS URL exposed by the ngrok sidecar.

    The helper polls the configured ngrok admin API until a secure tunnel is
    reported, falling back to environment-provided defaults when discovery
    fails. Using ``time.monotonic`` ensures the loop is safe to invoke from
    both synchronous and asynchronous code paths without requiring access to
    the running event loop.

    Args:
        max_wait_seconds: Maximum number of seconds to wait for tunnel discovery.

    Returns:
        A base URL suitable for webhook registration and deep link generation.
    """
    api_url = f"{settings.ngrok_api_base}/api/tunnels"
    deadline = time.monotonic() + max_wait_seconds

    while time.monotonic() < deadline:
        try:
            resp = requests.get(api_url, timeout=3)
            if resp.ok:
                public_url = _extract_https_url(resp.json())
                if public_url:
                    return public_url
        except Exception:
            # Ignore transient request failures and retry until the deadline.
            pass
        time.sleep(1)

    if settings.webapp_domain and settings.webapp_domain not in {"localhost", "127.0.0.1"}:
        return f"https://{settings.webapp_domain}"
    return f"http://localhost:{settings.webapp_port}"


def _extract_https_url(payload: dict[str, object]) -> Optional[str]:
    """
    Pull the first HTTPS tunnel URL out of an ngrok `/api/tunnels` response.

    Args:
        payload: Parsed JSON payload from the ngrok API.

    Returns:
        The HTTPS public URL if present, otherwise ``None``.
    """
    tunnels = payload.get("tunnels", [])
    if isinstance(tunnels, list):
        for entry in tunnels:
            if not isinstance(entry, dict):
                continue
            proto = entry.get("proto")
            public_url = entry.get("public_url")
            if proto == "https" and isinstance(public_url, str) and public_url.startswith("https://"):
                return public_url
    return None