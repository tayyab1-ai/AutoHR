# AutoHR

A Pakistan-localized hiring workspace for HR teams. The Django frontend renders the landing page, account screens, and HR dashboard.

**Create Job** is wired to PostgreSQL (`autohr_n`): validate intake → save job → **Groq AI** job description (step 2 on the same page) → HR review/edit → save finalized copy. The next pipeline step will attach a **Google Form** link after `Apply Here:`. Other dashboard sections still use demo data in `portal/data.py`.

## Current step (where the build is now)

| Pipeline phase | Status | Notes |
| --- | --- | --- |
| **1 — Job intake (form A–G)** | Done | Validate on server, save `job_postings` + `job_responsibilities` |
| **2 — AI job description (Groq)** | Done | Same-page stepper step 2; `ai_generated_jd_draft`; formatted preview + rectangular edit |
| **2b — Apply footer** | Done | AI ends with **How to Apply** → **`Apply Here: `** (blank; URL in next phase) |
| **3 — HR finalize description** | Done | **Post Create Google Form** → `approved_jd_content` (no real Google Form yet) |
| **4 — Create Google Form + link** | **Next** | Generate form, insert URL after `Apply Here:` |
| **5 — Publish to job boards** | Not started | Rozee / Indeed / LinkedIn |
| **Auth (real login/register)** | Not started | Dashboard uses demo `ensure_demo_hr()` |
| **Applications, pipeline, interviews, reports** | Demo UI | Data from `portal/data.py` |

**You are here:** finish step **4** (Google Form + link), then job boards.

**Next major track:** real **signup / login / profile completion** before first job — full field list, integrations (Google Forms, Drive, Meet, email, LinkedIn simple post, job boards), and DB plan are in **[docs/auth_onboarding_integrations.md](docs/auth_onboarding_integrations.md)**.

## What is finished

| Area | Status |
| --- | --- |
| Marketing landing page | Done |
| Sign-in and HR registration screens | Done, demo only |
| HR dashboard with eight sections on one page | Done |
| Pakistan-specific sample data | Done |
| Visual system (type, color, layout, motion) | Done |
| Local run setup, secret-file ignore rules, and `.env` loading | Done |
| PostgreSQL schema (`autohr_n`) | Done |
| **Create Job** — real intake fields, server validation, save to DB | Done |
| **Jobs** list — reads saved postings from the DB | Done (falls back to demo rows if none exist) |
| Dashboard panels other than Create Job / Jobs | Demo data only |
| Real sign-in / registration against the DB | Not started — spec in `docs/auth_onboarding_integrations.md` |
| Profile wizard (integrations before first job) | Not started — same spec |
| **Step 2 — AI job description** (Groq, formatted preview, rectangle edit box) | Done |
| **Step 2 — Apply Here:** line in AI output (blank for future form URL) | Done |
| **Post Create Google Form** — save finalized JD to DB | Done (form URL not created yet) |
| Google Form creation, Apply link injection, job-board posting | Not started |

## Pages

| Route | Screen | What you can do |
| --- | --- | --- |
| `/` | Landing | Read the product story and jump to Sign In, Get Started, or the dashboard |
| `/login/` | Sign in | Enter a work email and password. A valid demo submit opens the dashboard |
| `/register/` | Create an HR account | Fill the HR, company, and job-board fields. A valid demo submit opens the dashboard |
| `/dashboard/` | HR workspace | Move between Dashboard, Jobs, Create Job, Applications, Pipeline, Interviews, Reports, and Account without leaving the page |

Sign in and registration are the same template. The URL chooses which panel is visible, and a link on the page switches between them without a reload.

### Landing page

- Sticky navigation with links to the pipeline, scoring rubric, technology section, and dashboard
- Hero with a trial button, a dashboard button, and animated counts
- Trust row for Rozee.pk, Indeed Pakistan, LinkedIn, Mettl, and PSEB
- Four hiring phases and the ten pipeline steps
- Five interview dimensions, each scored out of 10: Communication, Confidence, Technical Knowledge, Relevance, and Problem-Solving
- Technology section, three HR testimonials, a closing call to action, and a footer

### Registration fields

The create-account form is prefilled with the demo HR profile so the layout can be reviewed quickly.

- **HR profile:** full name, job title, work phone, work email, password, confirm password
- **Company:** name, website, industry, company size, country, city, office address
- **Job-board accounts already created:** LinkedIn profile link, LinkedIn email and password, Indeed email and password, Rozee.pk email and password

Required fields are marked. Password fields can be shown or hidden. Info tips explain each field. Passwords must be at least 8 characters on the HR account. Submitting a valid form shows a short success message and then opens `/dashboard/`. No account is created.

### Dashboard

The sidebar swaps panels on the same screen. The header has search, **New Job**, a notification button, and the signed-in HR chip. On a narrow screen the sidebar slides in from the menu button.

| Section | What it shows |
| --- | --- |
| Dashboard | Four KPI cards, the Phase 1–4 funnel, a six-month applications chart, and recent activity |
| Jobs | Roles from PostgreSQL for your company when present; otherwise six sample roles from demo data |
| Create Job | 3-step flow: intake (A–G) → AI description → finalize (Google Form step stub) — see below |
| Applications | Six candidates in a split view, with overview and score-breakdown tabs |
| Pipeline | Kanban columns for Posted, Screened, Interviewed, and Decided |
| Interviews | Scheduled and completed 3-stage AI video interviews |
| Reports | Time to hire, cost per hire, offer acceptance, top source, and the applications chart |
| Account | The stored demo HR profile, including masked job-board passwords |

Sample company: **Northbridge Technologies**, Lahore. Signed-in HR: **Ayesha Khan**, HR Manager.

### Create Job (PostgreSQL + Groq)

The sidebar **Create Job** panel uses a **three-step stepper** on one page:

| Step | UI label | What happens |
| --- | --- | --- |
| 1 | Job Details | Full intake form (sections below), live preview, **Generate Job Description** |
| 2 | AI Job Description | Loading state, then formatted draft; preview or **Edit description** (rectangular editor) |
| 3 | Publish to Boards | **Post Create Google Form** saves finalized text (Google Form automation comes next) |

Sign-in is still demo-only; saves use **`ensure_demo_hr()`** (Northbridge Technologies / Ayesha Khan in the DB), not the email you type on `/login/`.

Intake fields are grouped as **A, B, C, D, E, and G**:

**A — Basic job information:** job title, department, job category, employment type, work mode, city, number of vacancies, job description, company name (must match the registered company in the DB), posting date, application deadline, urgency level.

**B — Experience and education:** minimum / maximum experience (years), fresh-graduate eligibility, minimum education level.

**C — Technical skills:** required skills (chip input); programming languages when the category is software, data, AI/ML, or cybersecurity; optional frameworks, tools, cloud platforms, and technical knowledge text.

**D — Salary and benefits:** optional min/max salary in PKR, required salary period, negotiable flag, and benefit toggles/text (bonus, insurance, leave, relocation, equipment, and so on).

**E — Responsibilities:** repeatable key responsibilities (required) and optional daily tasks — stored in `job_responsibilities`.

**G — Shortlisting and tone:** job post tone (with custom instructions when tone is Custom), shortlist count after CV screening (20–30, default 25), shortlist count after interview.

Each label has an **ⓘ tooltip**. The right column is a **live preview** (browser-only until you save).

**Generate Job Description** (step 1 → 2):

1. Server validates all intake fields (`JobIntakeForm`). Errors stay on step 1 — nothing is saved until validation passes.
2. Valid data is written to **`job_postings`** and **`job_responsibilities`** (status `draft`).
3. **Groq** runs on the server in the same request (`GROQ_API_KEY`, `GROQ_MODEL` in repo-root `.env`; default model in `.env.example` is `openai/gpt-oss-120b`). Prompt + normalization live in **`backend/portal/groq_jd.py`**.
4. The UI switches to **step 2**. The draft is stored in **`ai_generated_jd_draft`** and rendered with headings, bullets, and paragraphs (not raw `#` / `-` markdown). The closing section includes **`Apply Here: `** with a blank space for the Google Form URL in the next build step.
5. HR can **Edit description** (full-width rectangular textarea) or return to **Preview formatted**.
6. **Retry AI generation** calls `POST /dashboard/jobs/<id>/generate-jd/` if the first AI call failed.
7. **Post Create Google Form** writes the finalized text to **`approved_jd_content`** (edited copy, or the AI draft if unchanged). Creating the form and inserting the link is not implemented yet.

| Column | Purpose |
| --- | --- |
| `ai_generated_jd_draft` | AI output from Groq |
| `approved_jd_content` | HR-finalized description after review |

**API routes:** `POST /dashboard/jobs/create/`, `POST /dashboard/jobs/<uuid>/generate-jd/`, `POST /dashboard/jobs/<uuid>/prepare-google-form/`.

**Code:** `backend/portal/forms.py`, `services.py`, `groq_jd.py`, `models.py`, `dev_actor.py`, `frontend/templates/partials/create_job_panel.html`, `frontend/static/js/create_job.js`, `frontend/static/css/dashboard.css` (JD preview/edit styles).

## Sample data

Most dashboard numbers live in `backend/portal/data.py`. The **Jobs** table and **Create Job** flow read and write `job_postings` and `job_responsibilities` in PostgreSQL when repo-root `.env` is configured.

The set is written for a Pakistani HR audience:

- Salaries in PKR per month
- Offices in Lahore, Karachi, Islamabad, Rawalpindi, and Faisalabad
- Phone numbers with the `+92` country code
- Job boards called out as Rozee.pk and Indeed Pakistan
- The app time zone is `Asia/Karachi`

**Create Job** uses Groq for job-description drafting (see above). Landing-page copy also mentions Whisper interview transcription; that is **not** connected yet.

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
│   └── portal/               # app: views, auth, models, Groq, services
├── frontend/                 # UI templates + static (CSS/JS); may show as Frontend on Windows
│   ├── templates/
│   └── static/
├── database/
│   ├── schema.sql            # PostgreSQL DDL for autohr_n
│   └── ARCHITECTURE.md       # tables, columns, relationships
├── docs/
│   └── auth_onboarding_integrations.md
└── scripts/
    └── run-dev.ps1           # optional dev server helper
```

`portal` is the only Django app. Settings live in `backend/config/settings.py`. Secrets and `POSTGRES_*` / `GROQ_*` / email vars are in **`.env` at the repo root**.

## Run it locally

Requirements: Python 3.11 or newer, PostgreSQL with **`autohr_n`** schema applied, a valid **Groq API key**, and the virtual environment at `backend/.venv` (`pip install -r requirements.txt` installs Django, psycopg, and **groq**).

From PowerShell:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

Or from the repo root:

```powershell
.\scripts\run-dev.ps1
```

If activation is blocked, start the app with the environment’s Python directly:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py runserver
```

Leave that window open. Stopping the server makes every link in the browser fail. Then open:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/login/
- http://127.0.0.1:8000/register/
- http://127.0.0.1:8000/dashboard/

On a fresh machine, create the environment first:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Stylesheets and scripts are linked with a file-modification version, and development responses send `Cache-Control: no-store`. After a CSS change, reload the page. If Chrome still shows an older header, press **Ctrl+Shift+R** once.

## Database

PostgreSQL holds database **`autohr_n`**. Re-run `database/schema.sql` only after you change the schema (drop/recreate or migrate as you prefer).

| Item | Value |
| --- | --- |
| Host | `localhost` |
| Port | `5432` |
| Database | `autohr_n` |
| Login | `autohr` |
| Password | repo-root `.env` (`POSTGRES_PASSWORD`) |
| Schema script | `database/schema.sql` |
| Table guide | `database/ARCHITECTURE.md` |

The login `autohr` can change the schema (add or alter columns). The password is only in `.env`, which git ignores.

The schema includes **`job_postings`** (full intake columns), **`job_responsibilities`**, companies, users, board posts, candidates, applications, interviews, rankings, notifications, and related tables. **`job_postings`** and **`job_responsibilities`** are written by **Create Job**; other tables are for later pipeline steps. Details are in `database/ARCHITECTURE.md`.

`.env.example` at the repo root lists variable names (Postgres + Groq + email); copy to `.env` and fill in real secrets (never commit `.env`).

## Secrets

`.gitignore` keeps local secrets out of git:

- `.env` files (`.env.example` is allowed)
- key and certificate files
- `secrets.json`, `credentials.json`, and service-account JSON
- `local_settings.py`
- virtual environments, `__pycache__`, and SQLite files

Copy the example and put a real key in the ignored file:

```powershell
copy .env.example .env
```

```text
DJANGO_SECRET_KEY=your-long-random-string
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=autohr
POSTGRES_PASSWORD=your-local-password
POSTGRES_DB=autohr_n
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=openai/gpt-oss-120b
```

`backend/config/settings.py` loads the repo-root `.env` with **`override=True`** so values in the file replace stale `GROQ_API_KEY` / `POSTGRES_*` exports in the shell or Windows environment. Restart **`runserver`** after changing `.env`.

If `DJANGO_SECRET_KEY` is missing, the app uses a labeled demo key so `runserver` still starts. **Create Job** needs working **Postgres** and **Groq** configuration.

## Front-end notes

- Bootstrap 5.3 and Bootstrap Icons load from a CDN
- Plus Jakarta Sans loads from Google Fonts
- Scroll reveals use AOS
- Shared behavior (tooltips, counters, password visibility, auth toggle, demo submit) is in `static/js/main.js`
- Dashboard behavior (panel switching, sidebar, bar animation, candidate selection) is in `static/js/dashboard.js`
- Create Job (skill chips, repeatables, step 2 AI preview/edit, Groq save/retry, finalize POST) is in `static/js/create_job.js`
- Colors, type, and landing styles are in `static/css/theme.css`
- Dashboard layout is in `static/css/dashboard.css`

The header actions (New Job, notifications, and the HR chip) stay on one row. Dashboard sections are buttons, not separate URLs, so the address stays `/dashboard/` while you move around the workspace.

## What is not connected yet

- **Sign-in and registration** — demo UI only; no session or auth tied to job APIs.
- **Most dashboard panels** (overview KPIs, applications, pipeline, interviews, reports, account) — still driven by `backend/portal/data.py`.
- **Google Form** — next step: create the form, paste the URL after **`Apply Here:`** in the stored description, and wire **Post Create Google Form** to that automation.
- **Job boards** — no publish/sync to Rozee.pk, Indeed, or LinkedIn yet.

`database/schema.sql` and `database/ARCHITECTURE.md` describe the current database; extend them when new screens need more tables or columns.
