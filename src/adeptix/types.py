"""Response and webhook payload shapes.

Responses are returned as plain ``dict`` objects decoded from the API's JSON (exactly what the API
sent, nothing dropped or renamed); these ``TypedDict`` definitions describe them for type checkers
and editors. They carry no runtime validation.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, TypedDict, Union

CryptoChain = Literal["bsc", "polygon", "tron"]
CryptoToken = Literal["USDT", "USDC"]
CryptoPaymentStatus = Literal["pending", "matched", "expired"]
MerchantPaymentStatus = Literal["pending", "paid", "failed", "expired"]


class _CheckoutFieldsResponse(TypedDict):
    """The optional fields echoed back on every create and status response (``None`` when not sent)."""

    return_url: Optional[str]
    cancel_url: Optional[str]
    metadata: Optional[Dict[str, str]]
    description: Optional[str]


class CryptoPaymentRequest(_CheckoutFieldsResponse):
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
    #: A hosted, no-login payment page for this request - send the customer here, or ignore it.
    checkout_url: str
    order_ref: Optional[str]


class CryptoPaymentRequestStatus(_CheckoutFieldsResponse):
    """Returned by ``client.crypto.get_payment_request``."""

    payment_request_id: str
    status: CryptoPaymentStatus
    order_ref: Optional[str]
    requested_amount: str
    quoted_amount: str
    created_at: str
    expires_at: str
    checkout_url: str


class Payment(_CheckoutFieldsResponse):
    """Returned by ``client.payments.create``."""

    transaction_id: str
    #: A hosted checkout URL. Treat it as opaque - redirect the customer's browser here.
    payment_url: str
    order_ref: Optional[str]


class PaymentStatus(_CheckoutFieldsResponse):
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


class _WebhookEnvelope(TypedDict):
    #: ``"evt_..."`` - unique per event and identical on every retry of it. Deduplicate on this.
    id: str
    #: When the event was created, unix seconds (stable across retries).
    created: int
    #: The event format version, ``"2026-10-15"``.
    api_version: str
    metadata: Optional[Dict[str, str]]
    description: Optional[str]


class WebhookPaymentPaidEvent(_WebhookEnvelope):
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
    #: ``True`` if the payment was created with a test key (``ak_test_...``). Test and live events
    #: go to the same webhook URL - never fulfil a real order from an event where this is ``True``.
    test_mode: bool


class WebhookPaymentFailedEvent(_WebhookEnvelope):
    """Same shape as ``payment.paid``, with ``status`` ``"failed"`` and null settlement fields."""

    event: Literal["payment.failed"]
    transaction_id: str
    order_ref: Optional[str]
    status: MerchantPaymentStatus
    currency: str
    amount: str
    asset: Optional[str]
    value_coin: Optional[str]
    txid_out: Optional[str]
    paid_at: Optional[str]
    test_mode: bool


class WebhookCryptoPaymentMatchedEvent(_WebhookEnvelope):
    event: Literal["crypto_payment.matched"]
    payment_request_id: str
    order_ref: Optional[str]
    status: CryptoPaymentStatus
    asset_id: str
    quoted_amount: str
    amount: str
    #: Starts with ``sandbox_`` for a test-mode match - not a real transaction hash.
    tx_hash: str
    #: ``True`` if the payment was created with a test key (``ak_test_...``). Test and live events
    #: go to the same webhook URL - never fulfil a real order from an event where this is ``True``.
    test_mode: bool


class WebhookCryptoPaymentExpiredEvent(_WebhookEnvelope):
    """Sent once when a pending crypto request passes ``expires_at`` with no matching deposit.
    Nothing was credited."""

    event: Literal["crypto_payment.expired"]
    payment_request_id: str
    order_ref: Optional[str]
    status: CryptoPaymentStatus
    asset_id: str
    quoted_amount: str
    #: ISO 8601
    expires_at: str
    test_mode: bool


#: Every event type this SDK version knows. New types can be added by the API at any time: branch
#: on ``event["event"]`` and acknowledge (2xx) the ones you don't handle.
WebhookEvent = Union[
    WebhookPaymentPaidEvent,
    WebhookPaymentFailedEvent,
    WebhookCryptoPaymentMatchedEvent,
    WebhookCryptoPaymentExpiredEvent,
]


class ProviderCountries(TypedDict):
    #: ``"confirmed"``: a real list of served countries; ``"broad"``: wide coverage, illustrative
    #: codes only; ``"unconfirmed"``: partial or empty.
    scope: Literal["confirmed", "broad", "unconfirmed"]
    #: ISO 3166-1 alpha-2 codes.
    codes: List[str]


class Provider(TypedDict):
    """A provider usable as ``provider`` in ``client.payments.create``."""

    #: Pass this as ``provider`` when creating a payment.
    id: str
    name: str
    #: A decimal string in ``minimum_currency``, or ``None`` if unknown.
    minimum_amount: Optional[str]
    minimum_currency: Optional[str]
    #: Human-readable summary; ``None`` means "not confirmed", not "none".
    payment_methods: Optional[str]
    countries: Optional[ProviderCountries]
    #: ``"degraded"`` = currently reported unstable; still usable.
    status: Literal["active", "degraded"]


class CryptoAsset(TypedDict):
    """A chain/token pair accepted by ``client.crypto.create_payment_request``."""

    #: ``"<chain>_<token lower case>"``, e.g. ``"polygon_usdc"``.
    id: str
    chain: CryptoChain
    token: CryptoToken
    decimals: int
    #: Deposits below this decimal-string amount are not credited.
    min_amount: str
    #: The platform's default commission as a fraction (0.005 = 0.5%).
    commission_rate_default: float
