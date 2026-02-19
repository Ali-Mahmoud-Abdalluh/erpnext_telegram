## Summary
This PR adds several enhancements to the Telegram integration:

### 1. Interactive Leave Bot
- Employees can apply for leave directly from Telegram
- Systemd service setup for production deployment
- Chat ID retrieval via bot for Telegram User Settings
- Multi-language ready (Arabic implemented, extensible for other languages via Frappe translations)

### 2. Advanced Dynamic Recipients
- Enhanced dynamic recipient handling for Telegram notifications
- Support for multiple recipient types from DocType link fields (Customer, Supplier, Employee, etc.)
- New child table and recipient doctype for flexible configuration

### 3. Other changes
- Updated README with Interactive Leave Bot setup instructions
- New bot module with leave request workflow
- Configuration scripts for systemd service

## How to test
1. Enable Interactive Bot in Telegram Settings
2. Set Self Service Password on Employee records
3. Run the bot (systemd or manual)
4. Test leave application via Telegram
5. Configure dynamic recipients in Telegram Notification and verify delivery
