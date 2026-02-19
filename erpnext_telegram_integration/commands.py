# -*- coding: utf-8 -*-
"""
Bench commands for ERPNext Telegram Integration.

Run interactive leave bot:
  bench --site [sitename] telegram-leave-bot
  OR: bench --site [sitename] execute erpnext_telegram_integration.bot.leave_bot.run
"""
from __future__ import unicode_literals

import os
import sys

import click

import frappe


def _get_site_from_context(ctx):
    """Traverse context chain to find site from bench --site."""
    current = ctx
    while current:
        if hasattr(current, "obj") and current.obj:
            sites = getattr(current.obj, "sites", None)
            if sites:
                return sites[0]
        current = getattr(current, "parent", None)
    return None


def _get_site_from_argv():
    """Fallback: parse --site from sys.argv."""
    if "--site" in sys.argv:
        idx = sys.argv.index("--site")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


@click.command("telegram-leave-bot")
@click.option("--site", help="Site name (optional if using bench --site)")
@click.pass_context
def telegram_leave_bot(ctx, site):
    """Run the interactive Telegram bot for leave applications."""
    site = site or _get_site_from_context(ctx) or _get_site_from_argv() or os.environ.get("FRAPPE_SITE")

    if not site:
        click.echo(
            "Error: No site specified. Use: bench --site [sitename] telegram-leave-bot"
        )
        raise SystemExit(1)

    frappe.init(site=site)
    frappe.connect()

    from erpnext_telegram_integration.bot.leave_bot import run

    run()


commands = [telegram_leave_bot]
