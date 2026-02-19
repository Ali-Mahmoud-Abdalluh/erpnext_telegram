#!/bin/bash
# Setup script for Telegram Leave Bot as a systemd service
# Run from bench directory:
#   cd /home/frappe/frappe-bench
#   SITE_NAME=login.sescofire.com sudo -E bash apps/erpnext_telegram_integration/erpnext_telegram_integration/config/setup_telegram_bot_service.sh

set -e

# Find bench root: walk up from script dir until we find env/bin/python
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BENCH_PATH=""
for dir in "$SCRIPT_DIR" "$SCRIPT_DIR/.." "$SCRIPT_DIR/../.." "$SCRIPT_DIR/../../.." "$SCRIPT_DIR/../../../.." "$SCRIPT_DIR/../../../../.."; do
    dir="$(cd "$dir" 2>/dev/null && pwd)"
    if [ -f "$dir/env/bin/python" ]; then
        BENCH_PATH="$dir"
        break
    fi
done

# Fallback: if run from bench root
if [ -z "$BENCH_PATH" ] && [ -f "$(pwd)/env/bin/python" ]; then
    BENCH_PATH="$(pwd)"
fi

BENCH_PYTHON="$BENCH_PATH/env/bin/python"
RUN_BOT_SCRIPT="$BENCH_PATH/apps/erpnext_telegram_integration/erpnext_telegram_integration/bot/run_bot.py"

BENCH_USER="${BENCH_USER:-frappe}"
SITE_NAME="${SITE_NAME:-}"

if [ -z "$SITE_NAME" ]; then
    echo "Usage: SITE_NAME=your.site.com sudo -E bash setup_telegram_bot_service.sh"
    echo "Example: SITE_NAME=login.sescofire.com sudo -E bash setup_telegram_bot_service.sh"
    exit 1
fi

if [ -z "$BENCH_PATH" ] || [ ! -f "$BENCH_PYTHON" ]; then
    echo "Error: Could not find bench Python. Run this script from bench directory."
    echo "Expected: $BENCH_PATH/env/bin/python"
    exit 1
fi

if [ ! -f "$RUN_BOT_SCRIPT" ]; then
    echo "Error: run_bot.py not found at $RUN_BOT_SCRIPT"
    exit 1
fi

echo "Bench path: $BENCH_PATH"
echo "User: $BENCH_USER"
echo "Site: $SITE_NAME"
echo ""

SERVICE_FILE="/etc/systemd/system/telegram-leave-bot.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=ERPNext Telegram Leave Bot
After=network.target mariadb.service redis.service

[Service]
Type=simple
User=$BENCH_USER
Group=$BENCH_USER
WorkingDirectory=$BENCH_PATH
Environment=FRAPPE_SITE=$SITE_NAME
ExecStart=$BENCH_PYTHON $RUN_BOT_SCRIPT --site $SITE_NAME
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "Created $SERVICE_FILE"
echo ""
echo "To enable and start the service:"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable telegram-leave-bot"
echo "  sudo systemctl start telegram-leave-bot"
echo "  sudo systemctl status telegram-leave-bot"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u telegram-leave-bot -f"
echo ""
