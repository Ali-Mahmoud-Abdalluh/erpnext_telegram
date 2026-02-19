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

# 2. Setup Supervisor (Force Manual Config for Bot)
echo "Configuring Supervisor..."

# Variables
BENCH_DIR=$(pwd)
# Detect User: If root, assume 'frappe', else use current user
if [ "$(whoami)" == "root" ]; then
    USER_NAME="frappe"
else
    USER_NAME=$(whoami)
fi

CONF_FILE="/etc/supervisor/conf.d/frappe-bench-telegram-bot.conf"

echo "Creating Supervisor config at $CONF_FILE..."

# Write config file (Standard Bench worker pattern)
sudo bash -c "cat > $CONF_FILE" <<EOL
[program:frappe-bench-telegram-bot]
command=${BENCH_DIR}/env/bin/python -m frappe.utils.bench_helper frappe execute erpnext_telegram_integration.bot.leave_bot.run
priority=1
autostart=true
autorestart=true
stdout_logfile=${BENCH_DIR}/logs/telegram_bot.log
stderr_logfile=${BENCH_DIR}/logs/telegram_bot.error.log
user=${USER_NAME}
directory=${BENCH_DIR}/sites
EOL

# 3. Reload Supervisor
echo "Reloading Supervisor..."
sudo supervisorctl reread
sudo supervisorctl update

# 4. Check Status
echo "Checking Bot Status..."
sudo supervisorctl status frappe-bench-telegram-bot

echo "Setup Complete! Your bot should be running."
