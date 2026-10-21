import os
import sys

# Ensure root directory is on the Python path
app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gsms_project.settings')

from gsms_project.wsgi import application, app

# Vercel entrypoint
handler = app
