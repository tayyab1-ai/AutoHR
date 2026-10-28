# AutoHR

A Pakistan-localized hiring workspace for HR teams. This repository is the **frontend demo**: a Django project that renders the landing page, account screens, and HR dashboard with realistic sample data so the interface can be reviewed before it is connected to a database or the automation pipeline.

Nothing on these pages is saved. Forms validate in the browser and then open the dashboard preview.

## What is finished

| Area | Status |
| --- | --- |
| Marketing landing page | Done |
| Sign-in and HR registration screens | Done, demo only |
| HR dashboard with eight sections on one page | Done |
| Pakistan-specific sample data | Done |
| Visual system (type, color, layout, motion) | Done |
| Local run setup, secret-file ignore rules, and `.env` loading | Done |
| Database, real accounts, job-board posting, and AI calls | Not started |

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
| Jobs | Six sample roles with board, PKR salary, hire count, applicant count, and Live / Draft / Closed status |
| Create Job | Role form with a live preview, skill chips, and a demo “saved as draft” result |
| Applications | Six candidates in a split view, with overview and score-breakdown tabs |
| Pipeline | Kanban columns for Posted, Screened, Interviewed, and Decided |
| Interviews | Scheduled and completed 3-stage AI video interviews |
| Reports | Time to hire, cost per hire, offer acceptance, top source, and the applications chart |
| Account | The stored demo HR profile, including masked job-board passwords |

Sample company: **Northbridge Technologies**, Lahore. Signed-in HR: **Ayesha Khan**, HR Manager.

## Sample data

All dashboard numbers live in `Frontend/portal/data.py`. They are not loaded from a database.

The set is written for a Pakistani HR audience:

- Salaries in PKR per month
- Offices in Lahore, Karachi, Islamabad, Rawalpindi, and Faisalabad
- Phone numbers with the `+92` country code
- Job boards called out as Rozee.pk and Indeed Pakistan
- The app time zone is `Asia/Karachi`

The landing page describes a future stack (PostgreSQL, LLM job-description drafting, Whisper interview transcription). Those services are **not** connected in this repository.

## Project layout

```text
AutoHR-N/
├── README.md
├── .gitignore
└── Frontend/
    ├── manage.py
    ├── requirements.txt
    ├── .env.example
    ├── autohr_frontend/     # settings, URLs, cache middleware
    ├── portal/              # views and demo data
    ├── templates/           # landing, auth, dashboard, base
    └── static/
        ├── css/             # theme.css, dashboard.css
        └── js/              # main.js, dashboard.js
```

`portal` is the only installed app. Django static files are enabled. There is no database configuration (`DATABASES` is empty) and no admin site.

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
```

`Frontend/autohr_frontend/settings.py` reads `Frontend/.env` without overriding variables already set in the shell. If `DJANGO_SECRET_KEY` is missing, the app uses a labeled demo key so `runserver` still starts. Do not put a production key in `settings.py`.

## Front-end notes

- Bootstrap 5.3 and Bootstrap Icons load from a CDN
- Plus Jakarta Sans loads from Google Fonts
- Scroll reveals use AOS
- Shared behavior (tooltips, counters, password visibility, auth toggle, demo submit) is in `static/js/main.js`
- Dashboard behavior (panel switching, sidebar, bar animation, candidate selection, skill chips, job preview) is in `static/js/dashboard.js`
- Colors, type, and landing styles are in `static/css/theme.css`
- Dashboard layout is in `static/css/dashboard.css`

The header actions (New Job, notifications, and the HR chip) stay on one row. Dashboard sections are buttons, not separate URLs, so the address stays `/dashboard/` while you move around the workspace.
