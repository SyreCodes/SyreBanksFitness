# API module map

FastAPI exposes versioned REST under `/api/v1`; `/docs` contains actual schema and route documentation. Lists return `{items,total}` and accept bounded `limit`/`offset`. UUID object IDs are opaque. JSON errors use `{error:{code,message,details,request_id}}`.

| Domain | Implemented surface |
| --- | --- |
| Auth | register, login, me, refresh, logout, account/session actions, email verification and password-reset use cases |
| Clients | staff-scoped list/create/detail/update; own assessment/screening/consent profile |
| Leads | anonymous consented application; staff-scoped pipeline list/detail/update |
| Coaching | exercises; program templates/edit/assign; snapshotted assignments; workout sessions; weight measurements |
| Experience | habits and date-scoped logs; weekly check-ins/review; contacts/messages; notifications |
| Scheduling | bounded availability/status calendar; per-coach rules; bookings; cancellation |
| Commerce | editable catalog; orders; payment availability/initialization/verification/webhook; scoped subscriptions/invoices |
| CMS | anonymous public content; staff settings; blog publication; validated private/public media |
| Admin | scoped command-center dashboard; super-admin user list, role and activation changes; searchable audit with safe change details |
| Operations | `/health` process health and `/ready` database readiness |

The access token belongs in `Authorization: Bearer ...`. Refresh/logout cookie actions also require `X-CSRF-Token` from the readable `sbf_csrf` cookie and an allowlisted Origin. Never persist the access token in localStorage. Client and coach scoping is enforced in services.

The admin dashboard is `GET /api/v1/admin/dashboard`. Super administrators can list accounts at `GET /api/v1/admin/users` with `search`, `role`, `active`, `limit`, and `offset`; `PATCH /api/v1/admin/users/{id}` accepts authorized `role` and `active` changes. `GET /api/v1/audit` supports `search`, `action`, `resource_type`, `resource_id`, `actor_id`, `date_from`, and `date_to` filters. Staff can request `GET /api/v1/clients?attention=needs_attention` with normal pagination and search.

Calendar clients request `GET /api/v1/bookings/availability?start=<aware ISO>&end=<aware ISO>&include_unavailable=true`. The range must be at most 62 days; each returned item has a UTC start/end, coach, and `AVAILABLE`, `BOOKED`, `BLOCKED`, or `PAST` status. The response includes effective availability rules and timezone. `GET /api/v1/bookings` accepts the same `start`/`end` range with pagination. Staff can read or update coach rules at `GET/PATCH /api/v1/bookings/availability/settings/{coach_id}`; those rules include timezone, weekdays, hours, duration, blocked dates, vacation ranges, booking notice, advance horizon, and cancellation notice. Booking creation revalidates the selected slot on the server; `BOOKING_CONFLICT` means it was taken before confirmation.

`GET /api/v1/exercises/video-upload-policy` exposes the configured maximum bytes and supported MIME types. Staff upload a demonstration with multipart `POST /api/v1/exercises/{exercise_id}/video`, sending `file` and a stable `Idempotency-Key` header for retries. The browser must generate the multipart boundary. The response is the updated exercise with `video_media_id` and `video_url`; `DELETE` on the same path removes the stored demonstration. `UPLOAD_TOO_LARGE` (413), `UNSUPPORTED_VIDEO_TYPE` (422), `STORAGE_UNAVAILABLE` (503), and `IDEMPOTENCY_CONFLICT` (409) have actionable messages. A retry with the same key and file returns the already-attached asset; using a key for a different or retired asset conflicts.

Not every future domain from the master brief is implemented. CRM task/communication history, outbound webhooks, integration OAuth, global multi-domain search and customizable nutrition/check-in builders remain separate work items. Consult IMPLEMENTATION_STATUS.md.
