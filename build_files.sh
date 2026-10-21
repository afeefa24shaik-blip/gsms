#!/bin/bash
echo "Installing dependencies..."
python3 -m pip install -r requirements.txt

echo "Collecting static assets..."
python3 manage.py collectstatic --noinput --clear

echo "Applying migrations if database is configured..."
python3 manage.py migrate --noinput || true

echo "Build complete."
