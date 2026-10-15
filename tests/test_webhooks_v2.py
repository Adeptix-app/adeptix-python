from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from adeptix import (
    AdeptixWebhookSignatureError,
    construct_event,
    verify_webhook_signature,
    verify_webhook_signature_v2,
)

# Webhooks v2: `Adeptix-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">`.

SECRET = "whsec_test_secret"
NOW = 1_800_000_000


def sign_v2(body, secret: str, ts: int) -> str:
    raw = body.encode() if isinstance(body, str) else body
    mac = hmac.new(secret.encode(), str(ts).encode() + b"." + raw, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def test_matches_the_cross_sdk_test_vector():
    # The same vector the Node and PHP SDK tests use: all three must agree on it.
    body = '{"event":"payment.paid","id":"evt_1"}'
    header = "t=1800000000,v1=eef418a69de72d5244d7bd44535f9c515ed4fa7cbb9f241319d4f372078c37b7"
    assert verify_webhook_signature_v2(body, header, SECRET, now=NOW) is True


def test_accepts_valid_signature_string_or_bytes_inside_tolerance():
    body = json.dumps({"event": "payment.paid", "id": "evt_1"})
    header = sign_v2(body, SECRET, NOW)
    assert verify_webhook_signature_v2(body, header, SECRET, now=NOW) is True
    assert verify_webhook_signature_v2(body.encode(), header, SECRET, now=NOW + 300) is True
    assert verify_webhook_signature_v2(body, header, SECRET, now=NOW - 300) is True


def test_rejects_stale_or_future_timestamps_and_tolerance_is_configurable():
    header = sign_v2("{}", SECRET, NOW)
    assert verify_webhook_signature_v2("{}", header, SECRET, now=NOW + 301) is False
    assert verify_webhook_signature_v2("{}", header, SECRET, now=NOW - 301) is False
    assert verify_webhook_signature_v2("{}", header, SECRET, tolerance_seconds=900, now=NOW + 600) is True


def test_rejects_tampered_body_wrong_secret_and_restamped_timestamp():
    body = json.dumps({"event": "payment.paid"})
    header = sign_v2(body, SECRET, NOW)
    assert verify_webhook_signature_v2(body + " ", header, SECRET, now=NOW) is False
    assert verify_webhook_signature_v2(body, header, "other", now=NOW) is False
    assert verify_webhook_signature_v2(body, header.replace(f"t={NOW}", f"t={NOW + 1}"), SECRET, now=NOW) is False


def test_a_legacy_signature_is_not_a_v2_signature_and_vice_versa():
    body = "{}"
    legacy = "sha256=" + hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    assert verify_webhook_signature_v2(body, legacy, SECRET, now=NOW) is False
    assert verify_webhook_signature(body, sign_v2(body, SECRET, NOW), SECRET) is False
    assert verify_webhook_signature(body, legacy, SECRET) is True  # legacy verifier unchanged


def test_accepts_any_matching_v1_and_ignores_unknown_keys_and_never_raises_on_garbage():
    good = sign_v2("{}", SECRET, NOW).split("v1=")[1]
    assert verify_webhook_signature_v2("{}", f"t={NOW},v1={'0' * 64},v1={good}", SECRET, now=NOW) is True
    assert verify_webhook_signature_v2("{}", f"v0=x, t={NOW} , v1={good}, future=1", SECRET, now=NOW) is True
    for header in [None, "", "garbage", "t=,v1=", f"t=abc,v1={good}", f"v1={good}", f"t={NOW}", f"t={NOW},t={NOW},v1={good}", f"t={NOW},v1=zz"]:
        assert verify_webhook_signature_v2("{}", header, SECRET, now=NOW) is False, header


def test_construct_event_returns_the_event_for_each_known_type():
    import time

    for name in ["payment.paid", "payment.failed", "crypto_payment.matched", "crypto_payment.expired"]:
        body = json.dumps({"event": name, "id": "evt_1", "created": NOW, "api_version": "2026-10-15"})
        event = construct_event(body, sign_v2(body, SECRET, int(time.time())), SECRET)
        assert event["event"] == name
        assert event["id"] == "evt_1"


def test_construct_event_raises_on_bad_or_stale_signatures():
    body = json.dumps({"event": "payment.paid"})
    with pytest.raises(AdeptixWebhookSignatureError):
        construct_event(body, "t=1,v1=" + "0" * 64, SECRET)
    with pytest.raises(AdeptixWebhookSignatureError):
        construct_event(body, sign_v2(body, SECRET, 1_000), SECRET)
    with pytest.raises(AdeptixWebhookSignatureError):
        construct_event(body, None, SECRET)
