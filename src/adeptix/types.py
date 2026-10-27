"""Response and webhook payload shapes.

Responses are returned as plain ``dict`` objects decoded from the API's JSON (exactly what the API
sent, nothing dropped or renamed); these ``TypedDict`` definitions describe them for type checkers
and editors. They carry no runtime validation.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, TypedDict, Union

CryptoChain = Literal["bsc", "polygon", "tron"]
CryptoToken = Literal["USDT", "USDC"]
#: ``"matched"``: paid. The exact quoted amount arrived, or slightly more and it was matched by
#: tolerance matching (``payment["match_method"] == "tolerance"``; the extra is not refunded
#: automatically). ``"underpaid"``: slightly less arrived and was matched by tolerance matching (you
#: were credited what arrived; you decide). New values can be added: treat a status you do not know
#: as not paid.
CryptoPaymentStatus = Literal["pending", "matched", "expired", "underpaid"]
#: How a deposit was matched to a request.
CryptoMatchMethod = Literal["exact", "tolerance", "manual"]
#: Every crypto payment request status this SDK version knows.
CRYPTO_PAYMENT_STATUSES = ("pending", "matched", "expired", "underpaid")
#: Statuses in which a deposit was matched and credited (``"matched"`` is paid; ``"underpaid"`` is
#: for you to decide).
CRYPTO_PAYMENT_PAID_STATUSES = ("matched", "underpaid")
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
    #: The on-chain address to send the deposit to, for this request. It can differ between
    #: requests: always show the address from this response. Together with the exact amount it
    #: identifies this payment.
    pay_to_address: str
    #: The exact amount the customer must send. With a live key, 0.0001 to 0.05 above the amount
    #: requested.
    amount: str
    #: ISO 8601 timestamp - the request stops being matchable after this time
    #: (``expires_in_minutes`` after creation, 20 by default).
    expires_at: str
    #: A hosted, no-login payment page for this request - send the customer here, or ignore it.
    checkout_url: str
    order_ref: Optional[str]


class _CryptoPaymentDetailAdditions(TypedDict, total=False):
    #: ``"exact"``, ``"tolerance"`` (status underpaid / overpaid) or ``"manual"`` (assigned by
    #: support). Absent from older API responses.
    match_method: Optional[CryptoMatchMethod]


class CryptoPaymentDetail(_CryptoPaymentDetailAdditions):
    """The matched deposit of a crypto payment request, and what it credited."""

    #: Starts with ``sandbox_`` in test mode.
    tx_hash: str
    #: The amount that actually arrived (decimal string).
    amount: str
    #: ``None`` for Tron and in test mode.
    block_number: Optional[int]
    #: ISO 8601
    detected_at: str
    #: Net amount credited to your balance (amount minus commission); ``None`` in test mode.
    credited_amount: Optional[str]
    #: ``amount`` minus ``credited_amount``; ``None`` in test mode.
    commission_amount: Optional[str]


class _CryptoPaymentRequestStatusAdditions(TypedDict, total=False):
    """Fields added to the status response after 0.2.0 (absent from older API responses)."""

    #: ``"<chain>_<token lower case>"``, e.g. ``"polygon_usdc"``.
    asset_id: str
    chain: Optional[CryptoChain]
    token: Optional[CryptoToken]
    #: The address returned when the request was created (it can differ between requests);
    #: ``"sandbox"`` for a test request.
    pay_to_address: Optional[str]
    #: The matched deposit; ``None`` unless ``status`` is ``"matched"`` or ``"underpaid"``.
    payment: Optional[CryptoPaymentDetail]


class CryptoPaymentRequestStatus(_CheckoutFieldsResponse, _CryptoPaymentRequestStatusAdditions):
    """Returned by ``client.crypto.get_payment_request`` and ``client.crypto.payment_requests.list``."""

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


class _WebhookCryptoPaymentMatchedOptional(TypedDict, total=False):
    #: Present (``True``) only when support assigned this payment to the request by hand after
    #: reviewing it, e.g. a payment that arrived after expiry. Absent on automatic matches.
    manual: bool
    #: Present (``True``) only when slightly MORE than ``quoted_amount`` arrived and tolerance
    #: matching assigned it to this request. Still paid; the extra is not refunded automatically.
    #: The five keys below are present exactly when this one is.
    overpaid: bool
    #: With ``overpaid``: the quoted amount the customer was asked to send.
    expected_amount: str
    #: With ``overpaid``: what actually arrived (same as ``amount``).
    received_amount: str
    #: With ``overpaid``: ``received_amount`` minus ``expected_amount``, signed decimal string.
    difference: str
    #: With ``overpaid``: ``difference`` as a percentage of ``expected_amount``, two decimals.
    difference_pct: str
    #: With ``overpaid``: always ``"tolerance"``.
    match_method: Literal["tolerance"]


class WebhookCryptoPaymentMatchedEvent(_WebhookEnvelope, _WebhookCryptoPaymentMatchedOptional):
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


class WebhookCryptoPaymentAmountDiffersEvent(_WebhookEnvelope):
    """``crypto_payment.underpaid``: sent instead of ``crypto_payment.matched`` when a deposit of
    slightly LESS than the quoted amount was matched to the request by tolerance matching. You were
    credited ``received_amount`` minus commission. Fulfil the order only if you accept the amount
    received; refunds are manual. (Slightly MORE counts as paid: ``crypto_payment.matched`` with
    ``overpaid: True``.)"""

    event: Literal["crypto_payment.underpaid"]
    payment_request_id: str
    order_ref: Optional[str]
    status: Literal["underpaid"]
    asset_id: str
    requested_amount: str
    #: The quoted amount the customer was asked to send.
    expected_amount: str
    #: What actually arrived on-chain.
    received_amount: str
    #: ``received_amount`` minus ``expected_amount``, signed decimal string.
    difference: str
    #: ``difference`` as a percentage of ``expected_amount``, two decimals, signed string.
    difference_pct: str
    match_method: Literal["tolerance"]
    tx_hash: str
    test_mode: bool


#: Every event type this SDK version knows. New types can be added by the API at any time: branch
#: on ``event["event"]`` and acknowledge (2xx) the ones you don't handle.
WebhookEvent = Union[
    WebhookPaymentPaidEvent,
    WebhookPaymentFailedEvent,
    WebhookCryptoPaymentMatchedEvent,
    WebhookCryptoPaymentAmountDiffersEvent,
    WebhookCryptoPaymentExpiredEvent,
]

#: Every webhook event name this SDK version knows.
WEBHOOK_EVENT_TYPES = (
    "payment.paid",
    "payment.failed",
    "crypto_payment.matched",
    "crypto_payment.underpaid",
    "crypto_payment.expired",
)


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
    #: The smallest amount you can request (decimal string); deposits below it are never credited
    #: automatically.
    min_amount: str
    #: The platform's default commission as a fraction (0.005 = 0.5%).
    commission_rate_default: float
