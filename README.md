# adeptix

Official Python SDK for the [Adeptix API](https://docs.adeptix.app) — direct on-chain crypto
payments and hosted card/bank/wallet checkouts, from a single client.

Full API reference: **https://docs.adeptix.app**

## Install

```bash
pip install adeptix
```

> **Not on PyPI yet.** Until it is, install straight from GitHub:
>
> ```bash
> pip install git+https://github.com/Adeptix-app/adeptix-python.git
> ```

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

# Show request["amount"] and request["pay_to_address"] to the customer.
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

Amounts are always plain decimal **strings** (`"49.00"`), never floats. All parameters are
keyword-only. Responses are plain `dict`s, typed with `TypedDict`s (`CryptoPaymentRequest`,
`PaymentStatus`, ...) for your editor and type checker.

## Webhooks

Prefer webhooks over polling — see **https://docs.adeptix.app/webhooks** for how to configure a
webhook URL and secret from your dashboard.

```python
import os
from flask import Flask, request
from adeptix import AdeptixWebhookSignatureError, parse_webhook_event

app = Flask(__name__)

@app.post("/webhooks/adeptix")
def adeptix_webhook():
    # IMPORTANT: verification needs the raw body bytes, not request.get_json().
    try:
        event = parse_webhook_event(
            request.get_data(),
            request.headers.get("x-adeptix-signature"),
            os.environ["ADEPTIX_WEBHOOK_SECRET"],
        )
    except AdeptixWebhookSignatureError:
        return "", 401

    if event.get("test_mode"):
        # A test-key payment - acknowledge it, but never fulfil a real order from it.
        return "", 200

    if event["event"] == "payment.paid":
        ...  # mark your order paid - event["order_ref"] / event["transaction_id"]
    elif event["event"] == "crypto_payment.matched":
        ...  # mark your order paid - event["order_ref"] / event["payment_request_id"]

    return "", 200
```

In Django, pass `request.body` and `request.headers.get("x-adeptix-signature")`. If you only need a
yes/no answer, `verify_webhook_signature(raw_body, signature_header, secret)` returns a `bool` and
never raises.

Handlers should be idempotent — the same event can be delivered more than once.

## Test mode

Create a **Test** key (`ak_test_...`) from the dashboard's API Keys page and pass it as `api_key` —
nothing else in the client changes. No real payment is made and nothing touches a blockchain; the
amount you send picks the outcome:

- Merchant payments: an amount ending in `.00` is `paid` immediately (and a `payment.paid` webhook is
  sent), `.01` is `failed` (no webhook), anything else stays `pending`.
- Crypto payments: a requested amount ending in `.00` is `matched` immediately (and a
  `crypto_payment.matched` webhook is sent); anything else stays `pending` until it expires.
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
exponential backoff (`max_retries`, default 2). `POST` requests are **never** auto-retried — there's
no idempotency-key mechanism on the API today, so a retried `POST` could create a second payment
request or checkout session. Configure with:

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
