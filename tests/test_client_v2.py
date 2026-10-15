from __future__ import annotations

import pytest

from adeptix import AdeptixApiError, AdeptixClient
from conftest import FakeTransport

PAYMENT = {
    "transaction_id": "txn_1",
    "payment_url": "https://x",
    "order_ref": "o1",
    "return_url": "https://shop.example.com/r",
    "cancel_url": None,
    "metadata": {"a": "b"},
    "description": "d",
}

PROVIDER = {
    "id": "stripe",
    "name": "Stripe",
    "minimum_amount": "2",
    "minimum_currency": "USD",
    "payment_methods": None,
    "countries": None,
    "status": "active",
}


def make_client(transport: FakeTransport, **kwargs) -> AdeptixClient:
    return AdeptixClient("ak_live_test", transport=transport, **kwargs)


def test_payments_create_sends_idempotency_key_and_new_fields_only_when_given():
    transport = FakeTransport((201, PAYMENT))
    client = make_client(transport)

    result = client.payments.create(
        amount="10.00",
        currency="USD",
        email="a@b.com",
        provider="stripe",
        order_ref="o1",
        return_url="https://shop.example.com/r",
        description="d",
        metadata={"a": "b"},
        idempotency_key="key-1",
    )
    assert transport.calls[0]["headers"]["Idempotency-Key"] == "key-1"
    assert transport.sent_json(0) == {
        "amount": "10.00",
        "currency": "USD",
        "email": "a@b.com",
        "provider": "stripe",
        "order_ref": "o1",
        "return_url": "https://shop.example.com/r",
        "description": "d",
        "metadata": {"a": "b"},
    }
    assert result["return_url"] == "https://shop.example.com/r"

    client.payments.create(amount="10.00", currency="USD", email="a@b.com", provider="stripe")
    assert "Idempotency-Key" not in transport.calls[1]["headers"]
    assert transport.sent_json(1) == {"amount": "10.00", "currency": "USD", "email": "a@b.com", "provider": "stripe"}


def test_crypto_create_passes_key_and_checkout_fields():
    transport = FakeTransport((201, {"payment_request_id": "cpr_1", "checkout_url": "https://dash.adeptix.app/pay/crypto/cpr_1"}))
    client = make_client(transport)
    result = client.crypto.create_payment_request(
        chain="tron",
        token="USDT",
        amount="5.00",
        cancel_url="https://shop.example.com/c",
        idempotency_key="k2",
    )
    assert transport.calls[0]["headers"]["Idempotency-Key"] == "k2"
    assert transport.sent_json(0) == {"chain": "tron", "token": "USDT", "amount": "5.00", "cancel_url": "https://shop.example.com/c"}
    assert result["checkout_url"].endswith("/cpr_1")


def test_a_post_with_an_idempotency_key_is_still_never_auto_retried(sleeps):
    transport = FakeTransport((500, {"error": "internal_error"}))
    client = make_client(transport, max_retries=3)
    with pytest.raises(AdeptixApiError):
        client.payments.create(amount="1", currency="USD", email="a@b.com", provider="stripe", idempotency_key="k")
    assert transport.call_count == 1
    assert sleeps == []


def test_idempotency_error_codes_surface_on_the_exception():
    transport = FakeTransport((409, {"error": "idempotent_request_in_progress"}))
    with pytest.raises(AdeptixApiError) as info:
        make_client(transport).payments.create(
            amount="1", currency="USD", email="a@b.com", provider="stripe", idempotency_key="k"
        )
    assert info.value.status == 409
    assert info.value.code == "idempotent_request_in_progress"


def test_providers_list_and_get():
    transport = FakeTransport((200, {"data": [PROVIDER]}), (200, PROVIDER))
    client = make_client(transport)
    assert client.providers.list() == [PROVIDER]
    assert client.providers.get("stripe") == PROVIDER
    assert [c["url"] for c in transport.calls] == [
        "https://api.adeptix.app/v1/providers",
        "https://api.adeptix.app/v1/providers/stripe",
    ]


def test_crypto_assets_list():
    asset = {"id": "tron_usdt", "chain": "tron", "token": "USDT", "decimals": 6, "min_amount": "1.00", "commission_rate_default": 0.005}
    transport = FakeTransport((200, {"data": [asset]}))
    assert make_client(transport).crypto.assets.list() == [asset]
    assert transport.calls[0]["url"] == "https://api.adeptix.app/v1/crypto/assets"
    assert transport.calls[0]["method"] == "GET"
