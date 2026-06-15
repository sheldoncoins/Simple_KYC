"""Shared test configuration.

Sets up an isolated SQLite database + signing key and configures auth/rate-limit
env vars *before* the app is imported, so every test module shares one
configured app instance. Rate limits are set high here so flow tests never trip
them; the dedicated rate-limit test lowers them locally.
"""
from __future__ import annotations

import base64
import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["KYC_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["KYC_SIGNING_KEY_PATH"] = f"{_tmp}/key.pem"
os.environ["KYC_P2P_API_KEYS"] = "test-p2p-key,other-key"
os.environ["KYC_RATELIMIT_ONBOARD_PER_MIN"] = "1000"
os.environ["KYC_RATELIMIT_BIOMETRIC_PER_MIN"] = "1000"
os.environ["KYC_STORAGE_DIR"] = f"{_tmp}/media"
os.environ["KYC_STORAGE_KEY"] = base64.b64encode(b"0" * 32).decode()
os.environ.setdefault("KYC_MRZ_READER", "text")
os.environ.setdefault("KYC_LOG_FORMAT", "console")

P2P_KEY = "test-p2p-key"

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

init_db()


@pytest.fixture(scope="session")
def api_key() -> str:
    return P2P_KEY


@pytest.fixture
def client() -> TestClient:
    """Client that authenticates as a P2P partner on every request."""
    return TestClient(app, headers={"X-API-Key": P2P_KEY})


@pytest.fixture
def anon_client() -> TestClient:
    """Client with no API key -- for exercising auth rejection."""
    return TestClient(app)
