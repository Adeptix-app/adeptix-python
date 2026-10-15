"""Verify and parse Adeptix webhook deliveries. See https://docs.adeptix.app/webhooks"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from typing import Optional, Union, cast

from .errors import AdeptixWebhookSignatureError
from .types import WebhookEvent

_SIGNATURE_PREFIX = "sha256="
_HEX_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_DIGITS = re.compile(r"[0-9]{1,12}")

#: How far (seconds) a v2 signature timestamp may be from your clock.
DEFAULT_TOLERANCE_SECONDS = 300


def _to_bytes(value: Union[str, bytes, bytearray]) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    return bytes(value)


def verify_webhook_signature(
    raw_body: Union[str, bytes, bytearray],
    signature_header: Optional[str],
    webhook_secret: Union[str, bytes],
) -> bool:
    """Verify the ``x-adeptix-signature`` header against the raw (unparsed) request body.

    Always call this BEFORE ``json.loads``-ing the body - the signature covers the exact bytes
    received, not whatever your JSON parser normalizes them to. Pass ``bytes`` straight from your
    framework (e.g. Flask's ``request.get_data()``, Django's ``request.body``) where you can.

    :param raw_body: The exact, unparsed request body. A ``str`` is UTF-8 encoded before hashing.
    :param signature_header: The full ``x-adeptix-signature`` header value, e.g. ``"sha256=abc..."``.
    :param webhook_secret: Your account's webhook secret, from the dashboard's Settings page.
    :returns: ``True`` only if the signature is a valid HMAC-SHA256 of ``raw_body``. Never raises
        for a missing or malformed header - it just returns ``False``.
    """
    if not signature_header:
        return False

    provided = signature_header
    if provided.startswith(_SIGNATURE_PREFIX):
        provided = provided[len(_SIGNATURE_PREFIX):]

    # Reject anything that isn't exactly a 64-char hex digest up front. This only inspects the
    # attacker-supplied value (not the secret-derived one), so it leaks nothing about the expected
    # signature, and it guarantees compare_digest below gets two equal-length ASCII strings.
    if not _HEX_SHA256.fullmatch(provided):
        return False

    expected = hmac.new(_to_bytes(webhook_secret), _to_bytes(raw_body), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided.lower())


def verify_webhook_signature_v2(
    raw_body: Union[str, bytes, bytearray],
    signature_header: Optional[str],
    webhook_secret: Union[str, bytes],
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: Optional[float] = None,
) -> bool:
    """Verify the ``Adeptix-Signature`` header (``t=<unix seconds>,v1=<hex>``): an HMAC-SHA256 over
    ``"<t>.<raw body>"``, with replay protection.

    Returns ``False`` (never raises) for a missing or malformed header, a timestamp more than
    ``tolerance_seconds`` from ``now``, or a signature that matches none of the ``v1`` values. Call it
    BEFORE ``json.loads``-ing the body. This is the recommended scheme; ``verify_webhook_signature``
    (the ``x-adeptix-signature`` header) keeps working unchanged.

    :param now: Current time in unix seconds; defaults to the real clock (for tests).
    """
    if not signature_header:
        return False

    timestamp: Optional[str] = None
    candidates = []
    for part in signature_header.split(","):
        key, sep, value = part.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key:
            continue
        if key == "t":
            if timestamp is not None or not _DIGITS.fullmatch(value):
                return False
            timestamp = value
        elif key == "v1" and _HEX_SHA256.fullmatch(value):
            candidates.append(value.lower())
    if timestamp is None or not candidates:
        return False

    current = time.time() if now is None else now
    if abs(current - int(timestamp)) > tolerance_seconds:
        return False

    signed = timestamp.encode("ascii") + b"." + _to_bytes(raw_body)
    expected = hmac.new(_to_bytes(webhook_secret), signed, hashlib.sha256).hexdigest()
    ok = False
    for candidate in candidates:
        ok = hmac.compare_digest(expected, candidate) or ok
    return ok


def construct_event(
    raw_body: Union[str, bytes, bytearray],
    signature_header: Optional[str],
    webhook_secret: Union[str, bytes],
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
) -> WebhookEvent:
    """Verify the ``Adeptix-Signature`` header and decode the body in one step.

    Raises :class:`AdeptixWebhookSignatureError` if verification fails (bad signature or a
    timestamp outside the tolerance window) and ``ValueError`` if the verified body isn't a JSON
    object - never returns an unverified event. Branch on ``event["event"]``, acknowledge (2xx)
    types you don't handle, and deduplicate on ``event["id"]``.
    """
    if not verify_webhook_signature_v2(raw_body, signature_header, webhook_secret, tolerance_seconds):
        raise AdeptixWebhookSignatureError("Adeptix webhook signature verification failed")

    decoded = json.loads(_to_bytes(raw_body).decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Adeptix webhook payload was not a JSON object")
    return cast(WebhookEvent, decoded)


def parse_webhook_event(
    raw_body: Union[str, bytes, bytearray],
    signature_header: Optional[str],
    webhook_secret: Union[str, bytes],
) -> WebhookEvent:
    """Verify the signature and decode the body in one step.

    Raises :class:`AdeptixWebhookSignatureError` if the signature doesn't match, and ``ValueError``
    (``json.JSONDecodeError``) if the verified body isn't a JSON object - never returns an
    unverified event.
    """
    if not verify_webhook_signature(raw_body, signature_header, webhook_secret):
        raise AdeptixWebhookSignatureError("Adeptix webhook signature verification failed")

    decoded = json.loads(_to_bytes(raw_body).decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Adeptix webhook payload was not a JSON object")
    return cast(WebhookEvent, decoded)
