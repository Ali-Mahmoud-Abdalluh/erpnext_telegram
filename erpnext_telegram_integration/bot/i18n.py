# -*- coding: utf-8 -*-
"""
Multi-language support for the Interactive Leave Bot.
Uses Bot Default Language from Telegram Settings (same for all users).
"""
from __future__ import unicode_literals

import frappe
import functools

# Button labels and short options - must match user input, so we need all translations
# Key -> {lang_code: translated_text}
# Add more languages by extending this dict and adding corresponding CSV in translations/
BOT_STRINGS = {
    "request_leave": {
        "en": "Request Leave",
        "ar": "طلب إجازة",
        "es": "Solicitar permiso",
        "fr": "Demander un congé",
        "de": "Urlaub beantragen",
        "hi": "अवकाश का अनुरोध",
        "it": "Richiedi permesso",
        "pt": "Solicitar licença",
        "ru": "Запросить отпуск",
        "tr": "İzin talep et",
        "zh": "申请请假",
        "ja": "休暇申請",
        "ko": "휴가 신청",
        "nl": "Verlof aanvragen",
        "pl": "Złóż wniosek urlopowy",
        "bn": "ছুটির অনুরোধ",
        "id": "Ajukan cuti",
        "th": "ขอลางาน",
        "vi": "Xin nghỉ phép",
    },
    "link_token": {
        "en": "Link Token",
        "ar": "ربط الرمز",
        "es": "Vincular token",
        "fr": "Lier le jeton",
        "de": "Token verknüpfen",
        "hi": "टोकन लिंक करें",
        "it": "Collega token",
        "pt": "Vincular token",
        "ru": "Связать токен",
        "tr": "Token bağla",
        "zh": "链接令牌",
        "ja": "トークンをリンク",
        "ko": "토큰 연결",
        "nl": "Token koppelen",
        "pl": "Połącz token",
        "id": "Tautkan token",
        "th": "ลิงก์โทเค็น",
        "vi": "Liên kết token",
    },
    "logout": {
        "en": "Logout",
        "ar": "تسجيل خروج",
        "es": "Cerrar sesión",
        "fr": "Déconnexion",
        "de": "Abmelden",
        "hi": "लॉग आउट",
        "it": "Esci",
        "pt": "Sair",
        "ru": "Выйти",
        "tr": "Çıkış yap",
        "zh": "退出登录",
        "ja": "ログアウト",
        "ko": "로그아웃",
        "nl": "Uitloggen",
        "pl": "Wyloguj",
        "id": "Keluar",
        "th": "ออกจากระบบ",
        "vi": "Đăng xuất",
    },
    "cancel": {
        "en": "Cancel",
        "ar": "إلغاء",
        "es": "Cancelar",
        "fr": "Annuler",
        "de": "Abbrechen",
        "hi": "रद्द करें",
        "it": "Annulla",
        "pt": "Cancelar",
        "ru": "Отмена",
        "tr": "İptal",
        "zh": "取消",
        "ja": "キャンセル",
        "ko": "취소",
        "nl": "Annuleren",
        "pl": "Anuluj",
        "bn": "বাতিল",
        "id": "Batal",
        "th": "ยกเลิก",
        "vi": "Hủy",
    },
    "full_day": {
        "en": "Full Day",
        "ar": "يوم كامل",
        "es": "Día completo",
        "fr": "Journée complète",
        "de": "Ganztägig",
        "hi": "पूरा दिन",
        "it": "Giornata intera",
        "pt": "Dia inteiro",
        "ru": "Полный день",
        "tr": "Tam gün",
        "zh": "全天",
        "ja": "終日",
        "ko": "전일",
        "nl": "Hele dag",
        "pl": "Cały dzień",
        "id": "Sehari penuh",
        "th": "เต็มวัน",
        "vi": "Cả ngày",
    },
    "half_day": {
        "en": "Half Day",
        "ar": "نصف يوم",
        "es": "Medio día",
        "fr": "Demi-journée",
        "de": "Halbtags",
        "hi": "आधा दिन",
        "it": "Mezza giornata",
        "pt": "Meio dia",
        "ru": "Полдня",
        "tr": "Yarım gün",
        "zh": "半天",
        "ja": "半日",
        "ko": "반나절",
        "nl": "Halve dag",
        "pl": "Pół dnia",
        "id": "Setengah hari",
        "th": "ครึ่งวัน",
        "vi": "Nửa ngày",
    },
    "skip": {
        "en": "Skip",
        "ar": "تخطى",
        "es": "Omitir",
        "fr": "Passer",
        "de": "Überspringen",
        "hi": "छोड़ें",
        "it": "Salta",
        "pt": "Pular",
        "ru": "Пропустить",
        "tr": "Atla",
        "zh": "跳过",
        "ja": "スキップ",
        "ko": "건너뛰기",
        "nl": "Overslaan",
        "pl": "Pomiń",
        "id": "Lewati",
        "th": "ข้าม",
        "vi": "Bỏ qua",
    },
}

# All languages we have button translations for (fallback: en)
SUPPORTED_LANGS = tuple(BOT_STRINGS["cancel"].keys())


def _fetch_bot_lang_from_db():
    try:
        settings = frappe.get_all(
            "Telegram Settings",
            filters={"enable_interactive_bot": 1},
            fields=["name", "bot_default_language"],
            limit=1,
            ignore_permissions=True
        )
        if not settings:
             # Fallback: first Telegram Settings
            settings = frappe.get_all(
                "Telegram Settings",
                fields=["name", "bot_default_language"],
                limit=1,
                ignore_permissions=True
            )

        if settings:
            lang_name = settings[0].get("bot_default_language")
            if not lang_name:
                return "en"
            
            # Manual Mapping for common cases where DB lookup might fail or be slow
            manual_map = {
                "Arabic": "ar",
                "English": "en",
                "Spanish": "es",
                "French": "fr",
                "German": "de",
            }
            if lang_name in manual_map:
                return manual_map[lang_name]

            # Resolve language code from Language doctype if it's a name like "Arabic"
            if len(lang_name) > 2:
                lang_code = frappe.db.get_value("Language", lang_name, "language_code")
                if lang_code:
                    return lang_code

            if lang_name in SUPPORTED_LANGS:
                return lang_name
            return "en"
            
    except Exception as e:
        print(f"Error getting bot lang: {e}")
        pass
    return "en"


def get_bot_lang():
    """
    Get bot language from Telegram Settings (Bot Default Language).
    Uses frappe.cache() to allow hot-reloading when settings change.
    """
    return frappe.cache().get_value("bot_default_language", generator=_fetch_bot_lang_from_db)


def get_lang(context_user_data=None):
    """Alias for get_bot_lang - language is now from settings, not user. Kept for API compatibility."""
    return get_bot_lang()


def t(key, lang=None):
    """Get translated button/short string. Falls back to English."""
    if key not in BOT_STRINGS:
        return key
    d = BOT_STRINGS[key]
    lang = lang or get_bot_lang()
    if lang and lang in d:
        return d[lang]
    return d.get("en", key)


def matches(user_input, key):
    """Check if user_input matches any translation of key."""
    if key not in BOT_STRINGS:
        return False
    user_input = (user_input or "").strip()
    for trans in BOT_STRINGS[key].values():
        if trans and user_input == trans:
            return True
    return False


def _set_lang_and_translate(lang, source):
    """Set frappe.local.lang and call frappe._() for message translation."""
    try:
        if not hasattr(frappe, "local") or frappe.local is None:
            return source
        old_lang = getattr(frappe.local, "lang", "en")
        frappe.local.lang = lang or "en"
        result = frappe._(source)
        frappe.local.lang = old_lang
        return result
    except Exception:
        return source


# Message keys -> {lang_code: translated_text}
MSG_SOURCES = {
    "welcome_back": {
        "en": "Welcome back, {0} 👋",
        "ar": "مرحباً بعودتك، {0} 👋",
    },
    "welcome_new": {
        "en": "Hello! 👋\n\nPlease enter your **Employee Number** only (e.g. 31)\nor press **Link Token** to link your account:",
        "ar": "مرحباً! 👋\n\nالرجاء إدخال **رقم الموظف** فقط (مثال: 31)\nأو اضغط على **ربط الرمز** لربط حسابك:",
    },
    "send_token": {
        "en": "🔗 Send the **Token** from Telegram User Settings (copy and paste here):\n\nOr press **Cancel** to go back.",
        "ar": "🔗 أرسل **الرمز** من إعدادات مستخدم تيليجرام (انسخ والصق هنا):\n\nأو اضغط **إلغاء** للعودة.",
    },
    "digits_only": {
        "en": "❌ Numbers only (e.g. 31)\nor press **Link Token** to link your account:",
        "ar": "❌ أرقام فقط (مثال: 31)\nأو اضغط **ربط الرمز** لربط حسابك:",
    },
    "searching": {
        "en": "⏳ Searching...",
        "ar": "⏳ جاري البحث...",
    },
    "employee_not_found": {
        "en": "❌ Employee not found. Try again\nor press **Link Token** to link your account:",
        "ar": "❌ الموظف غير موجود. حاول مرة أخرى\nأو اضغط **ربط الرمز** لربط حسابك:",
    },
    "enter_password": {
        "en": "Hello {0} ({1}).\n🔒 Enter **password**:",
        "ar": "مرحباً {0} ({1}).\n🔒 أدخل **كلمة المرور**:",
    },
    "login_success": {
        "en": "✅ Logged in.\nHello {0}",
        "ar": "✅ تم تسجيل الدخول.\nمرحباً {0}",
    },
    "wrong_password": {
        "en": "❌ Wrong password. /start",
        "ar": "❌ كلمة المرور غير صحيحة. /start",
    },
    "logged_out": {
        "en": "Logged out 👋",
        "ar": "تم تسجيل الخروج 👋",
    },
    "leave_start_date": {
        "en": "📅 Leave start date:",
        "ar": "📅 تاريخ بدء الإجازة:",
    },
    "choose_from_menu": {
        "en": "Choose from menu:",
        "ar": "اختر من القائمة:",
    },
    "cancelled": {
        "en": "Cancelled.",
        "ar": "تم الإلغاء.",
    },
    "cancelled_enter_id": {
        "en": "Cancelled.\n\nPlease enter **Employee Number** (e.g. 31):",
        "ar": "تم الإلغاء.\n\nالرجاء إدخال **رقم الموظف** (مثال: 31):",
    },
    "token_success": {
        "en": "✅ Chat ID saved successfully!\n\nChat ID: `{0}`\n\nRefresh Telegram User Settings form to see the saved value.",
        "ar": "✅ تم حفظ معرف المحادثة بنجاح!\n\nID: `{0}`\n\nقم بتحديث نموذج إعدادات مستخدم تيليجرام لرؤية القيمة المحفوظة.",
    },
    "token_success_enter_id": {
        "en": "✅ Chat ID saved successfully!\n\nChat ID: `{0}`\n\nRefresh Telegram User Settings form to see the saved value.\n\nPlease enter **Employee Number** (e.g. 31):",
        "ar": "✅ تم حفظ معرف المحادثة بنجاح!\n\nID: `{0}`\n\nقم بتحديث نموذج إعدادات مستخدم تيليجرام لرؤية القيمة المحفوظة.\n\nالرجاء إدخال **رقم الموظف** (مثال: 31):",
    },
    "token_unknown": {
        "en": "⚠️ Unknown token. Make sure it was created in Telegram User Settings and linked to the same bot (Telegram Settings with Interactive Bot enabled).\n\nTry again or press **Cancel**:",
        "ar": "⚠️ رمز غير معروف. تأكد من إنشائه في إعدادات مستخدم تيليجرام وربطه بنفس البوت (إعدادات تيليجرام مع تفعيل البوت التفاعلي).\n\nحاول مرة أخرى أو اضغط **إلغاء**:",
    },
    "send_token_only": {
        "en": "Please send the token only (40 chars) or press **Cancel**:",
        "ar": "الرجاء إرسال الرمز فقط (40 حرفاً) أو اضغط **إلغاء**:",
    },
    "unknown_send_start": {
        "en": "⚠️ I didn't understand. Send /start to begin again.",
        "ar": "⚠️ لم أفهم. أرسل /start للبدء من جديد.",
    },
    "use_calendar": {
        "en": "📅 Use the calendar above to select, or send **Cancel** to cancel.",
        "ar": "📅 استخدم التقويم أعلاه للاختيار، أو أرسل **إلغاء** للإلغاء.",
    },
    "start_date_ok": {
        "en": "✅ Start: {0}\n\n📅 End date:",
        "ar": "✅ البدء: {0}\n\n📅 تاريخ الانتهاء:",
    },
    "verifying": {
        "en": "⏳ Verifying...",
        "ar": "⏳ جاري التحقق...",
    },
    "no_leaves": {
        "en": "❌ No leave types available.",
        "ar": "❌ لا توجد أنواع إجازات متاحة.",
    },
    "leave_type_prompt": {
        "en": "👇 Leave type:",
        "ar": "👇 نوع الإجازة:",
    },
    "choose_leave_type": {
        "en": "❌ Choose leave type from the list:",
        "ar": "❌ اختر نوع الإجازة من القائمة:",
    },
    "duration": {
        "en": "Duration:",
        "ar": "المدة:",
    },
    "choose_from_list": {
        "en": "❌ Choose from list:",
        "ar": "❌ اختر من القائمة:",
    },
    "leave_reason": {
        "en": "Leave reason (or 'Skip'):",
        "ar": "سبب الإجازة (أو 'تخطى'):",
    },
    "submitting": {
        "en": "⏳ Submitting...",
        "ar": "⏳ جاري الإرسال...",
    },
    "failed": {
        "en": "❌ Failed: {0}",
        "ar": "❌ فشل: {0}",
    },
    "submitted": {
        "en": "✅ Submitted: {0}",
        "ar": "✅ تم التقديم: {0}",
    },
    "cancelled_short": {
        "en": "Cancelled.",
        "ar": "تم الإلغاء.",
    },
    "error_occurred": {
        "en": "⚠️ An error occurred. Please try again.",
        "ar": "⚠️ حدث خطأ. حاول مرة أخرى.",
    },
    "err_attendance_exists": {
        "en": "⛔ Attendance already marked for this day.",
        "ar": "⛔ تم تسجيل الحضور لهذا اليوم بالفعل.",
    },
    "err_outside_allocation": {
        "en": "Date is outside leave allocation period.",
        "ar": "التاريخ خارج فترة تخصيص الإجازة.",
    },
    "err_insufficient_balance": {
        "en": "Insufficient leave balance.",
        "ar": "رصيد الإجازة غير كافٍ.",
    },
    "err_already_applied": {
        "en": "⛔ Leave application already exists for this period.",
        "ar": "⛔ يوجد طلب إجازة بالفعل لهذه الفترة.",
    },
    "err_unknown": {
        "en": "An unknown error occurred.",
        "ar": "حدث خطأ غير معروف.",
    },
}


def msg(key, lang=None, *args, **kwargs):
    """Get translated message. Uses internal dictionary, falls back to English."""
    lang = lang or get_bot_lang()
    
    # Get the dictionary for the key (which contains translations)
    translations = MSG_SOURCES.get(key)
    
    if isinstance(translations, dict):
        # Look up language, fallback to 'en'
        source = translations.get(lang) or translations.get("en") or key
    else:
        # Fallback for keys that might still be string-only (legacy safety)
        source = translations or key

    if args or kwargs:
        try:
            source = source.format(*args, **kwargs)
        except Exception:
            pass
            
    return source
