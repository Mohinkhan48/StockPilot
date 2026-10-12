#!/usr/bin/env bash
# =============================================================================
# Render Build Script for StockPilot Django REST Framework Backend
# =============================================================================
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "==> Upgrading pip..."
pip install --upgrade pip

echo "==> Installing backend dependencies..."
pip install -r requirements.txt

echo "==> Collecting static files with WhiteNoise..."
python manage.py collectstatic --no-input

echo "==> Running database migrations..."
python manage.py migrate

echo "==> Build completed successfully!"
