"""Response and webhook payload shapes.

Responses are returned as plain ``dict`` objects decoded from the API's JSON (exactly what the API
sent, nothing dropped or renamed); these ``TypedDict`` definitions describe them for type checkers
and editors. They carry no runtime validation.
"""

from __future__ import annotations

from typing import Literal, Optional, TypedDict, Union

CryptoChain = Literal["bsc", "polygon", "tron"]
CryptoToken = Literal["USDT", "USDC"]
CryptoPaymentStatus = Literal["pending", "matched", "expired"]
MerchantPaymentStatus = Literal["pending", "paid", "failed", "expired"]


class CryptoPaymentRequest(TypedDict):
    """Returned by ``client.crypto.create_payment_request``."""

    payment_request_id: str
    chain: CryptoChain
    token: CryptoToken
    #: The on-chain address to send the deposit to. Shared across requests - the amount is what
    #: identifies this one.
    pay_to_address: str
    #: The exact amount the customer must send. May differ slightly from the amount requested.
    amount: str
    #: ISO 8601 timestamp - the request stops being matchable after this time.
    expires_at: str


class CryptoPaymentRequestStatus(TypedDict):
    """Returned by ``client.crypto.get_payment_request``."""

    payment_request_id: str
    status: CryptoPaymentStatus
    order_ref: Optional[str]
    requested_amount: str
    quoted_amount: str
    created_at: str
    expires_at: str


class Payment(TypedDict):
    """Returned by ``client.payments.create``."""

    transaction_id: str
    #: A hosted checkout URL. Treat it as opaque - redirect the customer's browser here.
    payment_url: str


class PaymentStatus(TypedDict):
    """Returned by ``client.payments.get``."""

    transaction_id: str
    status: MerchantPaymentStatus
    order_ref: Optional[str]
    currency: str
    amount: str
    provider_id: str
    asset: Optional[str]
    value_coin: Optional[str]
    txid_out: Optional[str]
    created_at: str
    paid_at: Optional[str]


class WebhookPaymentPaidEvent(TypedDict):
    event: Literal["payment.paid"]
    transaction_id: str
    order_ref: Optional[str]
    status: MerchantPaymentStatus
    currency: str
    amount: str
    asset: Optional[str]
    value_coin: Optional[str]
    txid_out: Optional[str]
    paid_at: Optional[str]


class WebhookCryptoPaymentMatchedEvent(TypedDict):
    event: Literal["crypto_payment.matched"]
    payment_request_id: str
    order_ref: Optional[str]
    status: CryptoPaymentStatus
    asset_id: str
    quoted_amount: str
    amount: str
    tx_hash: str


WebhookEvent = Union[WebhookPaymentPaidEvent, WebhookCryptoPaymentMatchedEvent]
