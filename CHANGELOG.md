# Changelog

## 0.3.1

- **Verified email**: a live key now gets `403` with the new error code `email_unverified` from
  `payments.create()` and `crypto.create_payment_request()` until the account's email address is
  verified in the dashboard. Test keys are not affected. The code is added to `KNOWN_ERROR_CODES`.

## 0.3.0

All additions; existing code keeps working unchanged.

- **Payment window**: `crypto.create_payment_request()` takes an optional `expires_in_minutes=`
  (10-60, default 20). New error code `invalid_expiry`.
- **Minimum amount**: requests below the asset's `min_amount` are refused with the new error code
  `amount_below_minimum`; `AdeptixApiError.minimum_amount` carries the minimum.
- **Richer status**: `CryptoPaymentRequestStatus` gains `asset_id`, `chain`, `token`,
  `pay_to_address` and `payment` (`CryptoPaymentDetail`: `tx_hash`, `amount`, `block_number`,
  `detected_at`, `credited_amount`, `commission_amount`), typed as optional keys.
- **List**: `crypto.payment_requests.list(status=, order_ref=, created_after=, limit=)` (newest
  first, limit 1-100, default 25) and `crypto.payment_requests.get(id)`.
- **Webhooks**: optional `manual: True` on `crypto_payment.matched` when support assigned a payment
  by hand after review.
- **Tolerance matching**: a slightly different amount that can only belong to one request is
  matched and you are credited what arrived. Slightly **more** counts as paid: status `"matched"`
  and `crypto_payment.matched` with the new optional keys `overpaid: True`, `expected_amount`,
  `received_amount`, `difference`, `difference_pct` and `match_method` (the extra is not refunded
  automatically). Slightly **less**: `CryptoPaymentStatus` gains `"underpaid"` and the new event
  `crypto_payment.underpaid` (`WebhookCryptoPaymentAmountDiffersEvent`: `requested_amount`,
  `expected_amount`, `received_amount`, `difference`, `difference_pct`, `match_method`, `tx_hash`):
  fulfil only if you accept the amount received. Also `CryptoPaymentDetail["match_method"]` and the
  constants `CRYPTO_PAYMENT_STATUSES`, `CRYPTO_PAYMENT_PAID_STATUSES` and `WEBHOOK_EVENT_TYPES`.

## 0.2.0

All additions; existing code keeps working unchanged.

- **Idempotency**: `payments.create()` and `crypto.create_payment_request()` take an optional
  `idempotency_key=`. New error codes `idempotency_key_reuse` and `idempotent_request_in_progress`.
- **Checkout fields**: `description`, `return_url`, `cancel_url` and `metadata` on both create calls;
  echoed back on create and status responses. Crypto create/status responses now include
  `checkout_url`, a hosted payment page.
- **Discovery**: `providers.list()`, `providers.get(id)` and `crypto.assets.list()`.
- **Webhooks v2**: `construct_event()` and `verify_webhook_signature_v2()` verify the
  `Adeptix-Signature` header (timestamped, replay-protected, default tolerance 300 s). New events
  `payment.failed` and `crypto_payment.expired`; every event carries `id`, `created` and
  `api_version` plus `metadata` and `description`. `verify_webhook_signature()` and
  `parse_webhook_event()` are unchanged.
- Types for all of the above; `WebhookEvent` is now a union of four event types - handle unknown
  `event` values by acknowledging them.

## 0.1.0

Initial release.
