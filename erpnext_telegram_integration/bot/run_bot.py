#!/usr/bin/env python3
"""
Standalone launcher for Telegram Leave Bot.
Run directly with bench Python to avoid bench CLI / Click compatibility issues:

  /home/frappe/frappe-bench/env/bin/python /home/frappe/frappe-bench/apps/erpnext_telegram_integration/erpnext_telegram_integration/bot/run_bot.py --site login.sescofire.com

Or from bench directory:
  cd /home/frappe/frappe-bench && ./env/bin/python apps/erpnext_telegram_integration/erpnext_telegram_integration/bot/run_bot.py --site login.sescofire.com
"""
from __future__ import unicode_literals

import argparse
import logging
import os
import sys

# Suppress cssutils/Frappe CSS parsing errors (must be before frappe import)
for _name in ("cssutils", "CSSUTILS", "cssutils.cssutils"):
    logging.getLogger(_name).setLevel(logging.CRITICAL)
try:
    import cssutils
    cssutils.log.setLevel(logging.CRITICAL)
except ImportError:
    pass

# Resolve bench path and change to sites directory (required by Frappe)
_script_dir = os.path.dirname(os.path.abspath(__file__))
# bot -> pkg -> app root -> apps -> bench (4 levels up)
BENCH_PATH = os.environ.get(
    "BENCH_PATH",
    os.path.normpath(os.path.join(_script_dir, "..", "..", "..", "..")),
)
SITES_PATH = os.path.join(BENCH_PATH, "sites")
if os.path.isdir(SITES_PATH):
    os.chdir(SITES_PATH)


def main():
    parser = argparse.ArgumentParser(description="Run Telegram Leave Bot")
    parser.add_argument("--site", required=True, help="Site name (e.g. login.sescofire.com)")
    args = parser.parse_args()

    import frappe

    frappe.init(site=args.site)
    frappe.connect()

    from erpnext_telegram_integration.bot.leave_bot import run

    run()


if __name__ == "__main__":
    main()
