"""Signer provider: local Ed25519 roundtrip + JWKS, and KMS backend selection."""
from __future__ import annotations

import jwt
import pytest
from app.providers import registry


def test_local_signer_jwks_and_roundtrip() -> None:
    registry.set_signer(None)  # rebuild from KYC_SIGNER (defaults to local)
    s = registry.signer()

    jwks = s.jwks()
    key = jwks["keys"][0]
    assert key["kty"] == "OKP" and key["crv"] == "Ed25519" and key["use"] == "sig"
    assert key["kid"] == s.key_id

    token = s.sign_jwt({"iss": "kyc-server", "jti": "abc", "exp": 9999999999})
    assert jwt.get_unverified_header(token)["kid"] == s.key_id
    assert s.verify_jwt(token, issuer="kyc-server")["jti"] == "abc"


def test_kms_backend_is_an_unimplemented_seam(monkeypatch) -> None:
    monkeypatch.setenv("KYC_SIGNER", "kms")
    registry.set_signer(None)
    try:
        with pytest.raises(NotImplementedError):
            registry.signer()
    finally:
        registry.set_signer(None)  # reset so other tests rebuild the local signer
