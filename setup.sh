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
bench --site $(ls sites | grep -v 'assets\|apps\|common_site_config.json' | head -n 1) migrate

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
