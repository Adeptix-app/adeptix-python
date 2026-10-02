"""Official Python SDK for the Adeptix API - crypto payments and merchant payments.

Full API reference: https://docs.adeptix.app
"""

from ._version import __version__
from .client import AdeptixClient, CryptoPayments, Payments, Transport
from .errors import (
    KNOWN_ERROR_CODES,
    AdeptixApiError,
    AdeptixError,
    AdeptixUnexpectedResponseError,
    AdeptixWebhookSignatureError,
)
from .types import (
    CryptoChain,
    CryptoPaymentRequest,
    CryptoPaymentRequestStatus,
    CryptoPaymentStatus,
    CryptoToken,
    MerchantPaymentStatus,
    Payment,
    PaymentStatus,
    WebhookCryptoPaymentMatchedEvent,
    WebhookEvent,
    WebhookPaymentPaidEvent,
)
from .webhooks import parse_webhook_event, verify_webhook_signature

__all__ = [
    "__version__",
    "AdeptixClient",
    "CryptoPayments",
    "Payments",
    "Transport",
    "AdeptixError",
    "AdeptixApiError",
    "AdeptixUnexpectedResponseError",
    "AdeptixWebhookSignatureError",
    "KNOWN_ERROR_CODES",
    "verify_webhook_signature",
    "parse_webhook_event",
    "CryptoChain",
    "CryptoToken",
    "CryptoPaymentStatus",
    "MerchantPaymentStatus",
    "CryptoPaymentRequest",
    "CryptoPaymentRequestStatus",
    "Payment",
    "PaymentStatus",
    "WebhookEvent",
    "WebhookPaymentPaidEvent",
    "WebhookCryptoPaymentMatchedEvent",
]
