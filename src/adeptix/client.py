"""The Adeptix API client. See https://docs.adeptix.app for the full reference."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, cast
from urllib.parse import quote

from ._version import __version__
from .errors import AdeptixApiError, AdeptixUnexpectedResponseError
from .types import (
    CryptoChain,
    CryptoPaymentRequest,
    CryptoPaymentRequestStatus,
    CryptoToken,
    Payment,
    PaymentStatus,
)

DEFAULT_BASE_URL = "https://api.adeptix.app/v1"
DEFAULT_TIMEOUT_S = 15.0
DEFAULT_MAX_RETRIES = 2

#: ``(method, url, headers, body, timeout_s) -> (status_code, raw_response_body)``.
#: Must return for ANY HTTP status (including 4xx/5xx) and raise only on a network-level failure
#: where no response was received at all.
Transport = Callable[[str, str, Mapping[str, str], Optional[bytes], float], Tuple[int, bytes]]


def _urllib_transport(
    method: str, url: str, headers: Mapping[str, str], body: Optional[bytes], timeout_s: float
) -> Tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as err:
        # urllib raises for non-2xx; that's still a real HTTP response, so hand it back as one.
        try:
            return err.code, err.read()
        finally:
            err.close()


def _quote_path_segment(value: str) -> str:
    return quote(value, safe="")


class AdeptixClient:
    """Entry point for the Adeptix API. Example::

        client = AdeptixClient(api_key=os.environ["ADEPTIX_API_KEY"])
        client.crypto.create_payment_request(chain="polygon", token="USDC", amount="49.00")
        client.payments.create(amount="49.00", currency="USD", email="...", provider="stripe")

    :param api_key: Your API key from the dashboard's API Keys page, e.g. ``"ak_live_..."``.
    :param base_url: Override the API base URL. Defaults to the production API - you shouldn't
        normally need this.
    :param timeout_s: Per-request timeout in seconds. Defaults to 15.
    :param max_retries: How many times to retry a GET request on a network error or a 5xx
        response, with exponential backoff. Defaults to 2. POST requests are NEVER auto-retried -
        there's no idempotency-key mechanism on the API today, so a retried POST could create a
        second payment request or checkout session. Retry those yourself only when you're sure the
        first attempt never reached the server.
    :param transport: Inject a custom HTTP transport - mainly for tests. See :data:`Transport`.
        Defaults to a stdlib ``urllib`` request.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: Optional[Transport] = None,
    ) -> None:
        if not api_key:
            raise ValueError("AdeptixClient requires an api_key")
        self._api_key = api_key
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._transport: Transport = transport or _urllib_transport

        self.crypto = CryptoPayments(self)
        self.payments = Payments(self)

    def __repr__(self) -> str:
        # Deliberately omits the API key so it can't leak into logs or tracebacks.
        return f"AdeptixClient(base_url={self._base_url!r})"

    def _request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self._base_url}{path}"
        is_retryable = method == "GET"
        attempt = 0

        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": f"adeptix-python/{__version__}",
        }
        payload: Optional[bytes] = None
        if body is not None:
            # Drop None values so an omitted optional field isn't sent as JSON null.
            payload = json.dumps({k: v for k, v in body.items() if v is not None}).encode("utf-8")
            headers["Content-Type"] = "application/json"

        while True:
            try:
                status, raw = self._transport(method, url, headers, payload, self._timeout_s)
            except Exception:
                # Network error / timeout - retry only GETs, same backoff as a 5xx.
                if is_retryable and attempt < self._max_retries:
                    attempt += 1
                    time.sleep(2**attempt * 0.2)
                    continue
                raise

            text = raw.decode("utf-8", errors="replace")

            if 200 <= status < 300:
                try:
                    return json.loads(text)
                except ValueError:
                    raise AdeptixUnexpectedResponseError(status, text) from None

            if is_retryable and status >= 500 and attempt < self._max_retries:
                attempt += 1
                time.sleep(2**attempt * 0.2)
                continue

            try:
                parsed = json.loads(text)
            except ValueError:
                raise AdeptixUnexpectedResponseError(status, text) from None
            if not isinstance(parsed, dict) or not isinstance(parsed.get("error"), str):
                raise AdeptixUnexpectedResponseError(status, text)
            raise AdeptixApiError(status, parsed)


class CryptoPayments:
    """The Crypto Payments API - unique, exact-amount on-chain deposits for USDT/USDC on BSC,
    Polygon, or Tron. See https://docs.adeptix.app/crypto-payments"""

    def __init__(self, client: AdeptixClient) -> None:
        self._client = client

    def create_payment_request(
        self,
        *,
        chain: CryptoChain,
        token: CryptoToken,
        amount: str,
        order_ref: Optional[str] = None,
        customer_email: Optional[str] = None,
    ) -> CryptoPaymentRequest:
        """Reserve a unique deposit amount and get the address to send it to.

        POST - never auto-retried, see ``max_retries``.

        :param chain: One of ``"bsc"``, ``"polygon"``, ``"tron"``.
        :param token: One of ``"USDT"``, ``"USDC"``.
        :param amount: The amount you want to receive, as a plain decimal string, e.g. ``"49.00"``.
            Not a float.
        :param order_ref: Your own order/invoice identifier, echoed back in the status response and
            webhook payload.
        :param customer_email: The customer's email, stored for your own records.
        """
        return cast(
            CryptoPaymentRequest,
            self._client._request(
                "POST",
                "/crypto/payment-requests",
                {
                    "chain": chain,
                    "token": token,
                    "amount": amount,
                    "order_ref": order_ref,
                    "customer_email": customer_email,
                },
            ),
        )

    def get_payment_request(self, payment_request_id: str) -> CryptoPaymentRequestStatus:
        """Check the status of a previously created crypto payment request."""
        return cast(
            CryptoPaymentRequestStatus,
            self._client._request(
                "GET", f"/crypto/payment-requests/{_quote_path_segment(payment_request_id)}"
            ),
        )


class Payments:
    """The Merchant Payments API - hosted card/bank/wallet checkout via whichever regulated
    providers are enabled on your account. See https://docs.adeptix.app/merchant-payments"""

    def __init__(self, client: AdeptixClient) -> None:
        self._client = client

    def create(
        self,
        *,
        amount: str,
        currency: str,
        email: str,
        provider: str,
        order_ref: Optional[str] = None,
    ) -> Payment:
        """Open a hosted checkout session with a provider.

        POST - never auto-retried, see ``max_retries``.

        :param amount: The amount to charge, as a plain decimal string, e.g. ``"49.00"``. Not a float.
        :param currency: A 3-letter ISO currency code, e.g. ``"USD"``.
        :param email: The customer's email address.
        :param provider: The id of an enabled provider on your account, e.g. ``"stripe"``.
        :param order_ref: Your own order/invoice identifier, echoed back in the status response and
            webhook payload.
        """
        return cast(
            Payment,
            self._client._request(
                "POST",
                "/payment-links",
                {
                    "amount": amount,
                    "currency": currency,
                    "email": email,
                    "provider": provider,
                    "order_ref": order_ref,
                },
            ),
        )

    def get(self, transaction_id: str) -> PaymentStatus:
        """Check the status of a previously created payment."""
        return cast(
            PaymentStatus,
            self._client._request("GET", f"/payments/{_quote_path_segment(transaction_id)}"),
        )
