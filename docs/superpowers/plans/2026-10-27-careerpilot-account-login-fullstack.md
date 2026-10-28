# CareerPilot Account Login Full-Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build verified-email account authentication end to end, including the FastAPI/SQLite backend and a simple protected desktop web login experience.

**Architecture:** A focused `careerpilot.auth` package owns account/session persistence, password hashing, verification challenges, and SMTP delivery. FastAPI exposes authentication flows and resolves all private endpoint identities from a revocable server-side session instead of the anonymous owner cookie. React bootstraps `/v1/auth/me` once, protects business routes through an auth provider, and renders dedicated login/register pages outside AppShell.

**Tech Stack:** Python 3.12, FastAPI, SQLite, `pwdlib[argon2]`, stdlib `smtplib`/`email`, pytest, React 19, TypeScript, React Router, Vitest

**Spec:** `docs/superpowers/specs/2026-10-27-careerpilot-account-login-design.md`

## Global Constraints

- Desktop web scope: implement login/register and account-menu experiences; do not redesign mobile navigation.
- Registration requires a one-time six-digit email code; success never creates a login session.
- Codes expire after 10 minutes, resend after 60 seconds, allow five attempts, and allow five sends per hour per email/source.
- Passwords use Argon2id and never appear in persistence, API responses, or logs.
- Session cookies are HttpOnly, SameSite=Lax, Secure in production, and never stored in localStorage.
- Non-remembered sessions use a browser-session cookie with a 24-hour server-side absolute lifetime.
- Remembered sessions use a five-day sliding idle lifetime and a 30-day absolute lifetime.
- SMTP production delivery uses a NetEase authorization code; no development bypass may activate in production.
- Existing owner-scoped stores continue to receive a stable UUID, now the authenticated account ID.

## Review Focus

- Concurrent requests for the same username/email must produce one account and consume the code at most once.
- A guessed, expired, invalidated, replayed, or attempt-exhausted verification code must not create an account.
- A copied session lookup ID without its verifier must not authenticate; revoked/expired sessions must clear the cookie.
- Case and surrounding whitespace must not create duplicate usernames/emails or cause inconsistent login behavior.
- SMTP failure must invalidate the challenge and return an error rather than claim the email was sent.

---

### Task 1: Account, Session, and Password Foundation

**Files:**
- Create: `src/careerpilot/auth/__init__.py`
- Create: `src/careerpilot/auth/models.py`
- Create: `src/careerpilot/auth/passwords.py`
- Create: `src/careerpilot/auth/store.py`
- Modify: `src/careerpilot/config.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Test: `tests/auth/test_passwords.py`
- Test: `tests/auth/test_store.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Account`, `AuthSession`, `VerificationChallenge` dataclasses.
- Produces: `PasswordHasher.hash(password: str) -> str` and `verify(password: str, encoded: str) -> bool`.
- Produces: `SqliteAuthStore` account, session, and challenge transaction methods used by later tasks.
- Produces: `Settings.auth_db_path` and SMTP/session timeout configuration.

- [ ] **Step 1: Write failing password and store tests**

Cover Argon2id hashes, valid/invalid verification, case-insensitive uniqueness, concurrent duplicate rejection, verifier-hash-only session storage, atomic challenge consumption, replay rejection, and account/session lookup.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests\auth\test_passwords.py tests\auth\test_store.py tests\test_config.py -q`

Expected: FAIL because `careerpilot.auth` and auth/SMTP settings do not exist.

- [ ] **Step 3: Implement the models, Argon2id adapter, SQLite schema, and configuration**

Use normalized `casefold().strip()` identity columns with unique indexes; generate UUID account/session IDs; store only SHA-256 session verifier hashes and HMAC verification-code values. Add `pwdlib[argon2]` and update the lockfile.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: PASS.

### Task 2: NetEase Verification Mail and Challenge Policy

**Files:**
- Create: `src/careerpilot/auth/mailer.py`
- Create: `src/careerpilot/auth/verification.py`
- Test: `tests/auth/test_mailer.py`
- Test: `tests/auth/test_verification.py`

**Interfaces:**
- Consumes: `SqliteAuthStore`, challenge models, and SMTP settings from Task 1.
- Produces: `VerificationMailer.send_registration_code(recipient: str, code: str) -> None`.
- Produces: `SmtpVerificationMailer` and `VerificationService.request_registration_code(email: str, source_key: str, now: datetime | None = None) -> VerificationDispatch`.

- [ ] **Step 1: Write failing mail rendering and challenge-policy tests**

Assert multipart plain/HTML content, CareerPilot sender/subject, no credential leakage, exactly six random digits, 10-minute expiry, 60-second resend, five-per-hour limits, five attempts, new-code invalidation, and SMTP failure invalidation.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests\auth\test_mailer.py tests\auth\test_verification.py -q`

Expected: FAIL because the mailer and verification service do not exist.

- [ ] **Step 3: Implement the mailer and verification service**

Render a responsive 600px inline-style HTML card plus plain text, use `smtp.163.com:465` SSL by default, authenticate with the configured authorization code, and inject clock/random/mailer dependencies for deterministic tests.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: PASS.

### Task 3: Registration, Login, Current User, and Logout APIs

**Files:**
- Create: `src/careerpilot/auth/service.py`
- Modify: `src/careerpilot/api/schemas.py`
- Modify: `src/careerpilot/api/auth.py`
- Modify: `src/careerpilot/api/app.py`
- Test: `tests/api/test_auth.py`

**Interfaces:**
- Consumes: Task 1 store/hasher and Task 2 verification service.
- Produces: `AuthService.register`, `login`, `authenticate`, and `logout`.
- Produces: `POST /v1/auth/verification-codes`, `POST /v1/auth/register`, `POST /v1/auth/login`, `GET /v1/auth/me`, and `POST /v1/auth/logout`.
- Produces: FastAPI `resolve_identity` returning `Identity(owner_id=account.id, is_anonymous=False)` or HTTP 401.

- [ ] **Step 1: Write failing end-to-end authentication API tests**

Cover send-code metadata, registration without auto-login, username/email login, wrong-password generic errors, bounded repeated login failures, session versus persistent cookie attributes, refresh through `/me`, logout/replay denial, five-day idle expiry, 24-hour/30-day absolute expiry, malformed tokens, inactive accounts, and password/code omission from responses.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests\api\test_auth.py -q`

Expected: FAIL because the endpoints and authenticated session resolver do not exist.

- [ ] **Step 3: Implement the auth service, schemas, routes, and cookie lifecycle**

Issue `careerpilot_session=<id>.<verifier>`; add `Max-Age` only for remembered sessions; renew remembered idle expiry at most hourly; revoke and delete the cookie on logout or rejected stored sessions. Make `create_app` accept injected auth store/mailer/clock dependencies for tests.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: PASS.

### Task 4: Require Authenticated Ownership Across Existing APIs

**Files:**
- Create: `tests/api/auth_helpers.py`
- Modify: `tests/api/test_chat.py`
- Modify: `tests/api/test_actions.py`
- Modify: `tests/api/test_daily_reviews.py`
- Modify: `tests/api/test_documents.py`
- Modify: `tests/api/test_ideas.py`
- Modify: `tests/api/test_memories.py`
- Modify: `tests/api/test_memory_dashboard.py`
- Modify: `tests/api/test_rag_query.py`
- Modify: `src/careerpilot/api/app.py`

**Interfaces:**
- Consumes: authenticated `resolve_identity` from Task 3.
- Produces: `authenticated_client(...)` test helper returning a registered/logged-in client and account ID.
- Produces: 401 protection and unchanged account-scoped behavior for all existing private endpoints.

- [ ] **Step 1: Write failing protection and owner-isolation tests**

Add unauthenticated 401 assertions for chat, dashboard, documents, memories, conversations, runs, and external actions. Add same-origin rejection tests for cookie-authenticated mutating requests. Convert prior anonymous-cookie fixtures to real authenticated sessions and retain two-account isolation assertions.

- [ ] **Step 2: Run the API suite and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests\api -q`

Expected: FAIL while old anonymous assumptions or unprotected endpoints remain.

- [ ] **Step 3: Apply the authenticated dependency consistently**

Remove `read_or_create_identity` and `careerpilot_owner` behavior from private routes. Enforce allowed `Origin` values on cookie-authenticated POST/PATCH/DELETE requests. Keep health/readiness/static delivery public. Keep public knowledge endpoints technically public at the API level, as the spec only requires the frontend to call them after login.

- [ ] **Step 4: Run the API suite and verify GREEN**

Run the Step 2 command. Expected: PASS.

### Task 5: Frontend Authentication State and Protected Routing

**Files:**
- Create: `frontend/src/auth/AuthProvider.tsx`
- Create: `frontend/src/auth/ProtectedRoute.tsx`
- Create: `frontend/src/auth/auth-events.ts`
- Modify: `frontend/src/data/api.ts`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/app/App.tsx`
- Test: `frontend/src/auth/AuthProvider.test.tsx`
- Test: `frontend/src/app/App.test.tsx`

**Interfaces:**
- Consumes: Task 3 authentication API contracts and HttpOnly cookie behavior.
- Produces: `useAuth()` with `account`, `status`, `login`, `register`, `requestVerificationCode`, and `logout`.
- Produces: centralized 401 handling and protected business routes with return-location support.

- [ ] **Step 1: Write failing auth bootstrap and route-protection tests**

Assert startup blocks business rendering until `/me` settles, unauthenticated users go to `/login`, login returns to the intended route, authenticated users cannot remain on login/register, and a later 401 clears auth state without rendering raw data errors.

- [ ] **Step 2: Run focused frontend tests and verify RED**

Run: `npm test -- --run src/auth/AuthProvider.test.tsx src/app/App.test.tsx`

Expected: FAIL because the auth provider, protected route, and API methods do not exist.

- [ ] **Step 3: Implement API types, auth provider, event handling, and route guards**

Keep credentials in HttpOnly cookies, never localStorage. Ensure child pages cannot mount and fetch data until authentication is confirmed.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: PASS.

### Task 6: Simple Desktop Login, Registration, and Account Menu

**Files:**
- Create: `frontend/src/pages/auth/LoginPage.tsx`
- Create: `frontend/src/pages/auth/RegisterPage.tsx`
- Create: `frontend/src/pages/auth/auth.css`
- Modify: `frontend/src/components/layout/AppShell.tsx`
- Modify: `frontend/src/components/layout/app-shell.css`
- Modify: `frontend/src/pages/settings/SettingsPage.tsx`
- Test: `frontend/src/pages/auth/LoginPage.test.tsx`
- Test: `frontend/src/pages/auth/RegisterPage.test.tsx`
- Test: `frontend/src/components/layout/AppShell.test.tsx`

**Interfaces:**
- Consumes: `useAuth()` from Task 5.
- Produces: desktop login/register forms and a top-right account menu with settings/logout.

- [ ] **Step 1: Write failing interaction tests**

Cover username-or-email login, remember-me submission, password visibility, field/server errors, verification-code request and 60-second resend state, successful registration redirect without auto-login, username/email rendering, and logout.

- [ ] **Step 2: Run focused frontend tests and verify RED**

Run: `npm test -- --run src/pages/auth/LoginPage.test.tsx src/pages/auth/RegisterPage.test.tsx src/components/layout/AppShell.test.tsx`

Expected: FAIL because the pages and account menu do not exist.

- [ ] **Step 3: Implement the approved desktop web experience**

Use a centered 420px glass card on the existing warm background, no AppShell before login, no third-party/forgot-password placeholders, and the existing Bobo avatar plus username in the top-right menu after login.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: PASS.

### Task 7: Operational Configuration and Full Verification

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `src/careerpilot/api/auth.py` if cleanup is needed after integration
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: documented NetEase SMTP/auth database deployment configuration and production readiness validation.

- [ ] **Step 1: Write failing production-configuration tests**

Assert production rejects absent SMTP account/authorization code and unsafe cookie configuration, while test/development can inject a fake mailer without secrets.

- [ ] **Step 2: Run focused config tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests\test_config.py -q`

Expected: FAIL until the production contract includes email verification delivery.

- [ ] **Step 3: Document and enforce the production contract**

Document how to enable NetEase SMTP, where to place the newly regenerated authorization code, and all timeout variables without including real credentials. Include `auth_db_path` in readiness path checks.

- [ ] **Step 4: Run backend quality gates**

Run:

- `.venv\Scripts\python.exe -m pytest -q`
- `.venv\Scripts\python.exe -m ruff check src tests`
- `npm test`
- `npm run typecheck`
- `npm run build`

Expected: all tests pass and Ruff reports no errors.

- [ ] **Step 5: Inspect the final diff for secrets and scope**

Verify no authorization code, password, email address, screenshot content, or frontend implementation is present in the diff.
