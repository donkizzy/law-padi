# Accounts and sign-in plan

Status: approved 2026-10-16. Phases 0–3 and 5 are built; production email
delivery is still open and Google sign-in (Phase 4) is deferred. The "What
already exists", "Gaps" and "Changes by area" sections describe the starting
point when the plan was written, not the current code; the session design as
built is summarised in [`../architecture.md`](../architecture.md#accounts-and-sessions).

## Goal

Accounts stay optional. Anyone can ask questions and browse the Constitution as a
guest. An account adds what a guest can't keep: conversation history across
devices, saved provisions everywhere, and settings that follow the person.

## What already exists

The FastAPI template auth is wired end to end, but only at template quality:

- **Backend.** `POST /login/access-token` issues an 8-day JWT (`ACCESS_TOKEN_EXPIRE_MINUTES`).
  `POST /users/signup`, `GET/PATCH/DELETE /users/me`, `PATCH /users/me/password`,
  `POST /password-recovery/{email}` and `POST /reset-password/` are in place.
  Conversations already support both owners: `user_id` or `anonymous_session_id`.
  `POST /conversations/claim` moves guest conversations onto the signed-in account.
- **Frontend.** `/login`, `/signup`, `/recover-password` and `/reset-password` routes exist.
  `useAuth` keeps the JWT in `localStorage`. `isLoggedIn()` only checks that a token
  is present. Any 401 or 403 clears the token and does a hard redirect to `/login`.
  The sidebar shows "Sign in / Create account" to guests and an import button for
  guest chats.
- **Deployment.** The Cloudflare worker proxies `/api/*` to Render on the same origin,
  so first-party cookies are possible. Password-recovery email isn't configured in
  production yet.

## Gaps

1. The token sits in `localStorage` for 8 days. Any XSS can read it, and it can't be revoked.
2. `isLoggedIn()` treats an expired token as signed in. The visitor sees the app shell
   until the first API call fails, then gets bounced to `/login`.
3. Sign-up doesn't verify the email address, and production has no email delivery.
4. Login, sign-up and password recovery have no rate limits.
5. After signing in, the visitor always lands on `/`. They don't go back to where they were.
6. Guest data doesn't follow the visitor automatically. Conversations need a manual
   import, and saved provisions never leave the browser.
7. There's no Google sign-in. Many target users are on Android with a Gmail account.
8. The Nigeria Data Protection Act 2023 needs a privacy notice, consent wording,
   account deletion (the API exists, the UI should be checked) and a data export.

## Phases

### Phase 0: Landing behaviour (done)

- Guests who land on the bare `/` URL are redirected to `/welcome`.
- Signed-in visitors, deep links (`/?q=…`, `/?c=…`, `/?intent=ask`) and navigation
  inside the app go straight to the app.
- Code: `frontend/src/lib/landing.ts`, the `beforeLoad` in `frontend/src/routes/_layout/index.tsx`.

### Phase 1: Session hardening (done)

Built as planned, with these specifics:

- Access tokens last 15 minutes and refresh cookies 30 days (sliding).
  The cookie is named `constitution_session`.
- A rotated token presented again within 10 seconds is refused without revoking
  the family, so two tabs refreshing at once don't sign each other out.
- Tabs share one refresh through `navigator.locks`. Signing out in one tab ends
  the session in the others through a `BroadcastChannel`.
- Changing your password signs out every other device. An admin resetting a
  password or deactivating an account signs out all of that user's devices.
- Invalid or expired access tokens now get 401 instead of 403, so 403 only means
  "not allowed".
- Old `localStorage` tokens are deleted on load rather than honoured for a release,
  so existing accounts sign in once more.


- Replace the long-lived bearer token with:
  - a short-lived access token (about 15 minutes) kept in memory;
  - a rotating refresh token in an `HttpOnly; Secure; SameSite=Lax` cookie, scoped to `/api/v1/login`.
- Backend:
  - add a `refresh_token` table (hashed token, user, expiry, `revoked_at`, rotation family);
  - add `POST /login/refresh` and `POST /logout`;
  - if a refresh token is reused, revoke its whole family.
- Frontend:
  - add an `AuthProvider` that calls refresh once on boot;
  - expose `status: "unknown" | "guest" | "signed-in"`;
  - make `isLoggedIn()` read that status;
  - on a 401, retry once after a refresh, and only then drop to guest. No hard redirect.
- Keep reading the old `localStorage` token for one release, then remove it.
- Tests:
  - refresh rotation and reuse detection (pytest);
  - an expired session falls back to guest (Playwright).

### Phase 2: Sign-up and recovery that work in production (built; email delivery pending)

Built, with these specifics:

- Every signed token carries a `type` claim (`access`, `password-reset`,
  `email-verification`), so a link token can never be used to sign in.
  Reset links sent before this change stop working.
- `User.email_verified_at`. Accounts that existed before this change are marked
  verified by the migration. Changing your email clears it and sends a new link.
  Completing a password reset sets it.
- `POST /users/verify-email` and `POST /users/me/verification-email` (resend). Links
  are tied to the address they were sent to and last 48 hours. The `/verify-email`
  page confirms the address, and Settings shows a notice with a resend button until it's confirmed.
- Sign-up always answers "Check your email to confirm your address, then log in."
  If the address already has an account, its owner gets an "account exists" email instead.
- Postgres fixed-window rate limits (`rate_limit_counter`), keyed by hashed IP, email or user:

  | Action | Limit |
  | --- | --- |
  | Login | 50 per IP and 10 per IP+email, per 15 minutes |
  | Refresh | 120 per IP per 15 minutes |
  | Sign-up | 10 per IP per hour |
  | Recovery | 10 per IP and 3 per email, per hour |
  | Reset | 10 per IP per hour |
  | Verify | 20 per IP per hour |
  | Resend | 3 per user per hour |

  Over the limit returns 429 with `Retry-After`. The client IP comes from
  `X-Forwarded-For` only when `ORIGIN_PROXY_SECRET` is set, because only the
  Cloudflare worker can reach the API then.
- `?redirect=` on `/login` and `/signup`. It's resolved like a browser would and
  only followed when it stays on this origin and isn't an auth page.
- **Still to do:** pick an email provider and set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
  `SMTP_PASSWORD`, `EMAILS_FROM_EMAIL` and `PROJECT_NAME=constitution.ng` on Render.
  Until then, sign-up works but no email is sent, and resend answers 503.


- Configure SMTP (or a transactional provider) on Render and set `EMAILS_FROM_EMAIL`.
- Email verification:
  - add `email_verified_at` to `User`;
  - sending a verification link only needs a signed token, which the template can already generate.
- Unverified accounts can still use everything a guest can. Syncing waits until the email is verified.
- Add rate limits to login, sign-up, recovery and refresh. Key them by IP plus email.
  Use Postgres or the Cloudflare worker, so the stack doesn't gain Redis.
- Make account-enumeration-safe responses consistent across recovery and sign-up.
- Add a `?redirect=` search param to `/login` and `/signup`. Validate it as an
  internal path only.

### Phase 3: Guest to account continuity (done)

Built, with these specifics:

- `saved_provision` and `user_preferences` tables, under `/account/saved-provisions`
  (list, put, delete, merge) and `/account/preferences`. Every account route,
  and `/conversations/claim`, needs a confirmed email (403 otherwise). An account
  can keep up to 2,000 saved sections.
- `lib/account-sync.ts`: the browser's local stores stay the copy the UI reads.
  - The first sync for an account on a browser claims guest chats, merges that
    browser's bookmarks into the account, and takes the account's preferences
    (or uploads the browser's if the account has none).
  - After that, each load refreshes the browser from the account, and each
    change is sent as it happens.
  - Signing out clears the mirrored copy. Expiry or signing out in another tab
    stops sync without clearing.
- The manual "Bring guest chats into this account" button is gone. Claiming
  happens automatically and shows "Your N chats are now in your account."
- Copy now says where things live. The Saved page invites guests to sign in and
  unconfirmed accounts to confirm their email. Toasts no longer say "on this browser".


- After sign-in or sign-up, call `POST /conversations/claim` automatically. Then show
  one toast, for example "Your 3 chats are now in your account." This replaces the manual import button.
- Account-synced saved provisions:
  - add a `saved_provision` table: user, provision id, release, created time;
  - add CRUD endpoints;
  - make `useSavedProvisions` read from the server when signed in, and merge the
    local bookmarks once on first sign-in.
- Sync workspace preferences (Enter-to-send, answer style) to the account the same way.
- Syncing (conversations, saved provisions, preferences) turns on only after the email is verified.
- Ask for an account only where it helps: when saving a provision, at the
  third conversation, or when opening history on a new device. Keep the prompt soft and dismissible.

### Phase 4: Google sign-in (deferred)

- Add OAuth 2.0 / OIDC with Google using authlib or a hand-rolled PKCE flow.
- Link the Google identity by verified email to an existing account.
- Add a `user_identity` table: provider, subject, user.
- Put a "Continue with Google" button on `/login`, `/signup` and the welcome page.

### Phase 5: Privacy and account management (done)

Built, with these specifics:

- `GET /account/export` downloads profile, preferences, saved sections and every
  conversation with its messages. It's available to any signed-in account,
  confirmed or not. Settings → Security has a "Your account data" card with
  "Download my data" and "Delete my account" (with a confirmation step; this
  replaces the template's delete dialog). Deleting cascades to conversations,
  saved sections, preferences and sessions.
- `/privacy` covers:
  - what's kept and why;
  - who else handles it (Cloudflare, Render, Neon, DeepSeek, the email provider);
  - how long things are kept;
  - rights under the NDPA 2023, with a link to the NDPC.

  It's linked from the welcome footer, the sign-up form and Settings. A contact
  address appears only if `VITE_PRIVACY_CONTACT_EMAIL` is set.
- `GUEST_CONVERSATION_RETENTION_DAYS` (30) drives the guest cookie, the
  visibility cutoff and claiming. `app/retention.py` deletes idle guest
  conversations in batches, skipping any with a run in progress. With no cron
  on the free plan, about 2% of new conversations trigger a batch.
  `python -m app.retention` runs it on demand.
- All emails are now sent after the response (FastAPI background tasks), so SMTP
  never slows or reveals anything about sign-up or recovery.
- **Still to do:** set `VITE_PRIVACY_CONTACT_EMAIL`, and have the privacy notice
  reviewed before public launch.


- Settings: download my data (JSON of conversations and saved provisions) and
  delete my account, with a confirmation step.
- Add a privacy notice route linked from sign-up and the welcome footer. It should
  cover what's stored, why, for how long, and the NDPA rights.
- Retention: purge guest conversations after 30 days with no activity. Revoke
  refresh tokens on password change.

## Changes by area

| Area | Files |
| --- | --- |
| Models and migrations | `backend/app/models.py`, `backend/app/alembic/versions/` (refresh tokens, email verification, saved provisions, identities) |
| API | `backend/app/api/routes/login.py`, `users.py`, a new routes module for saved provisions (built as `account.py`), `backend/app/api/deps.py` |
| Client | regenerate `frontend/src/client/` with `bash scripts/generate-client.sh` |
| Frontend auth | `frontend/src/hooks/useAuth.ts`, `frontend/src/main.tsx` (error handling), new `AuthProvider` |
| Routes | `login.tsx`, `signup.tsx` (redirect param), `_layout/settings.tsx`, `_layout/saved.tsx` |
| Emails | `packages/react-email/` (verify-email template), not the generated HTML |
| Deployment | `render.yaml` / `deployment/render/prepare_env.py` (SMTP and cookie settings) |

## Decisions (2026-10-16)

1. Token storage: short-lived in-memory access token plus a rotating `HttpOnly` refresh cookie.
2. Google sign-in: not for now. Phase 4 is deferred.
3. Email: verify the address before syncing turns on. The production email provider is still to be chosen.
4. Preferences sync to the account.
5. Guest conversations are purged after 30 days with no activity.
