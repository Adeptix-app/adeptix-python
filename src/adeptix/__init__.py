"""Official Python SDK for the Adeptix API - crypto payments and merchant payments.

Full API reference: https://docs.adeptix.app
"""

from ._version import __version__
from .client import AdeptixClient, CryptoAssets, CryptoPayments, Payments, Providers, Transport
from .errors import (
    KNOWN_ERROR_CODES,
    AdeptixApiError,
    AdeptixError,
    AdeptixUnexpectedResponseError,
    AdeptixWebhookSignatureError,
)
from .types import (
    CryptoAsset,
    CryptoChain,
    CryptoPaymentRequest,
    CryptoPaymentRequestStatus,
    CryptoPaymentStatus,
    CryptoToken,
    MerchantPaymentStatus,
    Payment,
    PaymentStatus,
    Provider,
    ProviderCountries,
    WebhookCryptoPaymentExpiredEvent,
    WebhookCryptoPaymentMatchedEvent,
    WebhookEvent,
    WebhookPaymentFailedEvent,
    WebhookPaymentPaidEvent,
)
from .webhooks import (
    DEFAULT_TOLERANCE_SECONDS,
    construct_event,
    parse_webhook_event,
    verify_webhook_signature,
    verify_webhook_signature_v2,
)

__all__ = [
    "__version__",
    "AdeptixClient",
    "CryptoAssets",
    "CryptoPayments",
    "Payments",
    "Providers",
    "Transport",
    "AdeptixError",
    "AdeptixApiError",
    "AdeptixUnexpectedResponseError",
    "AdeptixWebhookSignatureError",
    "KNOWN_ERROR_CODES",
    "verify_webhook_signature",
    "parse_webhook_event",
    "verify_webhook_signature_v2",
    "construct_event",
    "DEFAULT_TOLERANCE_SECONDS",
    "CryptoAsset",
    "Provider",
    "ProviderCountries",
    "WebhookPaymentFailedEvent",
    "WebhookCryptoPaymentExpiredEvent",
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
