# adeptix

Official Python SDK for the [Adeptix API](https://docs.adeptix.app) — direct on-chain crypto
payments and hosted card/bank/wallet checkouts, from a single client.

Full API reference: **https://docs.adeptix.app**

## Install

Install straight from GitHub:

```bash
pip install git+https://github.com/Adeptix-app/adeptix-python.git
```

To pin a specific release instead of tracking the latest, add its tag:

```bash
pip install git+https://github.com/Adeptix-app/adeptix-python.git@v0.2.0
```

Requires Python 3.9 or later. No third-party dependencies — it uses only the standard library
(`urllib`, `hmac`, `json`).

## Quickstart

```python
import os
from adeptix import AdeptixClient

client = AdeptixClient(api_key=os.environ["ADEPTIX_API_KEY"])
```

### Crypto Payments API

```python
request = client.crypto.create_payment_request(
    chain="polygon",
    token="USDC",
    amount="49.00",
    order_ref="order_10231",
)

# Show request["amount"] and request["pay_to_address"] to the customer - or send them to
# request["checkout_url"], a hosted payment page (amount, address, QR code, countdown, live status).
# request["amount"] may differ slightly from "49.00" - see the docs' note on
# how deposits are matched by exact amount, not by a per-request address.

status = client.crypto.get_payment_request(request["payment_request_id"])
# status["status"]: "pending" | "matched" | "expired"
```

### Merchant Payments API

```python
payment = client.payments.create(
    amount="49.00",
    currency="USD",
    email="customer@example.com",
    provider="stripe",
    order_ref="order_10231",
)

# Redirect the customer's browser to payment["payment_url"].

status = client.payments.get(payment["transaction_id"])
# status["status"]: "pending" | "paid" | "failed" | "expired"
```

### Optional fields: description, return URL, cancel URL, metadata

Both create calls accept `description`, `return_url`, `cancel_url` and `metadata`; they are echoed
back in responses and (`metadata`, `description`) in webhooks.

```python
client.crypto.create_payment_request(
    chain="tron",
    token="USDT",
    amount="49.00",
    description="Annual plan",
    return_url="https://shop.example.com/thanks",  # used by the hosted checkout page
    cancel_url="https://shop.example.com/cart",
    metadata={"cart_id": "c_8841"},  # up to 20 string keys / string values
)
```

> `return_url` / `cancel_url` are applied on Adeptix-hosted pages (the crypto `checkout_url` page and
> the test-mode sandbox page). A customer paying by card or wallet through a live
> `payments.create()` checkout is **not** redirected back automatically - confirm the payment with the
> webhook or `payments.get()`, not by waiting for the customer to arrive at your return URL.

### Idempotency

Pass `idempotency_key=` to a create call and a retry of that same call can never create a second
payment: the same key with the same request returns the original response (same status and body); the
same key with a different request raises `AdeptixApiError` with code `idempotency_key_reuse`; the same
key while the first request is still running raises `idempotent_request_in_progress` (HTTP 409).

```python
import uuid

idempotency_key = str(uuid.uuid4())  # once per logical payment - store it with your order
payment = client.payments.create(
    amount="49.00",
    currency="USD",
    email="customer@example.com",
    provider="stripe",
    idempotency_key=idempotency_key,
)
# On a timeout, call it again with the SAME idempotency_key.
```

Keys are 1-255 printable ASCII characters and are remembered for 24 hours. See
**https://docs.adeptix.app/idempotency**.

### Discovery

```python
providers = client.providers.list()  # ids you can pass as `provider`
stripe = client.providers.get("stripe")
assets = client.crypto.assets.list()  # chain/token pairs you can request
```

Amounts are always plain decimal **strings** (`"49.00"`), never floats. All parameters are
keyword-only. Responses are plain `dict`s, typed with `TypedDict`s (`CryptoPaymentRequest`,
`PaymentStatus`, ...) for your editor and type checker.

## Webhooks

Prefer webhooks over polling — see **https://docs.adeptix.app/webhooks** for how to configure a
webhook URL and secret from your dashboard.

```python
import os
from flask import Flask, request
from adeptix import AdeptixWebhookSignatureError, construct_event

app = Flask(__name__)

@app.post("/webhooks/adeptix")
def adeptix_webhook():
    # IMPORTANT: verification needs the raw body bytes, not request.get_json().
    try:
        # Verifies the Adeptix-Signature header (HMAC over "<timestamp>.<raw body>") and rejects
        # timestamps more than 300 seconds off, so a captured delivery can't be replayed later.
        event = construct_event(
            request.get_data(),
            request.headers.get("Adeptix-Signature"),
            os.environ["ADEPTIX_WEBHOOK_SECRET"],
        )
    except AdeptixWebhookSignatureError:
        return "", 401

    if already_processed(event["id"]):  # dedupe on the event id
        return "", 200

    if event.get("test_mode"):
        # A test-key payment - acknowledge it, but never fulfil a real order from it.
        return "", 200

    if event["event"] == "payment.paid":
        ...  # mark your order paid - event["order_ref"] / event["transaction_id"]
    elif event["event"] == "crypto_payment.matched":
        ...  # mark your order paid - event["order_ref"] / event["payment_request_id"]
    elif event["event"] in ("payment.failed", "crypto_payment.expired"):
        ...  # a (test) card payment failed / a crypto request timed out unpaid
    # Any other event type: new ones can be added - acknowledge and ignore.

    mark_processed(event["id"])
    return "", 200
```

Every event has a stable `id` (identical on retries), `created` (unix seconds) and `api_version`. In
Django, pass `request.body` and `request.headers.get("Adeptix-Signature")`. If you only need a yes/no
answer, `verify_webhook_signature_v2(raw_body, header, secret)` returns a `bool` and never raises.

`construct_event` / `verify_webhook_signature_v2` read the newer `Adeptix-Signature` header. The
original `parse_webhook_event` / `verify_webhook_signature` (which read `x-adeptix-signature`) still
work unchanged if you haven't moved over - both headers are sent on every delivery. See
**https://docs.adeptix.app/webhooks**.

Handlers should be idempotent — the same event can be delivered more than once.

## Test mode

Create a **Test** key (`ak_test_...`) from the dashboard's API Keys page and pass it as `api_key` —
nothing else in the client changes. No real payment is made and nothing touches a blockchain; the
amount you send picks the outcome:

- Merchant payments: an amount ending in `.00` is `paid` immediately (and a `payment.paid` webhook is
  sent), `.01` is `failed` (and a `payment.failed` webhook is sent), anything else stays `pending`.
- Crypto payments: a requested amount ending in `.00` is `matched` immediately (and a
  `crypto_payment.matched` webhook is sent); anything else stays `pending` until it expires, then a
  `crypto_payment.expired` webhook is sent.
  `pay_to_address` is the literal string `"sandbox"`.

Test webhooks go to the same URL as live ones with `"test_mode": True` — make your production handler
ignore them, as in the example above. See **https://docs.adeptix.app** for details.

## Error handling

Every non-2xx response raises `AdeptixApiError`. Always check `.code`, not the message (which isn't
guaranteed to be present or stable):

```python
from adeptix import AdeptixApiError, AdeptixUnexpectedResponseError

try:
    client.payments.create(amount="49.00", currency="USD", email="a@b.com", provider="stripe")
except AdeptixApiError as err:
    print(err.status, err.code, err.details)
except AdeptixUnexpectedResponseError as err:
    # A non-JSON or malformed response (e.g. an HTML page from a proxy) - not a normal error path.
    print(err.status, err.body_text)
```

Both inherit from `AdeptixError`. Network failures (DNS, connection reset, timeout) are raised as
the underlying `urllib.error.URLError` / `OSError`, not wrapped.

See **https://docs.adeptix.app/errors** for the full list of error codes.

## Retries

`GET` requests (status checks) are automatically retried on a network error or a 5xx response, with
exponential backoff (`max_retries`, default 2). `POST` requests are **never** auto-retried by the
client - without an idempotency key a retried `POST` could create a second payment request or checkout
session. Retry them yourself with an `idempotency_key` (see above) and that is safe. Configure with:

```python
AdeptixClient(api_key=api_key, max_retries=3, timeout_s=20)
```

## Testing this SDK itself

```bash
python -m venv .venv
. .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## License

MIT
