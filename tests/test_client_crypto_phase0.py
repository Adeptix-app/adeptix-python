from __future__ import annotations

from datetime import datetime, timezone

import pytest

from adeptix import KNOWN_ERROR_CODES, AdeptixApiError, AdeptixClient
from conftest import FakeTransport


def make_client(transport: FakeTransport) -> AdeptixClient:
    return AdeptixClient("ak_live_test", transport=transport)


def test_expires_in_minutes_is_sent_only_when_given():
    transport = FakeTransport((201, {"payment_request_id": "cpr_1"}))
    client = make_client(transport)
    client.crypto.create_payment_request(chain="polygon", token="USDC", amount="49.00", expires_in_minutes=30)
    assert transport.sent_json() == {"chain": "polygon", "token": "USDC", "amount": "49.00", "expires_in_minutes": 30}
    client.crypto.create_payment_request(chain="polygon", token="USDC", amount="49.00")
    assert transport.sent_json() == {"chain": "polygon", "token": "USDC", "amount": "49.00"}


def test_amount_below_minimum_exposes_minimum_amount():
    transport = FakeTransport(
        (
            400,
            {
                "error": "amount_below_minimum",
                "message": "The minimum amount for USDT on this network is 1.00.",
                "minimum_amount": "1.00",
            },
        ),
        (400, {"error": "invalid_expiry", "message": "expires_in_minutes must be a whole number of minutes from 10 to 60."}),
    )
    client = make_client(transport)
    with pytest.raises(AdeptixApiError) as info:
        client.crypto.create_payment_request(chain="tron", token="USDT", amount="0.5")
    assert info.value.code == "amount_below_minimum"
    assert info.value.minimum_amount == "1.00"
    with pytest.raises(AdeptixApiError) as info2:
        client.crypto.create_payment_request(chain="tron", token="USDT", amount="5", expires_in_minutes=5)
    assert info2.value.code == "invalid_expiry"
    assert info2.value.minimum_amount is None
    assert "invalid_expiry" in KNOWN_ERROR_CODES
    assert "amount_below_minimum" in KNOWN_ERROR_CODES
    assert len(KNOWN_ERROR_CODES) == len(set(KNOWN_ERROR_CODES))


def test_payment_requests_list_builds_the_query():
    row = {"payment_request_id": "cpr_1", "status": "matched", "payment": {"credited_amount": "9.95"}}
    transport = FakeTransport((200, {"data": [row]}), (200, {"data": []}), (200, row))
    client = make_client(transport)
    rows = client.crypto.payment_requests.list(
        status="matched", order_ref="o 1", created_after=datetime(2026, 10, 1, tzinfo=timezone.utc), limit=10
    )
    assert rows == [row]
    assert client.crypto.payment_requests.list() == []
    assert client.crypto.payment_requests.get("cpr_1") == row
    assert [c["url"] for c in transport.calls] == [
        "https://api.adeptix.app/v1/crypto/payment-requests"
        "?status=matched&order_ref=o+1&created_after=2026-10-01T00%3A00%3A00%2B00%3A00&limit=10",
        "https://api.adeptix.app/v1/crypto/payment-requests",
        "https://api.adeptix.app/v1/crypto/payment-requests/cpr_1",
    ]
