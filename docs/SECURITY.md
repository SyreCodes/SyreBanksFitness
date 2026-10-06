# Security boundaries

Passwords use Argon2; access tokens are short-lived signed JWTs with audience/issuer checks. Refresh tokens are random, stored as hashes and rotated. Reuse revokes their session family. Password reset revokes prior sessions and uses expiring one-time tokens. Staff privileges cannot be requested through public registration.

Roles currently use a centrally enforced role enum and service policies. Extensible database roles/permissions and administrator MFA are not implemented. ADMIN/SUPER_ADMIN manage business configuration; COACH access is restricted to assigned clients and owned/published templates; CLIENT accesses only their own coaching records. Permission and ownership tests cover these boundaries.

Cookie mutation endpoints check allowlisted Origin and session-bound CSRF values. Production refresh cookies are Secure/HttpOnly with constrained SameSite behavior; CORS uses explicit origins. Rate limits use Redis when configured. Local in-memory fallback is only appropriate for single-process development and does not protect a multi-worker deployment.

Uploads validate size, MIME and file signatures, use generated storage keys, and keep client media private. Access is owner/staff-scoped; private URLs expire and are bound to a user and asset. Public client stories require current, explicit photo publication consent and are filtered again at read time. Browser UI never makes medical diagnoses.

Audit rows record resource actions and actors without tokens/passwords/health request bodies. Database administrators can still change stored rows; tamper-evident external retention and request/IP metadata expansion remain production hardening work. Production deployments require backup/restore validation, TLS, restricted storage buckets and provider sandbox acceptance.
