
import frappe
import unittest
from erpnext_telegram_integration.bot.leave_bot import validate_credentials, rate_limit_check

class TestLeaveBot(unittest.TestCase):
	def setUp(self):
		# Create a dummy employee
		if not frappe.db.exists("Employee", "EMP-BOT-TEST"):
			self.employee = frappe.get_doc({
				"doctype": "Employee",
				"employee": "EMP-BOT-TEST",
				"first_name": "Bot Test",
				"company": frappe.db.get_value("Company", filters={}, fieldname="name") or "Test Company",
				"status": "Active",
				"date_of_joining": "2020-01-01",
				"date_of_birth": "1990-01-01",
				"gender": "Male",
				"self_service_password": "securepassword123"
			}).insert(ignore_permissions=True)
		else:
			self.employee = frappe.get_doc("Employee", "EMP-BOT-TEST")
			self.employee.self_service_password = "securepassword123"
			self.employee.save(ignore_permissions=True)

		self.chat_id = "123456789"
		frappe.cache().delete_value(f"telegram_bot_login_failed:{self.chat_id}")

	def tearDown(self):
		frappe.cache().delete_value(f"telegram_bot_login_failed:{self.chat_id}")
		if frappe.db.exists("Employee", "EMP-BOT-TEST"):
			frappe.delete_doc("Employee", "EMP-BOT-TEST")

	def test_validate_credentials_success(self):
		"""Test successful login."""
		emp = validate_credentials(self.employee.name, "securepassword123", chat_id=self.chat_id)
		self.assertIsNotNone(emp)
		self.assertEqual(emp.name, self.employee.name)

	def test_validate_credentials_failure(self):
		"""Test failed login."""
		emp = validate_credentials(self.employee.name, "wrongpassword", chat_id=self.chat_id)
		self.assertIsNone(emp)

	def test_rate_limiting(self):
		"""Test rate limiting after 5 failed attempts."""
		# 1
		validate_credentials(self.employee.name, "wrong", chat_id=self.chat_id)
		# 2
		validate_credentials(self.employee.name, "wrong", chat_id=self.chat_id)
		# 3
		validate_credentials(self.employee.name, "wrong", chat_id=self.chat_id)
		# 4
		validate_credentials(self.employee.name, "wrong", chat_id=self.chat_id)
		# 5
		validate_credentials(self.employee.name, "wrong", chat_id=self.chat_id)

		# 6 - Should be rate limited
		result = validate_credentials(self.employee.name, "securepassword123", chat_id=self.chat_id)
		self.assertEqual(result, "RATE_LIMITED")

	def test_audit_log_creation(self):
		"""Test if audit log is created on login."""
		# Clear existing logs
		frappe.db.sql("DELETE FROM `tabTelegram Bot Audit` WHERE chat_id=%s", self.chat_id)
		
		# Successful login
		validate_credentials(self.employee.name, "securepassword123", chat_id=self.chat_id)
		
		# Check log - Wait, log_audit is called OUTSIDE validate_credentials for success case in bot handler
		# But inside validate_credentials for RATE_LIMIT case.
		# Let's check for RATE_LIMIT log
		
		# Trigger rate limit
		for _ in range(6):
			validate_credentials(self.employee.name, "wrong", chat_id=self.chat_id)
			
		logs = frappe.get_all("Telegram Bot Audit", filters={"chat_id": self.chat_id, "action": "Login", "status": "Failure"}, fields=["name", "message"])
		self.assertTrue(len(logs) > 0)
		self.assertIn("Rate limit exceeded", [l.message for l in logs])

