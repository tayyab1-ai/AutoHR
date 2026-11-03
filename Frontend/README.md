# Frontend (UI)

Django-rendered HTML, CSS, and vanilla JavaScript. On disk this folder may appear as `Frontend` on Windows; Django loads it via `frontend/` in `backend/config/settings.py` (same path on Windows).

| Path | Purpose |
|------|---------|
| `templates/` | Landing, auth, dashboard, partials |
| `static/css/` | Theme, dashboard, auth styles |
| `static/js/` | Auth, create job, dashboard, main |

No Node build step — edit and hard-refresh during development.
