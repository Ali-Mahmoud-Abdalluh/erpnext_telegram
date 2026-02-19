# -*- coding: utf-8 -*-
"""
Interactive Telegram Bot for Leave Applications.

Run with: bench --site [sitename] execute erpnext_telegram_integration.bot.leave_bot.run
"""
from __future__ import unicode_literals

import calendar
import functools
import logging
import re
import warnings
from datetime import date, datetime, timedelta

import frappe

from erpnext_telegram_integration.bot.i18n import (
    get_lang,
    matches,
    msg,
    t,
)

# Suppress PTBUserWarning about per_message (our mix of MessageHandler + CallbackQueryHandler works fine)
warnings.filterwarnings("ignore", message=".*per_message.*", category=UserWarning)

# DB connection errors that require reconnection (long-running bot, MySQL may close idle connections)
_DB_ERRORS = ()
try:
    import pymysql
    _DB_ERRORS = (pymysql.err.OperationalError, pymysql.err.InterfaceError)
except ImportError:
    pass


def _ensure_db_and_retry(handler):
    """Decorator: on DB connection errors, reconnect and retry handler once."""
    @functools.wraps(handler)
    async def wrapped(update, context):
        try:
            return await handler(update, context)
        except _DB_ERRORS as e:
            err_str = str(e).lower()
            if "gone away" in err_str or "connection reset" in err_str or "interface" in err_str:
                logger.warning("DB connection lost, reconnecting: %s", e)
                frappe.connect()
                return await handler(update, context)
            raise
    return wrapped
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)

# Match Cancel in any supported language (regex built from BOT_STRINGS)
def _cancel_regex():
    from erpnext_telegram_integration.bot.i18n import BOT_STRINGS
    cancels = BOT_STRINGS.get("cancel", {})
    if not cancels:
        return r"^Cancel$"
    escaped = [re.escape(t) for t in cancels.values() if t]
    return r"^(" + "|".join(escaped) + r)$" if escaped else r"^Cancel$"
_FILTER_CANCEL = filters.Regex(_cancel_regex())

# Conversation states
(
    ID_INPUT,
    PASSWORD_INPUT,
    MAIN_MENU,
    DATE_PICKER,
    LEAVE_TYPE_SELECT,
    HALF_DAY_SELECT,
    REASON_INPUT,
    TOKEN_INPUT,
) = range(8)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.WARNING,
)
logger = logging.getLogger(__name__)

# Suppress cssutils CSS parsing errors (from Frappe/weasyprint when loading)
logging.getLogger("cssutils").setLevel(logging.CRITICAL)


# --- HELPERS ---
def create_calendar(year, month):
    markup = []
    markup.append(
        [InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="IGNORE")]
    )
    days = ["M", "T", "W", "T", "F", "S", "S"]
    markup.append([InlineKeyboardButton(day, callback_data="IGNORE") for day in days])

    my_calendar = calendar.monthcalendar(year, month)
    for week in my_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="IGNORE"))
            else:
                row.append(
                    InlineKeyboardButton(
                        str(day),
                        callback_data=f"CALENDAR|SELECT|{year}|{month}|{day}",
                    )
                )
        markup.append(row)

    curr = date(year, month, 1)
    prev = curr - timedelta(days=1)
    next_m = curr + timedelta(days=32)
    markup.append(
        [
            InlineKeyboardButton(
                "<", callback_data=f"CALENDAR|CHANGE|{prev.year}|{prev.month}"
            ),
            InlineKeyboardButton(" ", callback_data="IGNORE"),
            InlineKeyboardButton(
                ">", callback_data=f"CALENDAR|CHANGE|{next_m.year}|{next_m.month}"
            ),
        ]
    )
    return InlineKeyboardMarkup(markup)


async def send_msg(update, context, text, reply_markup=None):
    return await context.bot.send_message(
        chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup
    )


def main_menu_keyboard(lang="en"):
    return ReplyKeyboardMarkup(
        [[t("request_leave", lang)], [t("link_token", lang)], [t("logout", lang)]],
        resize_keyboard=True,
    )


def id_input_keyboard(lang="en"):
    """Keyboard when waiting for employee ID - includes option to link token."""
    return ReplyKeyboardMarkup([[t("link_token", lang)]], resize_keyboard=True)


def token_input_keyboard(lang="en"):
    """Keyboard when waiting for token - cancel option."""
    return ReplyKeyboardMarkup([[t("cancel", lang)]], resize_keyboard=True)


# --- ERP FUNCTIONS (using Frappe directly) ---
def get_employee_by_chat_id(chat_id):
    """Find active employee by Telegram chat ID."""
    employees = frappe.get_all(
        "Employee",
        filters=[
            ["telegram_chat_id", "=", str(chat_id)],
            ["status", "=", "Active"],
        ],
        fields=["name", "employee_name"],
        limit_page_length=1,
    )
    return employees[0] if employees else None


def lookup_employee_by_number(number_input):
    """Find employee by employee number (numeric part of name)."""
    try:
        target_int = int(number_input)
    except ValueError:
        return None, None

    employees = frappe.get_all(
        "Employee",
        filters=[["status", "=", "Active"]],
        fields=["name", "employee_name"],
        limit_page_length=50,
    )

    for emp in employees:
        match = re.search(r"(\d+)$", emp["name"])
        if match and int(match.group(1)) == target_int:
            return emp["name"], emp["employee_name"]
    return None, None


def validate_credentials(employee_id, password):
    """Validate employee password for self-service."""
    if not password or not password.strip():
        return None

    password = password.strip()
    try:
        emp = frappe.get_doc("Employee", employee_id)
        # Try both field names: standard custom field and raw DB column name
        stored = (
            emp.get("self_service_password")
            or emp.get("custom_self_service_password")
            or frappe.db.get_value("Employee", employee_id, "self_service_password")
            or frappe.db.get_value("Employee", employee_id, "custom_self_service_password")
        )
        if stored and str(stored).strip() == password:
            return emp
    except Exception as e:
        logger.debug("validate_credentials failed for %s: %s", employee_id, e)
    return None


def update_chat_id(employee_id, chat_id):
    """Update employee's Telegram chat ID."""
    try:
        frappe.db.set_value("Employee", employee_id, "telegram_chat_id", str(chat_id))
        frappe.db.commit()
    except Exception as e:
        logger.exception("Failed to update chat_id: %s", e)


def get_leaves_details(employee_id, target_date):
    """Get available leave types and approver for employee."""
    available_leaves = []
    approver = None

    if not frappe.db.exists("DocType", "Leave Application"):
        return available_leaves, approver

    try:
        leave_types = frappe.get_all(
            "Leave Type",
            fields=["name", "is_lwp", "allow_negative"],
        )
        leave_config = {lt["name"]: lt for lt in leave_types}

        data = {}
        try:
            # Use HRMS method if available (ERPNext)
            from hrms.hr.doctype.leave_application.leave_application import (
                get_leave_details,
            )

            data = get_leave_details(employee_id, target_date) or {}
        except ImportError:
            pass

        approver = data.get("leave_approver")
        allocs = data.get("leave_allocation", {})
        lwps = data.get("lwps", [])

        for t_name, config in leave_config.items():
            bal = allocs.get(t_name, {}).get("remaining_leaves", 0)
            if bal > 0:
                available_leaves.append(
                    {"name": t_name, "balance": bal, "display": f"{t_name} ({bal})"}
                )
            elif t_name in lwps or config.get("is_lwp"):
                available_leaves.append(
                    {"name": t_name, "balance": 0, "display": t_name}
                )
            elif config.get("allow_negative"):
                available_leaves.append(
                    {"name": t_name, "balance": bal, "display": t_name}
                )

        # Fallback: if HRMS returned nothing, try basic allocation
        if not available_leaves and frappe.db.exists("DocType", "Leave Allocation"):
            allocs_list = frappe.get_all(
                "Leave Allocation",
                filters=[
                    ["employee", "=", employee_id],
                    ["docstatus", "=", 1],
                    ["from_date", "<=", target_date],
                    ["to_date", ">=", target_date],
                ],
                fields=["leave_type", "total_leaves_allocated", "leaves_taken"],
            )
            for a in allocs_list:
                remaining = (a.get("total_leaves_allocated") or 0) - (
                    a.get("leaves_taken") or 0
                )
                if remaining > 0:
                    available_leaves.append(
                        {
                            "name": a["leave_type"],
                            "balance": remaining,
                            "display": f"{a['leave_type']} ({remaining})",
                        }
                    )
    except Exception as e:
        logger.exception("get_leaves_details failed: %s", e)

    return available_leaves, approver


def clean_error_message(text, lang="en"):
    """Translate common errors to user language."""
    if "Attendance" in text and "already marked" in text:
        return msg("err_attendance_exists", lang)
    if "outside leave allocation" in text:
        return msg("err_outside_allocation", lang)
    if "insufficient balance" in text:
        return msg("err_insufficient_balance", lang)
    if "already applied" in text:
        return msg("err_already_applied", lang)
    return msg("err_unknown", lang)


def submit_leave_application(context_user_data):
    """Create Leave Application via Frappe."""
    reason = context_user_data.get("leave_reason", "")
    doc_dict = {
        "doctype": "Leave Application",
        "employee": context_user_data["employee_id"],
        "leave_type": context_user_data["leave_type"],
        "from_date": context_user_data["from_date"],
        "to_date": context_user_data["to_date"],
        "half_day": context_user_data["half_day"],
    }
    # Support both reason_for_leave (ERPNext) and description (some versions)
    meta = frappe.get_meta("Leave Application")
    if meta.has_field("reason_for_leave"):
        doc_dict["reason_for_leave"] = reason
    elif meta.has_field("description"):
        doc_dict["description"] = reason

    doc = frappe.get_doc(doc_dict)

    if context_user_data.get("leave_approver") and doc.meta.has_field("leave_approver"):
        doc.leave_approver = context_user_data["leave_approver"]

    doc.insert()
    frappe.db.commit()

    # Apply workflow if exists
    if doc.get("workflow_state"):
        try:
            frappe.model.workflow.apply_workflow(doc, "Apply")
            frappe.db.commit()
        except Exception:
            pass

    return doc.name, None


# --- BOT HANDLERS ---
@_ensure_db_and_retry
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start and initial message."""
    lang = get_lang(context.user_data)
    # 1. AUTO LOGIN for returning users
    emp_id = context.user_data.get("employee_id")
    if not emp_id:
        existing = get_employee_by_chat_id(update.effective_chat.id)
        if existing:
            emp_id = existing["name"]
            context.user_data["employee_id"] = emp_id
            context.user_data["employee_name"] = existing["employee_name"]

    # 2. IF LOGGED IN
    if emp_id:
        text = (update.message.text or "").strip() if update.message else ""
        if matches(text, "request_leave") or matches(text, "logout") or matches(text, "link_token"):
            return await menu_handler(update, context)
        await send_msg(
            update,
            context,
            msg("welcome_back", lang, context.user_data["employee_name"]),
            reply_markup=main_menu_keyboard(lang),
        )
        return MAIN_MENU

    # 3. NEW USER
    user_input = (update.message.text or "").strip()

    if user_input.startswith("/"):
        await send_msg(
            update,
            context,
            msg("welcome_new", lang),
            reply_markup=id_input_keyboard(lang),
        )
        return ID_INPUT

    if matches(user_input, "link_token"):
        context.user_data["token_return_state"] = ID_INPUT
        await send_msg(
            update,
            context,
            msg("send_token", lang),
            reply_markup=token_input_keyboard(lang),
        )
        return TOKEN_INPUT

    if user_input.isdigit():
        return await get_employee_id(update, context)

    await send_msg(
        update,
        context,
        msg("welcome_new", lang),
        reply_markup=id_input_keyboard(lang),
    )
    return ID_INPUT


@_ensure_db_and_retry
async def get_employee_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle employee ID input."""
    lang = get_lang(context.user_data)
    user_input = (update.message.text or "").strip()

    if matches(user_input, "link_token"):
        context.user_data["token_return_state"] = ID_INPUT
        await send_msg(
            update,
            context,
            msg("send_token", lang),
            reply_markup=token_input_keyboard(lang),
        )
        return TOKEN_INPUT

    if not user_input.isdigit():
        await send_msg(
            update,
            context,
            msg("digits_only", lang),
            reply_markup=id_input_keyboard(lang),
        )
        return ID_INPUT

    search_msg = await send_msg(
        update, context, msg("searching", lang), reply_markup=ReplyKeyboardRemove()
    )
    fid, fname = lookup_employee_by_number(user_input)
    try:
        await context.bot.delete_message(update.effective_chat.id, search_msg.message_id)
    except Exception:
        pass

    if not fid:
        await send_msg(
            update,
            context,
            msg("employee_not_found", lang),
            reply_markup=id_input_keyboard(lang),
        )
        return ID_INPUT

    context.user_data["temp_emp_id"] = fid
    await send_msg(
        update,
        context,
        msg("enter_password", lang, fname, fid),
        reply_markup=ReplyKeyboardRemove(),
    )
    return PASSWORD_INPUT


@_ensure_db_and_retry
async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate password and complete login."""
    lang = get_lang(context.user_data)
    pwd = update.message.text.strip()
    emp_id = context.user_data.get("temp_emp_id")
    emp = validate_credentials(emp_id, pwd)

    if emp:
        update_chat_id(emp_id, update.effective_chat.id)
        context.user_data["employee_id"] = emp_id
        context.user_data["employee_name"] = emp.employee_name
        await send_msg(
            update,
            context,
            msg("login_success", lang, emp.employee_name),
            reply_markup=main_menu_keyboard(lang),
        )
        return MAIN_MENU
    else:
        await send_msg(update, context, msg("wrong_password", lang))
        return ConversationHandler.END


@_ensure_db_and_retry
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu (leave request / logout)."""
    lang = get_lang(context.user_data)
    text = (update.message.text or "").strip()

    if matches(text, "link_token"):
        context.user_data["token_return_state"] = MAIN_MENU
        await send_msg(
            update,
            context,
            msg("send_token", lang),
            reply_markup=token_input_keyboard(lang),
        )
        return TOKEN_INPUT

    if matches(text, "logout"):
        update_chat_id(context.user_data.get("employee_id"), "")
        context.user_data.clear()
        await send_msg(
            update, context, msg("logged_out", lang), reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    elif matches(text, "request_leave"):
        now = datetime.now()
        context.user_data["calendar_step"] = "FROM"
        await send_msg(
            update,
            context,
            msg("leave_start_date", lang),
            reply_markup=create_calendar(now.year, now.month),
        )
        return DATE_PICKER
    await send_msg(
        update,
        context,
        msg("choose_from_menu", lang),
        reply_markup=main_menu_keyboard(lang),
    )
    return MAIN_MENU


@_ensure_db_and_retry
async def token_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token input when user chose 'Link Token'."""
    lang = get_lang(context.user_data)
    text = (update.message.text or "").strip()
    return_state = context.user_data.get("token_return_state", ID_INPUT)

    if matches(text, "cancel"):
        context.user_data.pop("token_return_state", None)
        if return_state == MAIN_MENU:
            await send_msg(
                update,
                context,
                msg("cancelled", lang),
                reply_markup=main_menu_keyboard(lang),
            )
            return MAIN_MENU
        await send_msg(
            update,
            context,
            msg("cancelled_enter_id", lang),
            reply_markup=id_input_keyboard(lang),
        )
        return ID_INPUT

    if _looks_like_token(text):
        if _is_token_in_db(update) and _handle_telegram_user_token(update, context, text):
            context.user_data.pop("token_return_state", None)
            success_msg = msg("token_success", lang, str(update.effective_chat.id))
            if return_state == MAIN_MENU:
                await send_msg(update, context, success_msg, reply_markup=main_menu_keyboard(lang))
                return MAIN_MENU
            success_msg = msg("token_success_enter_id", lang, str(update.effective_chat.id))
            await send_msg(
                update,
                context,
                success_msg,
                reply_markup=id_input_keyboard(lang),
            )
            return ID_INPUT
        await send_msg(
            update,
            context,
            msg("token_unknown", lang),
            reply_markup=token_input_keyboard(lang),
        )
        return TOKEN_INPUT

    await send_msg(
        update,
        context,
        msg("send_token_only", lang),
        reply_markup=token_input_keyboard(lang),
    )
    return TOKEN_INPUT


async def _fallback_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback when no other handler matches - reset and prompt /start."""
    lang = get_lang(context.user_data)
    await send_msg(
        update,
        context,
        msg("unknown_send_start", lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def _date_picker_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unexpected text in DATE_PICKER (e.g. user types instead of using calendar)."""
    lang = get_lang(context.user_data)
    await send_msg(
        update,
        context,
        msg("use_calendar", lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    return DATE_PICKER


@_ensure_db_and_retry
async def calendar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle calendar callbacks."""
    query = update.callback_query
    await query.answer()
    if query.data == "IGNORE":
        return DATE_PICKER

    data = query.data.split("|")
    if data[1] == "CHANGE":
        await query.edit_message_reply_markup(
            reply_markup=create_calendar(int(data[2]), int(data[3]))
        )
        return DATE_PICKER

    lang = get_lang(context.user_data)
    sel = f"{int(data[2])}-{int(data[3]):02d}-{int(data[4]):02d}"
    if context.user_data.get("calendar_step") == "FROM":
        context.user_data["from_date"] = sel
        context.user_data["calendar_step"] = "TO"
        await query.edit_message_text(
            msg("start_date_ok", lang, sel),
            reply_markup=create_calendar(int(data[2]), int(data[3])),
        )
        return DATE_PICKER

    context.user_data["to_date"] = sel
    await query.delete_message()
    verify_msg = await send_msg(
        update, context, msg("verifying", lang), reply_markup=ReplyKeyboardRemove()
    )

    leaves, approver = get_leaves_details(
        context.user_data["employee_id"], context.user_data["from_date"]
    )
    if approver:
        context.user_data["leave_approver"] = approver

    try:
        await context.bot.delete_message(update.effective_chat.id, verify_msg.message_id)
    except Exception:
        pass

    if not leaves:
        await send_msg(
            update,
            context,
            msg("no_leaves", lang),
            reply_markup=main_menu_keyboard(lang),
        )
        return MAIN_MENU

    context.user_data["available_leaves"] = leaves
    btns = [[l["display"]] for l in leaves] + [[t("cancel", lang)]]
    await send_msg(
        update,
        context,
        msg("leave_type_prompt", lang),
        reply_markup=ReplyKeyboardMarkup(
            btns, one_time_keyboard=True, resize_keyboard=True
        ),
    )
    return LEAVE_TYPE_SELECT


@_ensure_db_and_retry
async def leave_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle leave type selection."""
    lang = get_lang(context.user_data)
    text = update.message.text
    if matches(text, "cancel"):
        return await menu_handler(update, context)

    name = text.split("(")[0].strip()
    available = context.user_data.get("available_leaves") or []
    match = next((l for l in available if l["name"] == name), None)
    if not match:
        btns = [[l["display"]] for l in available] + [[t("cancel", lang)]]
        await send_msg(
            update,
            context,
            msg("choose_leave_type", lang),
            reply_markup=ReplyKeyboardMarkup(btns, resize_keyboard=True, one_time_keyboard=True),
        )
        return LEAVE_TYPE_SELECT

    context.user_data["leave_type"] = match["name"]
    context.user_data["current_balance"] = match.get("balance", 0)
    await send_msg(
        update,
        context,
        msg("duration", lang),
        reply_markup=ReplyKeyboardMarkup(
            [[t("full_day", lang), t("half_day", lang)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    return HALF_DAY_SELECT


@_ensure_db_and_retry
async def half_day_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle half-day selection."""
    lang = get_lang(context.user_data)
    text = update.message.text
    if matches(text, "cancel"):
        return await menu_handler(update, context)
    if not matches(text, "full_day") and not matches(text, "half_day"):
        await send_msg(
            update,
            context,
            msg("choose_from_list", lang),
            reply_markup=ReplyKeyboardMarkup(
                [[t("full_day", lang), t("half_day", lang)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        return HALF_DAY_SELECT
    context.user_data["half_day"] = 1 if matches(text, "half_day") else 0
    await send_msg(
        update,
        context,
        msg("leave_reason", lang),
        reply_markup=ReplyKeyboardMarkup(
            [[t("skip", lang)]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return REASON_INPUT


@_ensure_db_and_retry
async def reason_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reason input and submit leave application."""
    lang = get_lang(context.user_data)
    text = update.message.text
    if matches(text, "cancel"):
        return await menu_handler(update, context)
    context.user_data["leave_reason"] = (
        "" if matches(text, "skip") else text
    )

    submit_msg = await send_msg(update, context, msg("submitting", lang))

    try:
        doc_name, err = submit_leave_application(context.user_data)
        try:
            await context.bot.delete_message(update.effective_chat.id, submit_msg.message_id)
        except Exception:
            pass

        if err:
            await send_msg(
                update,
                context,
                msg("failed", lang, clean_error_message(err, lang)),
                reply_markup=main_menu_keyboard(lang),
            )
        else:
            await send_msg(
                update,
                context,
                msg("submitted", lang, doc_name),
                reply_markup=main_menu_keyboard(lang),
            )
    except Exception as e:
        try:
            await context.bot.delete_message(update.effective_chat.id, submit_msg.message_id)
        except Exception:
            pass
        err_text = str(e)
        await send_msg(
            update,
            context,
            msg("failed", lang, clean_error_message(err_text, lang)),
            reply_markup=main_menu_keyboard(lang),
        )

    return MAIN_MENU


@_ensure_db_and_retry
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel."""
    lang = get_lang(context.user_data)
    await send_msg(update, context, msg("cancelled_short", lang))
    return ConversationHandler.END


def get_bot_token():
    """Get bot token from Telegram Settings (first one with interactive enabled)."""
    try:
        settings = frappe.get_all(
            "Telegram Settings",
            filters={"enable_interactive_bot": 1},
            fields=["name", "telegram_token"],
            limit=1,
        )
        if settings and settings[0].get("telegram_token"):
            return settings[0]["telegram_token"], settings[0]["name"]
    except Exception:
        pass
    
    # Fallback: first Telegram Settings
    settings = frappe.get_all(
        "Telegram Settings",
        fields=["name", "telegram_token"],
        limit=1,
    )
    if settings and settings[0].get("telegram_token"):
        return settings[0]["telegram_token"], settings[0]["name"]
    
    frappe.throw(
        "No valid Telegram Bot Token found. Please configure a bot token in Telegram Settings."
    )


def _looks_like_token(text):
    """Check if text matches token format: exactly 38 or 40 hex chars."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if t.startswith("/"):
        t = t[1:].strip()
    # Must be exactly 38 or 40 chars AND all hex
    if len(t) not in (38, 40):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in t)


def _is_token_in_db(update):
    """
    Check if the message is a valid token in the database (for our bot).
    Returns True if: (1) token exists and matches our bot, or (2) exactly one record has this token (single-bot).
    """
    if not update.message or not update.message.text:
        return False
    raw = (update.message.text or "").strip()
    if not _looks_like_token(raw):
        return False
    tokens_to_try = [raw]
    if raw.startswith("/"):
        tokens_to_try.append(raw[1:].strip())
    elif raw:
        tokens_to_try.append("/" + raw)
    try:
        bot_token, _ = get_bot_token()
    except Exception:
        return False
    for t in tokens_to_try:
        if not t:
            continue
        records = frappe.get_all(
            "Telegram User Settings",
            filters=[["telegram_token", "=", t]],
            fields=["name", "telegram_settings"],
            limit=20,
        )
        if not records:
            continue
        for rec in records:
            ts_name = rec.get("telegram_settings")
            if ts_name:
                ts_token = frappe.db.get_value("Telegram Settings", ts_name, "telegram_token")
                if ts_token == bot_token:
                    return True
        # Fallback: exactly one record (single-bot setup)
        if len(records) == 1:
            return True
    return False


def _handle_telegram_user_token(update, context, token_text):
    """
    If token matches a Telegram User Settings record for our bot, update chat_id and notify.
    Returns True if handled, False otherwise.
    Matches by token + bot token (not settings name) so it works regardless of Telegram Settings doc name.
    Fallback: if exactly one Telegram User Settings has this token, update it (handles single-bot setups).
    """
    raw = (token_text or "").strip()
    tokens_to_try = [raw]
    if raw.startswith("/"):
        tokens_to_try.append(raw[1:].strip())
    elif raw:
        tokens_to_try.append("/" + raw)

    try:
        bot_token, _ = get_bot_token()
    except Exception:
        return False

    for t in tokens_to_try:
        if not t:
            continue
        records = frappe.get_all(
            "Telegram User Settings",
            filters=[["telegram_token", "=", t]],
            fields=["name", "telegram_settings"],
            limit=20,
        )
        if not records:
            continue
        # Prefer: same bot (linked Telegram Settings has same telegram_token)
        for rec in records:
            ts_name = rec.get("telegram_settings")
            if not ts_name:
                continue
            ts_token = frappe.db.get_value("Telegram Settings", ts_name, "telegram_token")
            if ts_token == bot_token:
                chat_id = str(update.effective_chat.id)
                frappe.db.set_value("Telegram User Settings", rec["name"], "telegram_chat_id", chat_id)
                frappe.db.commit()
                return True
        # Fallback: exactly one record with this token (single-bot setup)
        if len(records) == 1:
            chat_id = str(update.effective_chat.id)
            frappe.db.set_value("Telegram User Settings", records[0]["name"], "telegram_chat_id", chat_id)
            frappe.db.commit()
            return True
    return False


def run():
    """Start the interactive leave bot."""
    frappe.connect()
    token, _ = get_bot_token()
    app = (
        ApplicationBuilder()
        .token(token)
        .persistence(PicklePersistence(filepath="bot_session.pickle"))
        .build()
    )

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, start),
        ],
        states={
            ID_INPUT: [
                CommandHandler("start", start),
                MessageHandler(filters.TEXT, get_employee_id),
            ],
            PASSWORD_INPUT: [MessageHandler(filters.TEXT, check_password)],
            MAIN_MENU: [MessageHandler(filters.TEXT, menu_handler)],
            TOKEN_INPUT: [MessageHandler(filters.TEXT, token_input_handler)],
            DATE_PICKER: [
                CallbackQueryHandler(calendar_handler),
                MessageHandler(_FILTER_CANCEL, menu_handler),
                MessageHandler(filters.TEXT, _date_picker_unknown_text),
            ],
            LEAVE_TYPE_SELECT: [MessageHandler(filters.TEXT, leave_type_handler)],
            HALF_DAY_SELECT: [MessageHandler(filters.TEXT, half_day_handler)],
            REASON_INPUT: [MessageHandler(filters.TEXT, reason_handler)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(_FILTER_CANCEL, menu_handler),
            MessageHandler(filters.TEXT, _fallback_unknown),
        ],
        persistent=True,
        name="hrms_leave_bot",
    )

    # Token handling is integrated into start() and get_employee_id() - no separate handler.
    # This ensures non-token messages always flow through the conversation and get a response.
    app.add_handler(conv, group=0)

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors and send a friendly message. Reconnect DB on connection errors."""
        err = context.error
        logger.exception("Bot error: %s", err)
        # Reconnect on DB errors so next message will work
        if err and _DB_ERRORS and isinstance(err, _DB_ERRORS):
            try:
                frappe.connect()
                logger.info("DB reconnected after error")
            except Exception as reconn_err:
                logger.exception("DB reconnect failed: %s", reconn_err)
        # Send friendly message if we have a chat to reply to
        if update is not None and isinstance(update, Update) and update.effective_chat:
            try:
                lang = get_lang(getattr(context, "user_data", None) or {})
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=msg("error_occurred", lang),
                )
            except Exception:
                pass

    app.add_error_handler(error_handler)

    print("Interactive Leave Bot is running... (Ctrl+C to stop)")
    app.run_polling()