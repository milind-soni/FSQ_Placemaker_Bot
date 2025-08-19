import asyncio
import requests
from .config import settings


def discover_external_base_url(max_wait_seconds: int = 60) -> str:
    """Try to discover the public HTTPS URL from the ngrok API. Fallbacks to WEBAPP_DOMAIN if discovery fails."""
    api_url = f"{settings.ngrok_api_base}/api/tunnels"
    deadline = asyncio.get_event_loop().time() + max_wait_seconds
    while True:
        try:
            resp = requests.get(api_url, timeout=3)
            if resp.ok:
                data = resp.json()
                tunnels = data.get("tunnels", [])
                for t in tunnels:
                    public_url = t.get("public_url", "")
                    proto = t.get("proto", "")
                    if proto == "https" and public_url.startswith("https://"):
                        return public_url
        except Exception:
            pass
        if asyncio.get_event_loop().time() >= deadline:
            break
        try:
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))
        except RuntimeError:
            import time
            time.sleep(1)
    if settings.webapp_domain and settings.webapp_domain not in ("localhost", "127.0.0.1"):
        return f"https://{settings.webapp_domain}"
    return f"http://localhost:{settings.webapp_port}" 