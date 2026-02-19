# -*- coding: utf-8 -*-
# Copyright (c) 2019, Youssef Restom and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import telegram
import asyncio
from frappe.model.document import Document
from frappe.utils.data import quoted
from bs4 import BeautifulSoup


class TelegramSettings(Document):
	def validate(self):
		if self.enable_interactive_bot:
			if "hrms" not in frappe.get_installed_apps():
				frappe.throw((
					"The <b>Interactive Bot</b> feature requires the <b>HRMS</b> app to be installed. "
					"Please install HRMS or disable the Interactive Bot."
				))

	def on_update(self):
		"""Clear cache on update so bot picks up changes immediately."""
		frappe.cache().delete_value("bot_default_language")



@frappe.whitelist()
def send_to_telegram(telegram_user, message, reference_doctype=None, reference_name=None, attachment=None):

	space = "\n" * 2
	telegram_chat_id = frappe.db.get_value('Telegram User Settings', telegram_user,'telegram_chat_id')
	telegram_settings = frappe.db.get_value('Telegram User Settings', telegram_user,'telegram_settings')
	telegram_token = frappe.db.get_value('Telegram Settings', telegram_settings,'telegram_token')
	bot = telegram.Bot(token=telegram_token)


	if reference_doctype and reference_name:
		if message:
			soup = BeautifulSoup(message)
			message = soup.get_text('\n')
			if type(attachment) is str:
				attachment = int(attachment)
			else:
				if attachment:
					attachment = 1
			if attachment == 1:
				attachment_url = get_url_for_telegram(reference_doctype, reference_name)
				message = message + space + attachment_url
			asyncio.run(bot.send_message(chat_id=telegram_chat_id, text=message))
	else:
		message = space + str(message) + space
		asyncio.run(bot.send_message(chat_id=telegram_chat_id, text=message))



def get_url_for_telegram(doctype, name):
	doc = frappe.get_doc(doctype, name)
	return "{url}/api/method/erpnext_telegram_integration.get_pdf.pdf?doctype={doctype}&name={name}&key={key}".format(
		url=frappe.utils.get_url(),
		doctype=quoted(doctype),
		name=quoted(name),
		key=doc.get_signature()
	)


