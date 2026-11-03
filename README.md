# AutoHR

A Pakistan-localized hiring workspace for HR teams. Django serves the marketing landing page, **real signup/sign-in**, and a protected HR dashboard.

**Create Job** is wired to PostgreSQL (`autohr_n`): validate intake → save job → **Groq AI** job description (step 2 on the same page) → HR review/edit → save finalized copy. The next pipeline step will attach a **Google Form** link after `Apply Here:`.

**Access:** There is **no demo workspace**. `/dashboard/` and all job APIs require a signed-in HR user. Public routes are `/`, `/login/`, and `/register/` only.

## Current step (where the build is now)

| Pipeline phase | Status | Notes |
| --- | --- | --- |
| **Auth — signup (email OTP)** | Done | 6-digit code, 2-minute cache TTL, 3 attempts; user created only after OTP |
| **Auth — login / sessions** | Done | Email + password, PostgreSQL `users.password_hash`, multi-device sessions |
| **Auth — forgot password** | Done | Email OTP resets password for existing accounts |
| **1 — Job intake (form A–G)** | Done | Validate on server, save `job_postings` + `job_responsibilities` |
| **2 — AI job description (Groq)** | Done | Same-page stepper step 2; `ai_generated_jd_draft`; formatted preview + edit |
| **2b — Apply footer** | Done | AI ends with **How to Apply** → **`Apply Here: `** (blank; URL in next phase) |
| **3 — HR finalize description** | Done | **Post Create Google Form** → `approved_jd_content` (no real Google Form yet) |
| **4 — Create Google Form + link** | **Next** | Generate form, insert URL after `Apply Here:` |
| **5 — Publish to job boards** | Not started | Rozee / Indeed / LinkedIn |
| **Profile wizard + integrations** | Not started | Spec in [docs/auth_onboarding_integrations.md](docs/auth_onboarding_integrations.md) |
| **Applications, pipeline, interviews, reports (DB-backed)** | Not started | UI shells with empty states; no fake sample rows |

**You are here:** step **4** (Google Form + link), then job boards and profile/integrations wizard.

## What is finished

| Area | Status |
| --- | --- |
| Marketing landing page (public) | Done |
| **Signup** — email, password, OTP modal (Fetch API, no page reload on OTP step) | Done |
| **Login** — email/password, Django session | Done |
| **Forgot password** — OTP on login page | Done |
| **Protected dashboard** — login required; no anonymous demo actor | Done |
| HR dashboard shell (eight panels on one page) | Done |
| Visual system (type, color, layout, motion) | Done |
| Repo layout (`backend/`, `frontend/`, `database/`, root `.env`) | Done |
| PostgreSQL schema (`autohr_n`) | Done |
| **Create Job** — intake, validation, save to DB | Done |
| **Jobs** list — real rows for signed-in user’s company only | Done |
| **Step 2 — AI JD** (Groq, preview/edit) | Done |
| **Post Create Google Form** — save finalized JD to DB | Done (form URL not created yet) |
| Profile wizard, company/job-board credential onboarding | Not started |
| Google Form automation + Apply link injection | Not started |
| Job-board publishing | Not started |
| Applications / pipeline / interviews / reports from DB | Not started |

## Authentication

### Signup (`/register/`)

1. Enter **email**, **password**, **confirm password** (client + server rules: 8+ chars, at least one letter and one number).
2. **Sign up** sends a 6-digit OTP via **Gmail SMTP** (settings in repo-root `.env`).
3. OTP **modal**: countdown **2:00**, **resend** after expiry, **change email**, max **3** wrong attempts then lockout.
4. On success, account is created in PostgreSQL (`users` + placeholder `companies` row); redirect to **login** with success message.
5. Passwords are hashed with Django’s default hasher; plain text is never stored.

### Login (`/login/`)

- Email + password; session via `login()` and custom `HrEmailBackend` against `users`.
- Failed login shows a generic error; existing emails hint at **Forgot password**.
- After login, **`/dashboard/`** and job POST endpoints use the **session user’s** `company_id` / `user_id`.

### Forgot password

- On the login page: **Forgot password?** → new password + confirm → OTP email → verify → sign in with the new password.

### API routes (auth)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/signup/send-otp/` | Start signup, send OTP |
| POST | `/auth/signup/verify-otp/` | Verify OTP, create user |
| POST | `/auth/signup/resend-otp/` | Resend signup OTP |
| POST | `/auth/password/send-otp/` | Start password reset |
| POST | `/auth/password/verify-otp/` | Confirm reset OTP |
| POST | `/auth/password/resend-otp/` | Resend reset OTP |
| POST | `/auth/login/` | JSON login |
| POST | `/auth/logout/` | JSON logout |
| GET | `/logout/` | Sign out redirect to home |

**Code:** `backend/portal/auth_views.py`, `auth_services.py`, `auth_backend.py`, `auth_user.py`, `decorators.py`; UI: `frontend/templates/auth.html`, `frontend/static/js/auth.js`.

**Email setup:** `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (Google **App Password**), `DEFAULT_FROM_EMAIL` in `.env`. See `.env.example`.

Run once after pulling auth changes:

```powershell
cd backend
python manage.py migrate
```

## Pages

| Route | Access | What you can do |
| --- | --- | --- |
| `/` | Public | Marketing; redirects to dashboard if already signed in |
| `/login/` | Public | Sign in (redirects to dashboard if already signed in) |
| `/register/` | Public | Sign up with OTP |
| `/dashboard/` | **Login required** | HR workspace (panels below) |

Sign-in and registration share one template; the URL sets the visible panel. Auth actions use **Fetch API** (no full-page reload for OTP/login submit).

### Landing page

- Product story, pipeline, scoring rubric, technology section
- CTAs: **Get Started** → register, **Sign in to workspace** → login (no dashboard demo link)

### Registration (current UI)

- **Fields:** work email, password, confirm password (not the full company/profile wizard yet).
- After OTP verification, a **minimal company** row is created; full profile onboarding is planned in [docs/auth_onboarding_integrations.md](docs/auth_onboarding_integrations.md).

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

Settings: **`backend/config/settings.py`**. Secrets: **`.env`** at repo root (`POSTGRES_*`, `GROQ_*`, `DJANGO_SECRET_KEY`, Gmail SMTP).

## Run it locally

Requirements: Python 3.11+, PostgreSQL with **`autohr_n`** schema, **Groq API key**, **Gmail App Password** for OTP, venv at **`backend/.venv`**.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

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
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your@gmail.com
```

`settings.py` loads `.env` with **`override=True`**. Restart **`runserver`** after edits.

**Gmail OTP:** enable 2-Step Verification → create an **App Password** → put it in `EMAIL_HOST_PASSWORD` (not your normal Gmail password).

## Front-end notes

- Bootstrap 5.3, Bootstrap Icons, Plus Jakarta Sans, AOS (CDN)
- **`frontend/static/js/main.js`** — tooltips, counters, password visibility, auth panel toggle
- **`frontend/static/js/auth.js`** — signup OTP modal, login, forgot password
- **`frontend/static/js/create_job.js`** — Create Job stepper + Groq flow
- **`frontend/static/js/dashboard.js`** — panel switching, sidebar
- **`frontend/static/css/theme.css`**, **`dashboard.css`**, **`auth.css`**

## What is not connected yet

- **Profile wizard** — full company + job-board credentials before first job ([spec](docs/auth_onboarding_integrations.md))
- **Google Form** — create form, inject URL after **`Apply Here:`**
- **Job boards** — Rozee.pk, Indeed Pakistan, LinkedIn
- **Applications, pipeline, interviews, reports** — UI only; empty until backed by PostgreSQL
- **Whisper / AI interviews** — mentioned on landing; not implemented

Extend **`database/schema.sql`** and **`database/ARCHITECTURE.md`** when new features need tables or columns.
