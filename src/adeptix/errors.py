"""Exceptions raised by the Adeptix SDK. See https://docs.adeptix.app/errors"""

from __future__ import annotations

from typing import Any, Dict, Optional

#: Every error code the API documents today. ``AdeptixApiError.code`` is a plain ``str`` because
#: new codes may be added without an SDK release - compare against these, don't exhaustively match.
KNOWN_ERROR_CODES = (
    "unauthorized",
    "invalid_request",
    "not_found",
    "platform_not_configured",
    "internal_error",
    "asset_unavailable",
    "no_quote_available",
    "provider_unavailable",
    "provider_disabled_for_account",
    "checkout_provider_error",
)


class AdeptixError(Exception):
    """Base class for every exception this SDK raises itself (network errors are not wrapped)."""


class AdeptixApiError(AdeptixError):
    """Raised for any non-2xx response from the Adeptix API with a well-formed error body.

    ``code`` matches the ``error`` field documented at https://docs.adeptix.app/errors - always
    branch on ``code``, not on the message (which isn't guaranteed to be present or stable across
    API versions).
    """

    status: int
    code: str
    details: Any
    body: Dict[str, Any]

    def __init__(self, status: int, body: Dict[str, Any]) -> None:
        message: Optional[str] = body.get("message") if isinstance(body.get("message"), str) else None
        super().__init__(message or f"Adeptix API request failed with {status} ({body['error']})")
        self.status = status
        self.code = body["error"]
        self.details = body.get("details")
        self.body = body


class AdeptixUnexpectedResponseError(AdeptixError):
    """Raised when the API returns a non-JSON body, or JSON without a string ``error`` field -
    a genuine surprise, not a normal error path."""

    status: int
    body_text: str

    def __init__(self, status: int, body_text: str) -> None:
        super().__init__(f"Adeptix API returned an unexpected {status} response")
        self.status = status
        self.body_text = body_text


class AdeptixWebhookSignatureError(AdeptixError, ValueError):
    """Raised by :func:`adeptix.parse_webhook_event` when the signature doesn't match the body."""
