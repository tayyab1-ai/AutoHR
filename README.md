# AutoHR

A Pakistan-localized hiring workspace for HR teams. The Django frontend renders the landing page, account screens, and HR dashboard. **Create Job** saves full job intake records to PostgreSQL (`autohr_n`). Other dashboard sections still use demo data in `portal/data.py`.

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
| Real sign-in / registration against the DB | Not started |
| AI job-description generation and job-board posting | Not started (Create Job saves a draft only) |

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
| Create Job | Real job-posting intake (sections A–G), validation, then save to PostgreSQL — see below |
| Applications | Six candidates in a split view, with overview and score-breakdown tabs |
| Pipeline | Kanban columns for Posted, Screened, Interviewed, and Decided |
| Interviews | Scheduled and completed 3-stage AI video interviews |
| Reports | Time to hire, cost per hire, offer acceptance, top source, and the applications chart |
| Account | The stored demo HR profile, including masked job-board passwords |

Sample company: **Northbridge Technologies**, Lahore. Signed-in HR: **Ayesha Khan**, HR Manager.

### Create Job (connected to PostgreSQL)

The old short demo form (title, salary, a few skills) is replaced with the **full intake** HR needs before a role can move through the pipeline. Fields are grouped on the page as **A, B, C, D, E, and G** (same structure as the product spec).

**A — Basic job information:** job title, department, job category, employment type, work mode, city, number of vacancies, job description, company name (must match the registered company in the DB), posting date, application deadline, urgency level.

**B — Experience and education:** minimum / maximum experience (years), fresh-graduate eligibility, minimum education level.

**C — Technical skills:** required skills (chip input); programming languages when the category is software, data, AI/ML, or cybersecurity; optional frameworks, tools, cloud platforms, and technical knowledge text.

**D — Salary and benefits:** optional min/max salary in PKR, required salary period, negotiable flag, and benefit toggles/text (bonus, insurance, leave, relocation, equipment, and so on).

**E — Responsibilities:** repeatable key responsibilities (required) and optional daily tasks — stored in `job_responsibilities`.

**G — Shortlisting and tone:** job post tone (with custom instructions when tone is Custom), shortlist count after CV screening (20–30, default 25), shortlist count after interview.

Each label has an **ⓘ tooltip**. The right column is a **live preview** (browser-only until you save). **Generate Job Description** does **not** call AI yet; it **validates the form on the server**, then inserts a **draft** row in `job_postings` and related rows in `job_responsibilities`. Invalid input returns errors in the UI without writing to the database.

**Flow:** fill form → click **Generate Job Description** → `POST /dashboard/jobs/create/` → Django `JobIntakeForm` validation → `create_job_posting()` → PostgreSQL. Company context comes from `ensure_demo_hr()` (creates **Northbridge Technologies** and **Ayesha Khan** in the DB on first use if missing).

Implementation: `Frontend/portal/forms.py`, `services.py`, `models.py`, `templates/partials/create_job_panel.html`, `static/js/create_job.js`.

## Sample data

Most dashboard numbers live in `Frontend/portal/data.py`. The **Jobs** table and **Create Job** flow read and write `job_postings` and `job_responsibilities` in PostgreSQL when `Frontend/.env` is configured.

The set is written for a Pakistani HR audience:

- Salaries in PKR per month
- Offices in Lahore, Karachi, Islamabad, Rawalpindi, and Faisalabad
- Phone numbers with the `+92` country code
- Job boards called out as Rozee.pk and Indeed Pakistan
- The app time zone is `Asia/Karachi`

The landing page also describes LLM job-description drafting and Whisper interview transcription. Those services are not connected.

## Project layout

```text
AutoHR-N/
├── README.md
├── db_architecture.md       # every table, column, and relationship
├── .gitignore
├── db/
│   └── schema.sql           # the script already applied to PostgreSQL
└── Frontend/
    ├── manage.py
    ├── requirements.txt
    ├── .env.example
    ├── autohr_frontend/     # settings, URLs, cache middleware
    ├── portal/              # views, forms, models, services, demo data
    ├── templates/           # landing, auth, dashboard, create_job partial
    └── static/
        ├── css/             # theme.css, dashboard.css
        └── js/              # main.js, dashboard.js, create_job.js
```

`portal` is the only app. Django is configured to use PostgreSQL via `DATABASES` in `Frontend/autohr_frontend/settings.py` and `POSTGRES_*` in `Frontend/.env`.

## Run it locally

Requirements: Python 3.11 or newer, and the virtual environment already created at `Frontend/.venv` (Django 5 is installed there).

From PowerShell:

```powershell
cd Frontend
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

If activation is blocked, start the app with the environment’s Python directly:

```powershell
cd Frontend
.\.venv\Scripts\python.exe manage.py runserver
```

Leave that window open. Stopping the server makes every link in the browser fail. Then open:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/login/
- http://127.0.0.1:8000/register/
- http://127.0.0.1:8000/dashboard/

On a fresh machine, create the environment first:

```powershell
cd Frontend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py runserver
```

Stylesheets and scripts are linked with a file-modification version, and development responses send `Cache-Control: no-store`. After a CSS change, reload the page. If Chrome still shows an older header, press **Ctrl+Shift+R** once.

## Database

PostgreSQL holds database **`autohr_n`**. Re-run `db/schema.sql` only after you change the schema (drop/recreate or migrate as you prefer).

| Item | Value |
| --- | --- |
| Host | `localhost` |
| Port | `5432` |
| Database | `autohr_n` |
| Login | `autohr` |
| Password | `Frontend/.env` (`POSTGRES_PASSWORD`) |
| Schema script | `db/schema.sql` |
| Table guide | `db_architecture.md` |

The login `autohr` can change the schema (add or alter columns). The password is only in `Frontend/.env`, which git ignores.

The schema includes **`job_postings`** (full intake columns), **`job_responsibilities`**, companies, users, board posts, candidates, applications, interviews, rankings, notifications, and related tables. **`job_postings`** and **`job_responsibilities`** are written by **Create Job**; other tables are for later pipeline steps. Details are in `db_architecture.md`.

`Frontend/.env.example` lists the variable names without the real password.

## Secrets

`.gitignore` keeps local secrets out of git:

- `.env` files (`.env.example` is allowed)
- key and certificate files
- `secrets.json`, `credentials.json`, and service-account JSON
- `local_settings.py`
- virtual environments, `__pycache__`, and SQLite files

Copy the example and put a real key in the ignored file:

```powershell
cd Frontend
copy .env.example .env
```

```text
DJANGO_SECRET_KEY=your-long-random-string
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=autohr
POSTGRES_PASSWORD=your-local-password
POSTGRES_DB=autohr_n
```

`Frontend/autohr_frontend/settings.py` reads `Frontend/.env` without overriding variables already set in the shell. If `DJANGO_SECRET_KEY` is missing, the app uses a labeled demo key so `runserver` still starts. **Create Job requires a working Postgres connection** (`POSTGRES_*` and database `autohr_n` with schema applied).

## Front-end notes

- Bootstrap 5.3 and Bootstrap Icons load from a CDN
- Plus Jakarta Sans loads from Google Fonts
- Scroll reveals use AOS
- Shared behavior (tooltips, counters, password visibility, auth toggle, demo submit) is in `static/js/main.js`
- Dashboard behavior (panel switching, sidebar, bar animation, candidate selection) is in `static/js/dashboard.js`
- Create Job behavior (skill chips, repeatables, live preview, validation POST) is in `static/js/create_job.js`
- Colors, type, and landing styles are in `static/css/theme.css`
- Dashboard layout is in `static/css/dashboard.css`

The header actions (New Job, notifications, and the HR chip) stay on one row. Dashboard sections are buttons, not separate URLs, so the address stays `/dashboard/` while you move around the workspace.

## What is not connected yet

- **Sign-in and registration** — demo UI only; no users are created or authenticated against PostgreSQL.
- **Most dashboard panels** (overview KPIs, applications, pipeline, interviews, reports, account) — still driven by `Frontend/portal/data.py`.
- **AI job description** — after validation and DB save, the next pipeline step (LLM draft) is not implemented.
- **Job boards** — no publish/sync to Rozee.pk, Indeed, or LinkedIn yet.

`db/schema.sql` and `db_architecture.md` describe the current database; extend them when new screens need more tables or columns.
