from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from adeptix import (
    AdeptixWebhookSignatureError,
    parse_webhook_event,
    verify_webhook_signature,
)

SECRET = "whsec_test_secret"


def sign(body: str, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def body_of(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"))


# --- verify_webhook_signature ----------------------------------------------------------------


def test_accepts_a_correctly_signed_payload():
    body = body_of({"event": "payment.paid", "transaction_id": "txn_1"})
    assert verify_webhook_signature(body, sign(body, SECRET), SECRET) is True


def test_rejects_a_tampered_payload():
    body = body_of({"event": "payment.paid", "transaction_id": "txn_1"})
    signature = sign(body, SECRET)
    tampered = body_of({"event": "payment.paid", "transaction_id": "txn_2"})
    assert verify_webhook_signature(tampered, signature, SECRET) is False


def test_rejects_a_tampered_signature():
    body = body_of({"event": "payment.paid", "transaction_id": "txn_1"})
    signature = sign(body, SECRET)
    flipped = signature[:-1] + ("0" if signature[-1] != "0" else "1")
    assert verify_webhook_signature(body, flipped, SECRET) is False


def test_rejects_a_signature_made_with_the_wrong_secret():
    body = body_of({"event": "payment.paid", "transaction_id": "txn_1"})
    assert verify_webhook_signature(body, sign(body, "wrong_secret"), SECRET) is False


@pytest.mark.parametrize("header", [None, ""])
def test_rejects_a_missing_signature_header(header):
    assert verify_webhook_signature("{}", header, SECRET) is False


@pytest.mark.parametrize(
    "header",
    [
        "sha256=not-hex-!!",
        "sha256=",
        "sha256=abc",  # too short
        "sha256=" + "é" * 64,  # non-ASCII must not raise from compare_digest
    ],
)
def test_rejects_a_malformed_signature_without_raising(header):
    assert verify_webhook_signature("{}", header, SECRET) is False


def test_rejects_a_valid_signature_with_trailing_garbage():
    body = "{}"
    assert verify_webhook_signature(body, sign(body, SECRET) + "00", SECRET) is False
    assert verify_webhook_signature(body, sign(body, SECRET) + " ", SECRET) is False


def test_rejects_a_different_algorithm_prefix():
    body = "{}"
    digest = sign(body, SECRET)[len("sha256="):]
    assert verify_webhook_signature(body, "sha1=" + digest, SECRET) is False


def test_accepts_a_bare_hex_digest_and_uppercase_hex_like_the_node_sdk():
    body = "{}"
    digest = sign(body, SECRET)[len("sha256="):]
    assert verify_webhook_signature(body, digest, SECRET) is True
    assert verify_webhook_signature(body, "sha256=" + digest.upper(), SECRET) is True


def test_works_with_a_bytes_body_not_just_a_str():
    body = body_of({"event": "payment.paid"})
    signature = sign(body, SECRET)
    assert verify_webhook_signature(body.encode("utf-8"), signature, SECRET) is True
    assert verify_webhook_signature(bytearray(body.encode("utf-8")), signature, SECRET) is True


def test_non_ascii_body_is_hashed_as_utf8():
    # Raw UTF-8 in the body, not a \u escape.
    body = json.dumps({"event": "payment.paid", "order_ref": "café"}, ensure_ascii=False)
    signature = sign(body, SECRET)
    assert verify_webhook_signature(body, signature, SECRET) is True
    assert verify_webhook_signature(body.encode("utf-8"), signature, SECRET) is True


def test_accepts_a_bytes_secret():
    body = "{}"
    assert verify_webhook_signature(body, sign(body, SECRET), SECRET.encode()) is True


def test_uses_constant_time_comparison(monkeypatch):
    calls = []
    real = hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr("adeptix.webhooks.hmac.compare_digest", spy)
    body = "{}"
    assert verify_webhook_signature(body, sign(body, SECRET), SECRET) is True
    assert len(calls) == 1


# --- parse_webhook_event ---------------------------------------------------------------------


def test_parse_returns_the_parsed_event_when_the_signature_is_valid():
    body = body_of({"event": "crypto_payment.matched", "payment_request_id": "cpr_1"})
    event = parse_webhook_event(body, sign(body, SECRET), SECRET)
    assert event["event"] == "crypto_payment.matched"
    assert event["payment_request_id"] == "cpr_1"


def test_parse_accepts_a_bytes_body():
    body = body_of({"event": "payment.paid", "transaction_id": "txn_1"})
    event = parse_webhook_event(body.encode(), sign(body, SECRET), SECRET)
    assert event["event"] == "payment.paid"


def test_parse_raises_when_the_signature_is_invalid():
    body = body_of({"event": "payment.paid"})
    with pytest.raises(AdeptixWebhookSignatureError):
        parse_webhook_event(body, "sha256=wrong", SECRET)


def test_parse_raises_when_the_body_was_tampered():
    body = body_of({"event": "payment.paid", "amount": "1.00"})
    signature = sign(body, SECRET)
    with pytest.raises(AdeptixWebhookSignatureError):
        parse_webhook_event(body.replace("1.00", "999.00"), signature, SECRET)


def test_parse_raises_when_the_signature_header_is_missing():
    with pytest.raises(AdeptixWebhookSignatureError):
        parse_webhook_event("{}", None, SECRET)


def test_signature_error_is_a_value_error():
    with pytest.raises(ValueError):
        parse_webhook_event("{}", None, SECRET)


def test_parse_raises_on_a_validly_signed_non_json_body():
    body = "not json"
    with pytest.raises(ValueError) as exc_info:
        parse_webhook_event(body, sign(body, SECRET), SECRET)
    assert not isinstance(exc_info.value, AdeptixWebhookSignatureError)


def test_parse_raises_on_a_validly_signed_non_object_json_body():
    body = "[1,2,3]"
    with pytest.raises(ValueError):
        parse_webhook_event(body, sign(body, SECRET), SECRET)
