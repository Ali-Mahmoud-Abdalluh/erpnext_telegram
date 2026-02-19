import frappe
from erpnext_telegram_integration.bot import i18n
import sys

def run():
    print("--- DEBUGGING LANGUAGE RESOLUTION ---")
    
    # 1. Check DB directly
    settings = frappe.get_all("Telegram Settings", filters={"enable_interactive_bot": 1}, fields=["name", "bot_default_language"])
    print(f"DB Settings Found: {settings}")
    
    if settings:
        lang_name = settings[0].get("bot_default_language")
        print(f"Language in DB (Name): '{lang_name}'")
        
        # Check manual map
        manual_map = {
            "Arabic": "ar",
            "English": "en",
            "Spanish": "es",
            "French": "fr",
            "German": "de",
        }
        print(f"Mapping '{lang_name}' in manual map? {lang_name in manual_map} -> {manual_map.get(lang_name)}")
        
        # Check Language DocType
        lang_code = frappe.db.get_value("Language", lang_name, "language_code")
        print(f"Language DocType Lookup for '{lang_name}': {lang_code}")

    # 2. Check i18n logic
    print("\n--- CHECKING I18N MODULE ---")
    
    # Clear cache to be sure
    frappe.cache().delete_value("bot_default_language")
    
    resolved_lang = i18n.get_bot_lang()
    print(f"i18n.get_bot_lang() returns: '{resolved_lang}'")
    
    msg_welcome = i18n.msg("welcome_new")
    print(f"i18n.msg('welcome_new') preview:\n{msg_welcome[:50]}...")
    
    print("\n--- DONE ---")
