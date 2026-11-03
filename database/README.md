# Database (PostgreSQL)

| File | Purpose |
|------|---------|
| `schema.sql` | Full DDL for database **`autohr_n`** (tables, indexes, constraints) |
| `ARCHITECTURE.md` | Table-by-table reference and relationships |

Apply schema (adjust host/user/password as needed):

```powershell
$env:PGPASSWORD = "your-postgres-password"
psql -U autohr -d autohr_n -f database/schema.sql
```

Connection settings live in the repo-root **`.env`** (`POSTGRES_*`).

Django uses unmanaged models in `backend/portal/models.py` mapped to these tables.
