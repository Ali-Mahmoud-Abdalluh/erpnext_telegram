# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe


def after_install():
	"""Add custom fields to Employee for interactive Telegram bot."""
	add_employee_telegram_fields()
	setup_procfile()


def add_employee_telegram_fields():
	"""Create custom fields on Employee and Telegram Settings for interactive bot."""

	custom_fields = [
		{
			"dt": "Employee",
			"fieldname": "telegram_chat_id",
			"label": "Telegram Chat ID",
			"fieldtype": "Data",
			"insert_after": "company",
			"description": "Used by interactive Telegram bot for employee authentication",
			"read_only": 1,
		},
		{
			"dt": "Employee",
			"fieldname": "self_service_password",
			"label": "Self Service Password",
			"fieldtype": "Password",
			"insert_after": "telegram_chat_id",
			"description": "Password for Telegram bot / self-service leave application",
		},
	]

	for field in custom_fields:
		if not frappe.db.exists("DocType", field["dt"]):
			continue
		if frappe.db.exists(
			"Custom Field",
			{"dt": field["dt"], "fieldname": field["fieldname"]},
		):
			continue
		try:
			custom_field = frappe.get_doc(
				{
					"doctype": "Custom Field",
					**field,
				}
			)
			custom_field.insert(ignore_permissions=True)
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(
				message=f"Failed to add custom field {field.get('fieldname')}: {e}",
				title="ERPNext Telegram Install",
			)


def setup_procfile():
	"""Ensure the bot process is in the bench Procfile."""
	import os
	procfile_path = "Procfile" # bench root is CWD
	if not os.path.exists(procfile_path):
		return

	cmd = "telegram_bot: bench execute erpnext_telegram_integration.bot.leave_bot.run"
	
	try:
		with open(procfile_path, "r+") as f:
			content = f.read()
			if cmd in content:
				return

			# Ensure we are on a new line
			if content and not content.endswith("\n"):
				f.write("\n")
			
			f.write(f"{cmd}\n")
		
		print("Added telegram_bot to Procfile")
	except Exception:
		pass
