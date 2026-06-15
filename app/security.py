"""Edge security: P2P client authentication and rate limiting.

Two concerns the public endpoints need before real traffic:

* **AuthN** -- the P2P layer authenticates to this server with an API key
  (``X-API-Key``). Keys come from ``KYC_P2P_API_KEYS`` (comma-separated) so they
  rotate without code changes. Auth fails closed: no keys configured means no
  access. (mTLS / signed requests are a stronger future option; the dependency
  boundary here stays the same.)

* **Rate limiting** -- a simple in-process fixed-window limiter on the abusable
  endpoints (onboarding, biometric submission). It is per-process and resets on
  restart; a multi-node deployment should move this to Redis or the edge. The
  point now is the seam and the 429 behavior.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict

from fastapi import Header, HTTPException, Request

# --- P2P client authentication ---------------------------------------------


def p2p_api_keys() -> set[str]:
    """Configured P2P client keys (read live so rotation/tests take effect)."""
    raw = os.environ.get("KYC_P2P_API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}


def require_p2p_client(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """FastAPI dependency: allow only requests carrying a valid P2P API key."""
    keys = p2p_api_keys()
    if not keys or x_api_key is None or x_api_key not in keys:
        raise HTTPException(status_code=401, detail="invalid_or_missing_api_key")
    return x_api_key


# --- Staff authentication ---------------------------------------------------


def admin_api_keys() -> set[str]:
    """Configured staff keys for the admin/review console (read live)."""
    raw = os.environ.get("KYC_ADMIN_API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}


def require_staff(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> str:
    """FastAPI dependency: allow only staff requests (review/audit/metrics)."""
    keys = admin_api_keys()
    if not keys or x_admin_key is None or x_admin_key not in keys:
        raise HTTPException(status_code=401, detail="invalid_or_missing_admin_key")
    return x_admin_key


# --- Rate limiting ----------------------------------------------------------

_WINDOW_SECONDS = 60
_hits: dict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()


def _rate_limit_for(name: str) -> int:
    env = {
        "onboard": "KYC_RATELIMIT_ONBOARD_PER_MIN",
        "biometric": "KYC_RATELIMIT_BIOMETRIC_PER_MIN",
    }[name]
    return int(os.environ.get(env, "120"))


def _allow(key: str, limit: int, now: float) -> bool:
    with _lock:
        bucket = _hits[key]
        cutoff = now - _WINDOW_SECONDS
        bucket[:] = [t for t in bucket if t >= cutoff]
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


def reset_rate_limits() -> None:
    """Clear all buckets (test helper)."""
    with _lock:
        _hits.clear()


def rate_limit(name: str):
    """Build a dependency that enforces the per-minute limit named ``name``."""

    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not _allow(f"{name}:{client}", _rate_limit_for(name), time.time()):
            raise HTTPException(status_code=429, detail="rate_limited")

    return dependency
