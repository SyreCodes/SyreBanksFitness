# Premium single-coach upgrade — impact and phase record

## Inspection and implementation plan (6 November 2026)

Baseline: GitHub main `5a704ab`, existing React 19/Vite application, FastAPI/SQLAlchemy services, Alembic, PostgreSQL, private Azure media, Celery, CRM and GitHub/Azure release pipeline. Work continues in the existing production checkout; the original checkout's unfinished commerce work and customer data are preserved.

The reference review covers OneFit's public homepage and the public FlexPass Member store descriptions: https://onefit.fit/, https://apps.apple.com/ca/app/flexpass-member/id6794592537 and https://play.google.com/store/apps/details?id=rw.onefit.flexpass. Reusable UX principles are clear discovery categories, a short explained journey, transparent membership information and consistent mobile navigation. No reference code, photos or branded assets will be reused.

### Change impact

- Retain existing authentication, client records, exercise upload, assigned workout snapshots, tracking, CRM notifications, settings and administrative workflows.
- Replace hard-coded presentation colors with shared tokens; add persisted light/dark/system preference with pre-render initialization and keyboard-accessible controls.
- Enhance public navigation, homepage and existing components. Existing CMS photography remains the preferred source; do not invent a coach likeness, qualifications, testimonials or prices.
- Add public program introductions, filtered discovery, enrollment and product previews through explicit safe serializers. Published training currently exposes full exercises and program workouts to guests; the upgrade must close those paths and direct media URLs, not just remove navigation links.
- Reuse the reviewed unfinished commerce schema (prices, catalog metadata, digital assets and grants) as an additive foundation, validating existing records and old-release writes before deployment. Its unused future-commerce tables remain inactive. No live payment activation, new subscription on application, seed/import, or new paid Azure resources.
- Store program introduction metadata as validated CMS records tied to existing program IDs. Keep media ownership checks and explicit promotional publication separate from exercise/premium media.
- Centralize manual/pilot grants, expiry/revocation, and assignment-specific exercise access. Existing legitimate assignments remain valid; public discovery never includes training snapshots.
- Extend the CRM with a validated enrollment endpoint and own-user history; guest submissions are not claimed by unverified email matching.
- Preserve current Azure image/health/release contracts and backward-compatible migration practices. Validate rollback only in disposable databases; production rollback keeps additive schema.
- Future tenant isolation will require workspace IDs, scoped unique constraints and queries, storage/queue isolation, membership roles and migration of legacy ownership. No marketplace or tenant-management system is introduced now.

### Acceptance record

Implementation follows the twelve phases below. Automated verification uses disposable databases and synthetic accounts, never production seed data. The release remains subject to the GitHub quality gates and the exact Azure release result.

### Manual content needed for a genuine launch

Coach-owned photography and introduction videos, genuine biography/qualifications, published programs, separately configured RWF/USD prices, package terms, product descriptions/previews and approved legal text. Missing content must produce useful honest states; it must not be fabricated. Email remains deferred; admin notifications use the existing in-app notification system.


## Phase results (6 November)

### 1. Design system and themes
Files: `apps/web/src/premium.css`, `styles.css`, `features/theme/`, `components/ui.tsx`, `index.html`, existing public/admin/client/auth/calendar styles.

Completed: shared light/dark tokens, system preference, pre-paint theme selection, persistence, cross-tab updates, blocked-storage fallback, visible public/account controls, responsive forms/cards/modals/navigation and reduced motion. Form labels now reference the correct native control and connect hint/error descriptions.

Verification: theme unit tests; keyboard skip link, system switching and reload persistence in Chromium; automated WCAG A/AA checks in both themes. Existing forms and calendar remain covered by regressions. Manual configuration: none. Automated checks do not replace assistive-technology testing with real users.

### 2. Public navigation, homepage and credibility
Files: `features/public/{PublicSite,HomePage,PublicPages,Sections,content}`, CMS settings schemas/services, `features/admin/Business.tsx`.

Completed: compact mobile menu, public programs/coaching/store/about/pricing links, journey CTA, goal discovery, coaching process, clearly illustrative app preview, consent-gated social proof and editable story/qualifications/methodology/expectations. The public exercise route explains member access; navigation does not advertise a public premium library. Literal newline escapes are normalized for presentation. Authenticated routes are preserved.

Verification: guest browsing, image loading, mobile overflow, CMS save, theme/contrast checks. Manual configuration: replace the clearly credited illustrative training photograph with owner-supplied photography when ready; enter genuine biography and qualifications. No fabricated credentials or client results were added.

### 3. Program discovery
Files: `features/launch/{data,components,PublicLaunch}`, `modules/launch/{routes,services,schemas}`.

Completed: six goal categories, experience/equipment/environment/frequency filters, suitability and commitment details, safe public descriptions. Existing program workouts remain private. Missing coach-configured commitment is shown as unconfirmed rather than invented.

Verification: selection through the real API and browser, guest serialization excludes workouts, legacy assignments remain functional. Manual configuration: publish programs and fill their introduction metadata. The current single-coach UI displays up to 100 programs; server pagination remains available for larger catalogs.

### 4. Short application
Files: `features/launch/Enrollment.tsx`, its tests, launch enrollment schemas/routes, `modules/leads/{models,services}`.

Completed: goal/training/routine/contact steps, preserved session draft with 24-hour expiry, malformed draft recovery, back navigation, optional equipment/obstacle, current consent version, signed-in history and honest request receipt. A program selection leads through its introduction and options before contact submission. The existing private health assessment remains a separate onboarding workflow.

Verification: form progression, draft persistence/expiry, required selections, current consent, application visible in the CRM, authenticated ownership. Guest requests are not attached to accounts simply by matching an email. Manual configuration: review the legal/privacy content and consent version before inviting clients.

### 5. Program introductions and videos
Files: `features/launch/PublicLaunch.tsx`, `features/admin/Launch.tsx`, launch asset/introduction endpoints, migration `0013`.

Completed: cinematic introduction and demonstration players; philosophy, suitability, commitment, support, measurement, expectations and FAQs; admin file upload and introduction editing. Promotional uploads require explicit publication confirmation and are separate from private exercise media.

Verification: content validation, actual video upload/read, introduction journey, admin edit/save, original exercise upload/replacement remains verified. Manual configuration: supply authentic promotional videos and confirm publication rights; absent video has an honest explanatory state.

### 6. Relevant packages and enrollment requests
Files: launch catalog serializers/services, `components.tsx`, `PublicLaunch.tsx`, legacy commerce price synchronization.

Completed: program-scoped packages, independent RWF/USD prices, billing interval/features/support/duration/renewal/cancellation/suitability, enrollment/waitlist/consultation request types, existing CRM and admin in-app notification. No exchange-rate estimate is presented as a charge. Legacy price edits keep the same currency synchronized without overwriting another currency.

Verification: exact program-package match, RWF zero-decimal and USD cent units, admin notification, no order/subscription/grant on application, disabled payment callbacks even when provider credentials exist. Manual configuration: enter and approve each price and commercial term. `LIVE_PAYMENTS_ENABLED` defaults false and must stay false for this phase; launch UI switches cannot activate payments. Email delivery is still deferred.

### 7. Public digital storefront
Files: `features/launch/PublicLaunch.tsx`, `features/admin/Launch.tsx`, launch catalog/resource APIs, `ProductPrice` and `DigitalAsset` models.

Completed: guest/member browsing, featured/category/search filters, descriptions, images, sample previews, separately priced currencies, delivery information, related products and FAQs; admin uploads/manages public samples and private full resources. Purchase CTAs collect launch interest only.

Verification: real admin product and private/PDF sample upload, public storefront/search/category/detail, signed-in discovery, protected full-file delivery, revoke checks. Manual configuration: create products, samples, full files and delivery/terms; no sample products are seeded into production. Guest checkout remains a future inactive boundary. The admin catalog displays the first 100 products; backend pagination is available.

### 8. Backend access and content protection
Files: `modules/commerce/entitlements.py`, `modules/coaching/services.py`, `modules/cms/{routes,services}.py`, launch access endpoints and additive `0012` storage.

Completed: role, ownership, assignment and entitlement checks on the API; scoped manual/pilot grants with reason/expiry/revoke; safe guest serializers; protected exercise and digital files for GET/HEAD/range requests; token version/active-user checks; independent edit authorization. Program grants create immutable assigned snapshots. Expired/revoked access cannot submit workouts. A request-local policy cache avoids resolving the entire membership repeatedly for each exercise in a page.

Verification: guest/no-grant/wrong-program/expired/future/revoked paths, stale media tokens, legacy public-media flags, cross-client isolation, file editing restrictions, preserved legitimate legacy assignments. Manual configuration: intentionally grant legitimate clients the appropriate scope and expiry. Existing third-party video links are governed by the external host; upload premium demonstrations into the private media service for backend enforcement.

### 9. Member mission and navigation
Files: `features/client/{dashboard,mission,MemberExtras,ClientApp}`, `layouts/AppShell.tsx`.

Completed: timezone-aware greeting and scheduled mission, completed/rest states, next session, habit checklist, consistency, latest coach message/review, access status, and Home/Discover/My Plan/Progress/Profile bottom navigation. Desktop tools remain accessible.

Verification: local-day/week boundary tests, numeric/legacy weekdays, previous-week completion, expired assignments, mobile layout and five-link navigation. Existing bookings, messages and check-ins are covered. Manual configuration: assign real training schedules and coach content; no invented progress is shown.

### 10. Workouts, progress and communications
Files: `features/client/{workouts,progress,MemberExtras,types}`, exercise metadata schemas/editors.

Completed: prescribed resistance, prior sets, API-authorized demonstrations, instructions and coach-written alternatives, sticky rest timer, saved sets and completion summary, weekly totals, recent best sets, optional private progress photos and coach reviews. Private file links refresh before expiry during long open sessions. Existing habit, check-in, session, notification, measurement and messaging workflows are retained.

Verification: workout unit/browser save, measurement/check-in/message/booking flows, photo upload and unauthenticated denial, nullable historical resistance handling. Manual configuration: author appropriate alternatives and instructions; statistics clearly use the latest 100 workout sessions, not a claim of all-time records.

### 11. Admin consistency and controls
Files: `features/admin/{Launch,AdminApp,Business,Programs,ExerciseEditor,Dashboard}`, shared styles.

Completed: Offers & access sections for introductions/catalog/grants/launch flags; program publication control, full video-file upload/replacement, story/theme settings; existing administrative modules preserved. Flags can pause enrollment, discovery or digital-store launch independently. The API remains the authority for access.

Verification: all existing admin module pages load, users/account history, CMS save, introduction edit, product asset/price save, grant/revoke with no paid membership, light/dark WCAG checks. Manual configuration: use the owner guide below; keep the app single-business.

### 12. Regression, migration, security and release

Verified locally: 162 API tests with PostgreSQL (including concurrent outbox delivery); 53 frontend unit/component tests; Ruff and mypy (76 source files); TypeScript and ESLint; production web build; 24 Azure release unit tests. All 13 browser acceptance cases passed locally (the final registration assertion was corrected and rerun separately); the full CI run will repeat them together. WCAG A/AA automated scans passed on 14 public/client/admin pages in both light and dark themes.

Migration checks: SQLite legacy rows and old-release writes; isolated PostgreSQL upgrade to `0013`, schema comparison, downgrade to `0011`, re-upgrade and comparison. Production rollback keeps additive columns/tables in place: revert the application image, never automatically run a database downgrade. Previous API/worker writes retain compatible defaults.

Security: current production npm audit reports zero vulnerabilities after compatible Zod/Vite patch updates. Nine moderate advisories remain in development-only lint/test dependency chains; npm proposes a breaking/downgrade solution for part of that chain, so no forced toolchain replacement was applied. No credentials, local databases or uploaded media are committed. The environment's Starlette/httpx test-client deprecation warning is non-failing.

Limits: these acceptance checks do not certify 1,000 simultaneous Azure users. Existing budget/replica limits are unchanged, and paid capacity upgrades remain deferred. The external MCAPS subscription shutdown policy and email delivery remain separate operational limitations documented in the Azure handover.

### Current compatibility notes

Legacy subscription and invoice records remain usable. Existing explicit coach program assignments remain access grants until their status ends. Manual program grants create a separate immutable assignment; revoking a grant does not delete history or revoke another valid source of access. Training videos previously flagged public are now protected at request time. External video links cannot be made private on a third-party host; upload premium files to the existing private media service. Payment provider contract tests explicitly enable the test-only flag; production defaults remain disabled.


## Owner configuration guide

1. Sign in as administrator and open **Content**. Add your real story, credentials, photography, contact details and approved legal copy. Existing records remain editable.
2. Open **Programs** to build/publish a real training plan. Open **Offers & access → Introductions** to attach its public cover/introduction/demo files and explain suitability, commitment, support and expectations.
3. In **Offers & access → Catalog**, create a coaching or membership offer, choose the relevant program(s), configure RWF and USD independently, and enter commercial terms. Choose enrollment open or waiting list. These controls collect interest and do not charge anyone.
4. For a digital product, choose **Digital product**, category, public cover/sample and private full resources. Explicitly confirm publication only for previews. Set publication to Published when its description and terms are ready.
5. Review submitted requests in **Leads** and the existing in-app notifications. Guest requests remain CRM records; requests submitted while logged in also appear in that client's Profile.
6. Use **Access** to find a client and issue a scoped, expiring manual/pilot grant with a reason. Revoke there when appropriate. A program grant creates an assignment; a digital grant reveals the private resources in Profile. Existing coaching assignments remain valid independently.
7. Use **Launch settings** to pause unfinished public discovery/store/enrollment. Select theme in the public header or account settings. Theme preference is per browser, not a tenant branding setting.

## Future workspace isolation

Before supporting multiple independent coaches, introduce a workspace entity and explicit workspace membership roles. Add/backfill workspace IDs to clients, catalog, programs, grants, CMS, CRM, communications, orders and jobs. Scope every read/write/unique constraint and object-storage path to the workspace; validate referenced IDs in the same workspace; partition queued jobs and cache keys. Add cross-workspace denial tests, audit ownership migration, and separate platform operators from workspace admins. Current admin roles intentionally operate the single Syre Banks business and must not be sold as isolated tenant administration.

## Release checkpoint

On 12 November 2026, the owner reactivated the Azure subscription after live management reported it Disabled. PostgreSQL, the API, worker, DNS and HTTPS subsequently recovered. No resource rebuild, data import, production seed or paid capacity upgrade was performed.

Release `baf2bffa0cb4cafc36c72db2f32c8b602c89d148` completed successfully in [GitHub run 43156403330](https://github.com/SyreCodes/SyreBanksFitness/actions/runs/43156403330) at 06:49 Kigali time. All quality gates passed together: 162 API tests, 53 frontend tests, 13 browser acceptance cases, 24 release tests, lint/type/build checks and production-image smoke. Production migration `job-syrebanks-migrate-10l1gpj` and scheduled check `job-syrebanks-outbox-ayl1f0h` succeeded. Azure pinned 100% of API traffic to the new revision and retired the old active revision.

Post-release checks passed on https://ubuntustar.com: readiness/database/Redis, administrator login/profile/secure-cookie refresh/logout, public catalog/config, disabled live payments, guest denial for restricted content, mobile layouts, persisted themes and all four Offers & access sections. The saved homepage image was switched from the old Azure hostname to the existing bundled image on UbuntuStar.com, with the original stock-photo attribution restored. No customer or catalog records were created for production verification.

The final visual walkthrough found remaining escaped newlines in shared public-page headings. This follow-up normalizes those headings and the legacy application confirmation, and expands browser coverage to Coaching, FAQ, Journal and Contact. Its hosted outcome and any further continuation commands are recorded in the local handover at `artifacts/premium-upgrade/CONTINUE.md` in the original workspace. Automatic release remains enabled; a passing source check alone does not prove a newer commit is deployed.
