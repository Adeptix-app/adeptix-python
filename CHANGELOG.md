# Changelog

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
