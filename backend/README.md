# Backend (Django)

Server-side application: HTTP routes, auth, PostgreSQL models, Groq JD generation.

| Path | Purpose |
|------|---------|
| `manage.py` | Django CLI entrypoint |
| `config/` | Settings, URLs, WSGI/ASGI, middleware |
| `portal/` | Main app (views, auth, models, services) |
| `requirements.txt` | Python dependencies |
| `.venv/` | Local virtualenv (create with `python -m venv .venv`) |

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Environment variables are loaded from **`../.env`** at the repository root.
