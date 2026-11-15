import os, sys, django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
    print([r[0] for r in c.fetchall()])

