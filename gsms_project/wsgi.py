"""
WSGI config for gsms_project project.

It exposes the WSGI callable as a module-level variable named ``application``.
For Vercel deployment, it also exposes ``app`` and automatically applies migrations
on serverless cold start if database tables are uninitialized.
"""

import os
import sys

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gsms_project.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
app = application

# Serverless & Deployment Auto-Migration & Seeding Handler
def init_serverless_database():
    """
    If database tables do not exist (fresh container /tmp or new Postgres instance),
    automatically executes migrations and seeds initial staff credentials to avoid
    OperationalError: no such table.
    """
    try:
        from django.db import connection
        table_names = connection.introspection.table_names()
        if 'gsms_users' not in table_names:
            print("[Database Auto-Init] Database tables not found. Running migrations...")
            from django.core.management import call_command
            call_command('migrate', interactive=False)
            try:
                call_command('seed_data')
                print("[Database Auto-Init] Migrations and seed data completed successfully.")
            except Exception as se:
                print(f"[Database Auto-Init] Seed note: {se}")
    except Exception as e:
        print(f"[Database Auto-Init] Migration check error: {e}")

# Always execute check on startup
init_serverless_database()
