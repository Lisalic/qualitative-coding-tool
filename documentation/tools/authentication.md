# Authentication

## Purpose

Register an account, log in, and log out. Gates access to every other tool.

## Where to find it

- `/login` → `frontend/src/pages/Login.jsx`
- `/register` → `frontend/src/pages/Register.jsx`
- `/` and any unknown path render `frontend/src/components/auth/AuthGate.jsx`, which shows the authenticated Home page or an anonymous Landing page depending on session state.

Anonymous users see only Login/Register in the sidebar (`frontend/src/components/layout/Sidebar.jsx`); every other route is wrapped in `ProtectedRoute` and redirects to `/login` (carrying `state.from`) if unauthenticated.

## Prerequisites

None. No API key is needed for auth itself.

## Inputs

| Field | Required | Notes |
|---|---|---|
| Email | yes | `type="email"` |
| Password | yes | |
| Confirm Password | yes, register only | client-checked equal to Password before submit |

## What happens on submit

Both forms are direct (non-job) JSON POSTs via the shared `api` axios instance:

- Login: `POST /api/login/` `{email, password}`
- Register: `POST /api/register/` `{email, password}`

On success, both return `{id, email, access_token}` and set an httponly `access_token` cookie server-side. The frontend also stores `access_token` in `localStorage`, sets it on `api.defaults.headers`, dispatches the `auth-changed` window event (picked up by `useAuth.js`, which polls `GET /api/me/`), and navigates to `/` after a short delay (500ms login, 1000ms register).

Logout: `POST /api/logout/` clears the cookie server-side; the frontend removes `localStorage.access_token` and dispatches `auth-changed`.

## Output

No artifact. A valid session (cookie + `localStorage.access_token`) that every subsequent request relies on.

## Troubleshooting

| Symptom | Cause |
|---|---|
| 401 "Invalid credentials" | Wrong email/password on login |
| 400 email-already-registered | Register with an existing email |
| "Passwords do not match" | Register-only client-side check |
| Redirected to `/login` from any tool page | No valid session; `ProtectedRoute` caught it |

## Developer reference

- Frontend: `pages/Login.jsx`, `pages/Register.jsx`, `components/auth/AuthFormSection.jsx` (shared `mode="login"|"register"` form), `components/auth/AuthLinksSection.jsx`, `components/auth/AuthGate.jsx`, `components/auth/ProtectedRoute.jsx`, `components/auth/useAuth.js`.
- Backend: `backend/app/api/auth_routes.py` → password hashing/verification and JWT issuance in `backend/app/auth.py` and `backend/app/api/utils.py`. See [architecture.md#auth](../architecture.md#auth) for the token format and resolution order.
- Endpoints: `POST /api/login/`, `POST /api/register/`, `GET /api/me/`, `POST /api/logout/` — see [api-reference.md](../api-reference.md#authentication--backendappapiauth_routespy).
