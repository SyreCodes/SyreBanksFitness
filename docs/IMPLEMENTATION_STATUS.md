# Implementation status — 5 October 2026

## Completed

- The existing React/Vite public site, application flow, client portal, and coach/admin workspace remain connected to the FastAPI domain APIs. This sprint changed the calendar and exercise-media workflows within that architecture.
- Admin and client booking pages share a conventional calendar with month, week, and day views; previous/Today/next navigation; a Sunday-first month grid; timed week/day event blocks; status text and legend; and a compact month plus selected-day agenda on mobile. Available slots open a booking confirmation showing coach, date, start/end times, duration, timezone, and meeting method. Successful bookings refresh the calendar immediately.
- The scheduling API supports bounded calendar date ranges, available/booked/blocked/past slot states, coach-specific availability settings, blocked dates, vacation ranges, minimum notice, maximum advance range, duration checks, cancellation cutoffs, and UTC responses. Booking creation locks coach and client rows on PostgreSQL and rejects overlapping sessions. The existing available-only 14-day endpoint behavior remains usable for callers without range parameters.
- Admin exercise editing accepts local MP4, WebM, and MOV files. It shows the configured limit, selected-file details and preview, current-video playback, replace/remove actions, upload progress, processing state, cancellation, and clear errors. If the exercise details save but the video fails, Retry Upload sends only the retained file with the same idempotency key.
- Uploaded video replacement stores the new object and commits its media attachment before retiring the old object. A failed upload leaves the existing demonstration intact. Exercise lists load metadata only; playback loads on demand.
- Video upload uses a configurable `VIDEO_MAX_UPLOAD_MB` limit (100 MB by default), MIME and file-signature checks, bounded reads, streamed local/S3 storage through the provider abstraction, idempotency records, and structured failure logs without secrets.

## Fixed

- Host-run API uploads failed because `.env` pointed `MEDIA_ROOT` to Docker's `/app/private-media`. Host development now uses a writable local media path; Docker Compose retains its mounted `/app/private-media` path.
- Oversized, unsupported, unavailable-storage, and idempotency-conflict uploads now return structured 413/422/503/409 errors that the editor explains in plain language. The browser creates the multipart boundary and sends authentication, CSRF, and idempotency headers.
- Admin session creation no longer assumes a hardcoded Kigali UTC offset. Both calendar pages send timezone-aware published slot timestamps from the API.
- Browser acceptance checks for public pricing now compare displayed prices with the editable product API instead of assuming the seed price remains unchanged.

## Tested

- Backend: **72 pytest tests passed**, including upload success/failure/replacement/idempotency and booking rules, HTTP routes, timezone behavior, and simultaneous booking attempts. Ruff and Mypy passed. These tests used local SQLite; production PostgreSQL behavior remains to be verified in deployment.
- Frontend: **41 Vitest tests passed**; TypeScript typecheck, ESLint, and the Vite production build passed.
- Browser: **7 Playwright tests passed** in installed Chrome against the local API and web app. They cover desktop/mobile routes, booking and dashboard refresh, an MP4 upload and replacement surviving reloads, and existing public/admin/client flows. The new booking and video journeys also reported no browser console errors or uncaught page errors.
- Alembic revision **0011** for upload idempotency passed on fresh SQLite and was applied to the existing local database after a backup. Local media upload and playback were verified through the browser.

## Known limitations

- S3-compatible storage still receives uploads through the API. Direct presigned browser-to-object-storage uploads, video transcoding, thumbnails/posters, and durable asynchronous processing states are future work. The current API attaches media only after a complete storage write. Production reverse-proxy body limits, timeouts, temporary disk capacity, and S3 credentials must be configured and verified before deploying 100 MB uploads.
- The new coach availability rules can be managed through staff API endpoints. A dedicated admin form for editing per-coach hours, blocked dates, and vacations is not yet present.
- PostgreSQL concurrency, Redis, S3, SMTP, merchant payment flows, and other deployed integrations have not been exercised in this local SQLite environment. Live payment checkout and recurring billing still depend on provider setup and verification.
- Marketing media uploads still need consent provenance for arbitrary uploaded images. Broader CRM search, analytics, and settings features from the master brief remain planned.

## Next recommended improvements

1. Run the same booking race and video replacement tests against a staging PostgreSQL/S3 deployment, then load-test upload size and proxy timeout settings.
2. Add a staff availability editor for coach working hours, blocked dates, vacations, notice, and cancellation policy.
3. Add a presigned direct-upload and confirmation flow if production video traffic grows; add transcoding/posters only when the hosting and playback requirements justify it.
4. Complete provider-backed payment, email, and production infrastructure acceptance before launch.
