# AutoHR

A Pakistan-localized hiring workspace for HR teams. Django serves the marketing landing page, **real signup/sign-in**, and a protected HR dashboard.

**Pipeline:** Create Job (PostgreSQL + **Groq AI** job description) → **Google Form** application link → CV scoring & shortlist → **interview invitations emailed through the HR user's Gmail** → candidate self-scheduling + consent → **3-stage AI interview** → final rankings with HR override.

**Access:** There is **no demo workspace**. `/dashboard/` and all job APIs require a signed-in HR user. Public routes are `/`, `/login/`, `/register/`, and the candidate's personal `/interview/<token>/` link.

## Current step (where the build is now)

| Pipeline phase | Status | Notes |
| --- | --- | --- |
| **Auth — Google sign-in** | Done | One button; new users provisioned in PostgreSQL; verified Google email required |
| **Auth — sessions** | Done | Django session per device; list/revoke under **Account → Signed-in devices** |
| **1 — Job intake (form A–G)** | Done | Validate on server, save `job_postings` + `job_responsibilities` |
| **2 — AI job description (Groq)** | Done | Same-page stepper step 2; `ai_generated_jd_draft`; formatted preview + edit |
| **3 — HR finalize description** | Done | `approved_jd_content` |
| **4 — Create Google Form + link** | Done | Form created via Google Forms API; URL inserted after `Apply Here:` |
| **4b — Form response sync** | Done | **Automatic** background sync every `FORM_SYNC_INTERVAL_SECONDS` (default 300) + manual Sync button |
| **5 — CV scoring & shortlist** | Done | Groq scoring with per-job weights; manual Shortlist/Reject |
| **6 — Interview invitations** | Done | Magic link **emailed via Gmail API** (Profile → Integrations → Gmail); copyable link shown if email fails |
| **7 — Scheduling + consent gate** | Done | Candidate picks an offered slot; mandatory recording + AI consent |
| **8 — AI interview (3 stages)** | Done | Room opens 15 min before the slot; one answer per question; stages in order |
| **9 — Final rankings** | Done | Interviews panel → **Final Rankings** (CV 40% + interview 60%), HR override verdict + notes |
| **Publish to job boards** | Not started | Rozee / Indeed / LinkedIn |
| **Profile wizard + integrations** | In progress | 7-step wizard UI + step APIs; Gmail/Workspace/Calendar OAuth |

## Interview integrity rules

- Invitations: only **shortlisted / invited / scheduled (not started)** candidates can be (re)invited. Re-sending keeps the same active link; once the candidate has started, re-inviting is refused.
- Scheduling: only slots the portal offers (office hours, `TIME_ZONE` = Asia/Karachi) are accepted; no rescheduling after the interview starts.
- Room: requires a valid, unexpired link + consent; opens `INTERVIEW_ROOM_EARLY_ACCESS_MINUTES` (15) before the slot; a completed interview cannot be reopened.
- Answers: one submission per question; stages must be completed in order and every question answered. Unanswered questions score **0**.
- Candidates are stored **per company** (`candidates.company_id`), so one company's edits never show up in another's dashboard.
- CVs and interview recordings under `/media/` are served **only to signed-in HR of the owning company**.

## Authentication

AutoHR uses **Google only**. There is no email/password login, OTP, or SMTP.

### Sign up / Sign in (`/login/`, `/register/`)

1. Click **Continue with Google** (same flow for new and returning users).
2. Google returns a **verified** email and account id (`users.google_sub`).
3. **New users:** placeholder `companies` row + `users` row + profile setup record.
4. **Existing users:** matched by `google_sub`, or by email (links `google_sub` on first Google sign-in).
5. Django creates a **session cookie** (14-day sliding window, httpOnly). Each browser/device is a separate session.

### Multi-device sessions

- **Account → Signed-in devices** lists active sessions (label, last active, IP).
- **Sign out** on one device or **Sign out other devices** without affecting the current browser.
- Revoking deletes the server-side Django session for that device.

### Account deletion

- **Account → Delete account** — type `DELETE` and your account email (no email OTP).

### API routes (auth)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/auth/google/start/` | Redirect to Google (optional `?next=/path`) |
| GET | `/auth/google/callback/` | OAuth callback (do not open manually) |
| POST | `/auth/logout/` | JSON logout |
| GET | `/logout/` | Logout redirect to home |
| GET | `/account/api/sessions/` | List devices |
| POST | `/account/api/sessions/revoke/` | Revoke one session (`session_id`) |
| POST | `/account/api/sessions/revoke-others/` | Revoke all other sessions |

**Code:** `backend/portal/google_auth_views.py`, `auth_services.py`, `auth_backend.py`, `session_services.py`; UI: `frontend/templates/auth.html`.

### Google Cloud setup (required)

1. Open [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**.
2. **Create credentials** → **OAuth client ID** → type **Web application**.
3. **Authorized JavaScript origins:** `http://127.0.0.1:8000` (add your production origin later).
4. **Authorized redirect URIs** (both required):
   - `http://127.0.0.1:8000/auth/google/callback/` — sign-in
   - `http://127.0.0.1:8000/integrations/google/callback/` — profile integrations (Forms/Sheets/Drive)
5. Copy **Client ID** and **Client secret** into `.env`.
6. OAuth consent screen: add scopes for sign-in (email, profile, openid). For integrations, also enable Google Forms/Sheets/Drive APIs when you use the profile wizard.
7. Generate `TOKEN_ENCRYPTION_KEY` (Fernet) for stored integration refresh tokens — see `.env.example`.

Run after pulling auth changes:

```powershell
cd backend
python manage.py migrate
python manage.py ensure_profile_schema
```

`ensure_profile_schema` applies SQL under `database/migrations/` (including `users.google_sub`).

## Pages

| Route | Access | What you can do |
| --- | --- | --- |
| `/` | Public | Marketing; redirects to dashboard if already signed in |
| `/login/` | Public | Sign in (redirects to dashboard if already signed in) |
| `/register/` | Public | Sign up with Google (same as login) |
| `/dashboard/` | **Login required** | HR workspace (panels below) |

Sign-in and registration share one template; both use **Continue with Google**.

### Landing page

- Product story, pipeline, scoring rubric, technology section
- CTAs: **Get Started** → register, **Sign in to workspace** → login (no dashboard demo link)

### Registration (current UI)

- **Continue with Google** only; a **minimal company** row is created for new users. Full onboarding is the in-app profile wizard ([spec](docs/auth_onboarding_integrations.md)).

### Dashboard (signed-in only)

Sidebar panels on one screen; header has **New Job**, notifications placeholder, and HR chip from **your** DB user.

| Section | What it shows today |
| --- | --- |
| Dashboard | KPIs derived from your job count; other metrics **0** / placeholders until modules ship |
| Jobs | **PostgreSQL** postings for your company (empty state if none) |
| Create Job | Full intake → Groq JD → finalize (see below) |
| Applications | Empty state — not wired to DB yet |
| Pipeline | Empty state — not wired to DB yet |
| Interviews | Empty state — not wired to DB yet |
| Reports | Placeholder stats — not wired to DB yet |
| Account | **Your** HR + company fields from PostgreSQL |

### Create Job (PostgreSQL + Groq)

Three-step stepper on one page:

| Step | UI label | What happens |
| --- | --- | --- |
| 1 | Job Details | Intake form (sections A–G), **Generate Job Description** |
| 2 | AI Job Description | Groq draft, preview / edit, retry |
| 3 | Publish to Boards | **Post Create Google Form** saves finalized text (automation next) |

Requires **sign-in**. Data is scoped to the logged-in user’s company.

Intake groups **A, B, C, D, E, G** (basic info, experience/education, skills, salary/benefits, responsibilities, shortlisting/tone). Tooltips on labels; live preview on the right.

**Generate Job Description:**

1. Server validates (`JobIntakeForm`); errors stay on step 1.
2. Save to **`job_postings`** + **`job_responsibilities`** (`draft`).
3. **Groq** in the same request (`GROQ_API_KEY`, `GROQ_MODEL` in `.env`; default `openai/gpt-oss-120b` in `.env.example`). Logic: **`backend/portal/groq_jd.py`**.
4. Step 2 shows formatted draft in **`ai_generated_jd_draft`**; ends with **`Apply Here: `** (URL later).
5. **Retry:** `POST /dashboard/jobs/<uuid>/generate-jd/`
6. **Post Create Google Form:** writes **`approved_jd_content`**

| Column | Purpose |
| --- | --- |
| `ai_generated_jd_draft` | AI output from Groq |
| `approved_jd_content` | HR-finalized description |

**Job API routes (login required):** `POST /dashboard/jobs/create/`, `POST /dashboard/jobs/<uuid>/generate-jd/`, `POST /dashboard/jobs/<uuid>/prepare-google-form/`

**Code:** `backend/portal/forms.py`, `services.py`, `groq_jd.py`, `models.py`, `session_user.py`, `frontend/templates/partials/create_job_panel.html`, `frontend/static/js/create_job.js`, `frontend/static/css/dashboard.css`

## Demo mode removed

Previously, the app used **`ensure_demo_hr()`** and **`portal/data.py`** so anyone could open the dashboard and see fake jobs/candidates. That is **removed**:

- No auto-login as Northbridge / Ayesha Khan
- No fallback fake job list
- No demo auth redirect in `main.js`
- Anonymous **`/dashboard/`** → redirect to **`/login/?next=/dashboard/`**

## Project layout

```text
AutoHR-N/
├── README.md
├── .env.example              # copy to .env (repo root; gitignored)
├── .gitignore
├── backend/                  # Django API + business logic
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/               # settings, URLs, WSGI, middleware
│   └── portal/               # views, auth, models, Groq, services
├── frontend/                 # templates + static (may show as Frontend on Windows)
│   ├── templates/
│   └── static/
├── database/
│   ├── schema.sql
│   └── ARCHITECTURE.md
├── docs/
│   └── auth_onboarding_integrations.md
└── scripts/
    └── run-dev.ps1
```

Settings: **`backend/config/settings.py`**. Secrets: **`.env`** at repo root (`POSTGRES_*`, `GROQ_*`, `DJANGO_SECRET_KEY`, `GOOGLE_OAUTH_*`, `TOKEN_ENCRYPTION_KEY`). Candidate emails go through the **Gmail API** (no SMTP).

## Run it locally

Requirements: Python 3.11+, PostgreSQL with **`autohr_n`** schema, **Groq API key**, a Google OAuth client, venv at **`backend/.venv`**.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py ensure_profile_schema   # applies database/migrations/*.sql (idempotent)
python manage.py runserver
```

Run the verification suites from the repo root, for example `backend\.venv\Scripts\python.exe scripts\verify_audit_fixes.py`
(also `scripts\verify_interview_sprint1.py`, `scripts\verify_interview_sprint2.py`, `scripts\verify_google_form_sync.py`, `backend\scripts\verify_cv_scoring.py`).

Or from repo root: **`.\scripts\run-dev.ps1`**

Open:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/register/
- http://127.0.0.1:8000/login/
- http://127.0.0.1:8000/dashboard/ (after login)

Hard-refresh (**Ctrl+Shift+R**) after CSS/JS changes. Dev responses use `Cache-Control: no-store`.

## Database

| Item | Value |
| --- | --- |
| Database | `autohr_n` |
| Schema script | `database/schema.sql` |
| Reference | `database/ARCHITECTURE.md` |
| Connection | `POSTGRES_*` in `.env` |

Django uses unmanaged models in **`backend/portal/models.py`**. **`job_postings`** / **`job_responsibilities`** are written by Create Job; auth uses **`users`** / **`companies`**.

## Secrets (`.env` at repo root)

Copy **`.env.example`** → **`.env`**. Never commit `.env`.

```text
DJANGO_SECRET_KEY=...
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=autohr
POSTGRES_PASSWORD=...
POSTGRES_DB=autohr_n
GROQ_API_KEY=...
GROQ_MODEL=openai/gpt-oss-120b
GOOGLE_OAUTH_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-...
GOOGLE_AUTH_REDIRECT_URI=http://127.0.0.1:8000/auth/google/callback/
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/integrations/google/callback/
TOKEN_ENCRYPTION_KEY=...   # Fernet key for integration tokens
DJANGO_DEBUG=true          # set false on a real server (then SECRET_KEY + TOKEN_ENCRYPTION_KEY are required)
DJANGO_ALLOWED_HOSTS=      # required when DJANGO_DEBUG=false
FORM_SYNC_INTERVAL_SECONDS=300
GROQ_MAX_TOKENS=           # optional cap if your Groq plan limits output tokens per minute
```

### Deploying (DJANGO_DEBUG=false)

- HTTPS-only cookies, HSTS and HTTPS redirect switch on automatically.
- Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`; set `TRUST_X_FORWARDED_FOR` / `DJANGO_BEHIND_HTTPS_PROXY` only behind your own proxy.
- With several web processes, set `FORM_SYNC_INTERVAL_SECONDS=0` and run one worker: `python manage.py sync_google_form_responses --interval 300`.

`settings.py` loads `.env` with **`override=True`**. Restart **`runserver`** after edits.

## Front-end notes

- Bootstrap 5.3, Bootstrap Icons, Plus Jakarta Sans, AOS (CDN)
- **`frontend/static/js/main.js`** — tooltips, counters, password visibility, auth panel toggle
- **`frontend/static/js/auth.js`** — Google sign-in button state
- **`frontend/static/js/create_job.js`** — Create Job stepper + Groq flow
- **`frontend/static/js/dashboard.js`** — panel switching, sidebar
- **`frontend/static/js/cv_scoring.js`** — CV scoring, shortlist, invitations
- **`frontend/static/js/leaderboard.js`** — Final Rankings + HR override
- **`frontend/static/css/theme.css`**, **`dashboard.css`**, **`auth.css`**

## What is not connected yet

- **Job boards** — Rozee.pk, Indeed Pakistan, LinkedIn
- **Profile wizard** — remaining polish ([spec](docs/auth_onboarding_integrations.md))
- **Reports panel** — analytics not built yet

Extend **`database/schema.sql`** and **`database/ARCHITECTURE.md`** when new features need tables or columns.
