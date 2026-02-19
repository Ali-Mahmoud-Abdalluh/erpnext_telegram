#!/bin/bash
set -e

# setup.sh - One-click setup for ERPNext Telegram Integration Bot

# Ensure we are in the bench root (if running from apps/erpnext_telegram_integration)
if [ -d "../../sites" ]; then
    cd ../..
    echo "Changed directory to bench root."
fi

echo "Starting Telegram Bot Setup..."

# 1. Migrate (Triggers install.py -> adds to Procfile)
echo "Running bench migrate..."
# Find first directory in sites/ that is not assets, apps, or starting with .
SITE_NAME=$(find sites -maxdepth 1 -mindepth 1 -type d ! -name "assets" ! -name "apps" ! -name ".*" | head -n 1 | sed 's|sites/||')
if [ -z "$SITE_NAME" ]; then
    echo "Error: Could not detect site name."
    exit 1
fi
echo "Detected site: $SITE_NAME"
bench --site $SITE_NAME migrate

# 2. Setup Supervisor (Reads Procfile -> Updates Supervisor Config)
echo "Updating Supervisor Configuration..."
sudo bench setup supervisor

# 3. Reload Supervisor
echo "Reloading Supervisor..."
sudo supervisorctl reread
sudo supervisorctl update

# 4. Check Status
echo "Checking Bot Status..."
sudo supervisorctl status telegram_bot

echo "Setup Complete! Your bot should be running."
