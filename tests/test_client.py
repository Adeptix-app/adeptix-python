from __future__ import annotations

import pytest

from adeptix import (
    AdeptixApiError,
    AdeptixClient,
    AdeptixError,
    AdeptixUnexpectedResponseError,
)
from conftest import FakeTransport

PAYMENT_STATUS_PAID = {
    "transaction_id": "txn_test",
    "status": "paid",
    "order_ref": None,
    "currency": "USD",
    "amount": "10.00",
    "provider_id": "stripe",
    "asset": "USDC",
    "value_coin": "9.98",
    "txid_out": "0x1",
    "created_at": "x",
    "paid_at": "y",
}


def make_client(transport: FakeTransport, **kwargs) -> AdeptixClient:
    return AdeptixClient("ak_live_test", transport=transport, **kwargs)


# --- construction ----------------------------------------------------------------------------


def test_requires_an_api_key():
    with pytest.raises(ValueError):
        AdeptixClient("")


def test_repr_does_not_leak_the_api_key():
    assert "ak_live_test" not in repr(make_client(FakeTransport((200, {}))))


def test_custom_base_url_trailing_slash_is_stripped():
    transport = FakeTransport((200, PAYMENT_STATUS_PAID))
    client = make_client(transport, base_url="https://sandbox.example.com/v1///")
    client.payments.get("txn_test")
    assert transport.calls[0]["url"] == "https://sandbox.example.com/v1/payments/txn_test"


# --- crypto payments -------------------------------------------------------------------------


def test_create_payment_request_sends_the_right_request_and_parses_the_response():
    transport = FakeTransport(
        (
            201,
            {
                "payment_request_id": "cpr_test",
                "chain": "polygon",
                "token": "USDC",
                "pay_to_address": "0xabc",
                "amount": "49.0001",
                "expires_at": "2026-01-01T00:00:00.000Z",
            },
        )
    )
    client = make_client(transport, timeout_s=7)

    result = client.crypto.create_payment_request(
        chain="polygon", token="USDC", amount="49.00", order_ref="order_1"
    )

    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.adeptix.app/v1/crypto/payment-requests"
    assert call["headers"]["Authorization"] == "Bearer ak_live_test"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["timeout_s"] == 7
    # Omitted optional fields (customer_email) are dropped, not sent as null.
    assert transport.sent_json() == {
        "chain": "polygon",
        "token": "USDC",
        "amount": "49.00",
        "order_ref": "order_1",
    }
    assert result["payment_request_id"] == "cpr_test"
    assert result["amount"] == "49.0001"


def test_get_payment_request_issues_a_get_to_the_right_path():
    transport = FakeTransport(
        (
            200,
            {
                "payment_request_id": "cpr_abc",
                "status": "pending",
                "order_ref": None,
                "requested_amount": "1",
                "quoted_amount": "1",
                "created_at": "x",
                "expires_at": "y",
            },
        )
    )
    result = make_client(transport).crypto.get_payment_request("cpr_abc")

    call = transport.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://api.adeptix.app/v1/crypto/payment-requests/cpr_abc"
    assert call["headers"]["Authorization"] == "Bearer ak_live_test"
    assert call["body"] is None
    assert "Content-Type" not in call["headers"]
    assert result["status"] == "pending"


def test_path_ids_are_url_encoded():
    transport = FakeTransport((200, {"payment_request_id": "x", "status": "pending"}))
    make_client(transport).crypto.get_payment_request("cpr/../admin?x=1")
    assert transport.calls[0]["url"] == (
        "https://api.adeptix.app/v1/crypto/payment-requests/cpr%2F..%2Fadmin%3Fx%3D1"
    )


# --- merchant payments -----------------------------------------------------------------------


def test_payments_create_sends_the_right_request():
    transport = FakeTransport(
        (201, {"transaction_id": "txn_test", "payment_url": "https://example.com/checkout"})
    )
    result = make_client(transport).payments.create(
        amount="10.00", currency="usd", email="a@b.com", provider="stripe", order_ref="order_9"
    )

    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.adeptix.app/v1/payment-links"
    assert call["headers"]["Authorization"] == "Bearer ak_live_test"
    assert transport.sent_json() == {
        "amount": "10.00",
        "currency": "usd",
        "email": "a@b.com",
        "provider": "stripe",
        "order_ref": "order_9",
    }
    assert result["transaction_id"] == "txn_test"
    assert result["payment_url"] == "https://example.com/checkout"


def test_payments_get_returns_status():
    transport = FakeTransport((200, PAYMENT_STATUS_PAID))
    result = make_client(transport).payments.get("txn_test")

    assert transport.calls[0]["method"] == "GET"
    assert transport.calls[0]["url"] == "https://api.adeptix.app/v1/payments/txn_test"
    assert result["status"] == "paid"


def test_resource_params_are_keyword_only():
    client = make_client(FakeTransport((201, {})))
    with pytest.raises(TypeError):
        client.payments.create("10.00", "USD", "a@b.com", "stripe")  # type: ignore[misc]


# --- error handling --------------------------------------------------------------------------


def test_raises_api_error_with_code_and_details_from_a_400_response():
    body = {"error": "invalid_request", "details": {"fieldErrors": {"amount": ["bad"]}}}
    client = make_client(FakeTransport((400, body)))

    with pytest.raises(AdeptixApiError) as exc_info:
        client.payments.create(amount="bad", currency="USD", email="a@b.com", provider="stripe")

    err = exc_info.value
    assert err.status == 400
    assert err.code == "invalid_request"
    assert err.details == {"fieldErrors": {"amount": ["bad"]}}
    assert err.body == body
    assert "invalid_request" in str(err)
    assert isinstance(err, AdeptixError)
    assert not isinstance(err, AdeptixUnexpectedResponseError)


def test_api_error_uses_the_api_message_when_present():
    client = make_client(FakeTransport((401, {"error": "unauthorized", "message": "Bad API key"})))
    with pytest.raises(AdeptixApiError) as exc_info:
        client.payments.get("txn_test")
    assert str(exc_info.value) == "Bad API key"
    assert exc_info.value.code == "unauthorized"


def test_non_json_error_body_raises_unexpected_response_error():
    html = b"<html><body>502 Bad Gateway</body></html>"
    client = make_client(FakeTransport((502, html)))

    with pytest.raises(AdeptixUnexpectedResponseError) as exc_info:
        client.payments.create(amount="1", currency="USD", email="a@b.com", provider="stripe")

    err = exc_info.value
    assert err.status == 502
    assert err.body_text == html.decode()
    assert not isinstance(err, AdeptixApiError)


@pytest.mark.parametrize("body", [{"message": "no error field"}, {"error": 42}, ["error"], "error"])
def test_json_error_body_without_a_string_error_field_raises_unexpected_response_error(body):
    client = make_client(FakeTransport((400, body)))
    with pytest.raises(AdeptixUnexpectedResponseError) as exc_info:
        client.payments.create(amount="1", currency="USD", email="a@b.com", provider="stripe")
    assert exc_info.value.status == 400


def test_non_json_success_body_raises_unexpected_response_error():
    client = make_client(FakeTransport((200, b"OK")))
    with pytest.raises(AdeptixUnexpectedResponseError) as exc_info:
        client.payments.create(amount="1", currency="USD", email="a@b.com", provider="stripe")
    assert exc_info.value.status == 200
    assert exc_info.value.body_text == "OK"


# --- retries: GET retries, POST never does ---------------------------------------------------


def test_a_post_is_never_retried_on_a_500(sleeps):
    transport = FakeTransport((500, {"error": "internal_error"}))
    client = make_client(transport, max_retries=3)

    with pytest.raises(AdeptixApiError) as exc_info:
        client.payments.create(amount="1", currency="USD", email="a@b.com", provider="stripe")

    assert exc_info.value.code == "internal_error"
    assert transport.call_count == 1
    assert sleeps == []


def test_a_crypto_post_is_never_retried_on_a_500(sleeps):
    transport = FakeTransport((503, {"error": "internal_error"}))
    client = make_client(transport, max_retries=3)

    with pytest.raises(AdeptixApiError):
        client.crypto.create_payment_request(chain="tron", token="USDT", amount="5.00")

    assert transport.call_count == 1
    assert sleeps == []


def test_a_post_is_never_retried_on_a_network_error(sleeps):
    transport = FakeTransport(ConnectionError("connection reset"))
    client = make_client(transport, max_retries=3)

    with pytest.raises(ConnectionError):
        client.payments.create(amount="1", currency="USD", email="a@b.com", provider="stripe")

    assert transport.call_count == 1
    assert sleeps == []


def test_a_get_is_retried_on_a_500_up_to_max_retries_then_succeeds(sleeps):
    transport = FakeTransport(
        (500, {"error": "internal_error"}),
        (500, {"error": "internal_error"}),
        (200, PAYMENT_STATUS_PAID),
    )
    client = make_client(transport, max_retries=3)

    result = client.payments.get("txn_test")

    assert transport.call_count == 3
    assert result["status"] == "paid"
    assert sleeps == pytest.approx([0.4, 0.8])  # 2**attempt * 200ms


def test_a_get_is_retried_on_a_network_error(sleeps):
    transport = FakeTransport(TimeoutError("timed out"), (200, PAYMENT_STATUS_PAID))
    result = make_client(transport).payments.get("txn_test")

    assert transport.call_count == 2
    assert result["status"] == "paid"
    assert sleeps == pytest.approx([0.4])


def test_a_get_gives_up_after_max_retries_and_raises_the_last_error(sleeps):
    transport = FakeTransport((503, {"error": "platform_not_configured"}))
    client = make_client(transport, max_retries=2)

    with pytest.raises(AdeptixApiError) as exc_info:
        client.payments.get("txn_test")

    assert exc_info.value.code == "platform_not_configured"
    assert transport.call_count == 3  # initial + 2 retries
    assert sleeps == pytest.approx([0.4, 0.8])


def test_a_get_gives_up_after_max_retries_on_repeated_network_errors(sleeps):
    transport = FakeTransport(ConnectionError("down"))
    client = make_client(transport, max_retries=2)

    with pytest.raises(ConnectionError):
        client.crypto.get_payment_request("cpr_abc")

    assert transport.call_count == 3


def test_a_get_is_not_retried_on_a_4xx(sleeps):
    transport = FakeTransport((404, {"error": "not_found"}))
    with pytest.raises(AdeptixApiError) as exc_info:
        make_client(transport, max_retries=3).payments.get("txn_missing")

    assert exc_info.value.code == "not_found"
    assert transport.call_count == 1
    assert sleeps == []


def test_max_retries_zero_disables_get_retries(sleeps):
    transport = FakeTransport((500, {"error": "internal_error"}))
    with pytest.raises(AdeptixApiError):
        make_client(transport, max_retries=0).payments.get("txn_test")
    assert transport.call_count == 1
