# Provider integration strategy

The platform uses provider boundaries for payments, email and storage. Celery/Redis supplies a worker foundation. Credential-free development never manufactures a successful payment or delivered email.

Flutterwave is the initial Rwanda-oriented payment adapter. Orders snapshot product price/currency/features/entitlements. Activation follows server verification of status, amount, currency and reference. Payment, subscription and invoice writes are idempotent. Real provider sandbox approval and merchant capabilities still require external configuration. Supported currency exponents are USD2 and RWF0.

Implementation references: [Flutterwave Standard](https://developer.flutterwave.com/reference/checkout), [transaction verification](https://developer.flutterwave.com/docs/transaction-verification), [webhooks](https://developer.flutterwave.com/docs/webhooks). Confirm account/payment-method support with the merchant account before launch.

Storage supports local private files for development and an S3-compatible adapter. Configure bucket, endpoint, region and server credentials for AWS S3/R2/MinIO. The Compose MinIO service is not automatically a provisioned bucket. Private media belongs in private object storage; never expose the storage key as a public URL.

SMTP requires a reachable configured mail service. Email use cases return a truthful unavailable state when delivery is absent; production email queuing/retry and delivery monitoring require verification. Email credentials remain server-side.

Google Calendar, Gmail OAuth, Slack, Zoom and Microsoft Teams account connection flows are planned and not connected. Bookings work locally without meeting links/calendar synchronization. Do not interpret a configuration card as a working OAuth integration. AI/wearables/community flags remain disabled.
