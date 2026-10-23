from __future__ import annotations

import hashlib
import hmac
import json
import time

from adeptix import (
    CRYPTO_PAYMENT_PAID_STATUSES,
    CRYPTO_PAYMENT_STATUSES,
    WEBHOOK_EVENT_TYPES,
    construct_event,
)

# Tolerance matching (Unreleased): status underpaid with the crypto_payment.underpaid event, and an
# overpayment within tolerance as a paid crypto_payment.matched with overpaid: true.

SECRET = "whsec_test_secret"

UNDERPAID = {
    "event": "crypto_payment.underpaid",
    "id": "evt_e2b7c94a1d0f4e3b9a6c58d7f1e2a304",
    "created": 1790000600,
    "api_version": "2026-10-15",
    "payment_request_id": "cpr_7ae03d5b1c9e4f2a8d6b0c3e1f4a7b92",
    "order_ref": "order_10231",
    "status": "underpaid",
    "asset_id": "polygon_usdc",
    "requested_amount": "49.00",
    "expected_amount": "49.0137",
    "received_amount": "48.0137",
    "difference": "-1",
    "difference_pct": "-2.04",
    "match_method": "tolerance",
    "tx_hash": "0xabc",
    "test_mode": False,
    "metadata": None,
    "description": None,
}


def sign_v2(body: str, ts: int) -> str:
    mac = hmac.new(SECRET.encode(), str(ts).encode() + b"." + body.encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def test_constants():
    assert CRYPTO_PAYMENT_STATUSES == ("pending", "matched", "expired", "underpaid")
    assert CRYPTO_PAYMENT_PAID_STATUSES == ("matched", "underpaid")
    assert "crypto_payment.underpaid" in WEBHOOK_EVENT_TYPES
    assert "crypto_payment.overpaid" not in WEBHOOK_EVENT_TYPES
    assert len(WEBHOOK_EVENT_TYPES) == 5


def test_construct_event_returns_the_amount_differs_fields():
    body = json.dumps(UNDERPAID)
    event = construct_event(body, sign_v2(body, int(time.time())), SECRET)
    assert event["event"] == "crypto_payment.underpaid"
    assert event["status"] in CRYPTO_PAYMENT_PAID_STATUSES
    assert event["status"] != "matched"
    assert (event["expected_amount"], event["received_amount"], event["difference"], event["difference_pct"]) == (
        "49.0137",
        "48.0137",
        "-1",
        "-2.04",
    )
    assert event["match_method"] == "tolerance"


def test_overpayment_within_tolerance_is_a_paid_matched_event():
    over = {
        "event": "crypto_payment.matched",
        "id": "evt_4c9d2e7f0a1b4c83b6e5d9a2f7c1e086",
        "created": 1790000600,
        "api_version": "2026-10-15",
        "payment_request_id": "cpr_7ae03d5b1c9e4f2a8d6b0c3e1f4a7b92",
        "order_ref": "order_10231",
        "status": "matched",
        "asset_id": "polygon_usdc",
        "quoted_amount": "49.0137",
        "amount": "50.0137",
        "tx_hash": "0xabc",
        "test_mode": False,
        "metadata": None,
        "description": None,
        "overpaid": True,
        "expected_amount": "49.0137",
        "received_amount": "50.0137",
        "difference": "1",
        "difference_pct": "2.04",
        "match_method": "tolerance",
    }
    body = json.dumps(over)
    event = construct_event(body, sign_v2(body, int(time.time())), SECRET)
    assert event["event"] == "crypto_payment.matched"
    assert event["status"] == "matched"
    assert event.get("overpaid") is True
    assert event["received_amount"] == event["amount"]


def test_legacy_overpaid_strings_never_crash_the_parser():
    # An event or status string this SDK no longer knows (sent briefly before overpayments within
    # tolerance became "matched") parses fine; a handler simply acknowledges it.
    legacy = dict(UNDERPAID, event="crypto_payment.overpaid", status="overpaid", received_amount="50.0137", difference="1", difference_pct="2.04")
    body = json.dumps(legacy)
    event = construct_event(body, sign_v2(body, int(time.time())), SECRET)
    assert event["event"] == "crypto_payment.overpaid"
    assert event["event"] not in WEBHOOK_EVENT_TYPES
    assert event["status"] not in CRYPTO_PAYMENT_PAID_STATUSES
