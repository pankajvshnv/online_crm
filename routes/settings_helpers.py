from datetime import date, datetime
from decimal import Decimal
import base64
import hashlib
import os
import re
import secrets
from config import get_db_connection
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from flask import jsonify




def serialize_value(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        return float(value)
    return value


def serialize_rows(rows):
    return [
        {key: serialize_value(value) for key, value in row.items()}
        for row in rows
    ]


def make_unique_code(cursor, table_name, column_name, prefix):
    while True:
        code = f"{prefix}{secrets.token_hex(4).upper()}"
        cursor.execute(
            f"SELECT 1 FROM {table_name} WHERE {column_name} = %s LIMIT 1",
            (code,),
        )
        if not cursor.fetchone():
            return code


def json_error(message, status_code=400):
    return jsonify({"success": False, "message": message}), status_code


def parse_int(value, field_label, minimum=None, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_label} is required.")

    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field_label} must be at least {minimum}.")

    if maximum is not None and parsed > maximum:
        raise ValueError(f"{field_label} must be at most {maximum}.")

    return parsed


def get_status_filter():
    return [
        {
            "name": "status",
            "label": "Status",
            "options": [
                {"label": "Active", "value": 1},
                {"label": "Inactive", "value": 0},
            ],
        }
    ]


def get_page_size_options():
    return [
        10,
        20,
        50,
        100,
        {"label": "All", "value": "all"},
    ]


LEAD_STATUS_TONES = [
    {"value": "blue", "label": "Blue"},
    {"value": "green", "label": "Green"},
    {"value": "cyan", "label": "Cyan"},
    {"value": "teal", "label": "Teal"},
    {"value": "purple", "label": "Purple"},
    {"value": "indigo", "label": "Indigo"},
    {"value": "pink", "label": "Pink"},
    {"value": "rose", "label": "Rose"},
    {"value": "red", "label": "Red"},
    {"value": "orange", "label": "Orange"},
    {"value": "amber", "label": "Amber"},
    {"value": "yellow", "label": "Yellow"},
    {"value": "lime", "label": "Lime"},
    {"value": "slate", "label": "Slate"},
    {"value": "gray", "label": "Gray"},
]
LEAD_STATUS_TONE_VALUES = {tone["value"] for tone in LEAD_STATUS_TONES}


def normalize_mobile(raw_mobile):
    digits = re.sub(r"\D+", "", str(raw_mobile or "").strip())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits


def validate_indian_mobile(mobile_number):
    mobile = normalize_mobile(mobile_number)
    if len(mobile) != 10:
        return None, "Mobile number must be exactly 10 digits after normalization."
    if mobile[0] not in {"6", "7", "8", "9"}:
        return None, "Indian mobile number must start with 6, 7, 8, or 9."
    return mobile, ""


def clean_text(value, max_length, allowed_pattern=r"[^A-Za-z0-9 @._\-\(\)]"):
    cleaned = re.sub(allowed_pattern, " ", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_length]


def clean_name(value):
    return clean_text(value, 50, r"[^A-Za-z0-9 ]")


def clean_email(value):
    return clean_text(value, 50, r"[^A-Za-z0-9@._\-\(\)]")


def clean_address(value):
    return clean_text(value, 100, r"[^A-Za-z0-9 @._\-\(\)]")


def _mobile_key():
    secret_key = (os.getenv("SECRET_KEY") or "").strip()
    if not secret_key:
        raise RuntimeError("SECRET_KEY missing in .env")
    return hashlib.sha512(secret_key.encode("utf-8")).digest()


def encrypt_mobile(mobile_number):
    mobile, _message = validate_indian_mobile(mobile_number)
    if not mobile:
        return str(mobile_number or "").strip()[:15]
    return mobile


def decrypt_mobile(encrypted_mobile):
    return str(encrypted_mobile or "").strip()


def resolve_uuid_to_id(cursor, table_name, uuid_column, uuid_value):
    if not uuid_value:
        return None

    cursor.execute(
        f"SELECT id FROM {table_name} WHERE {uuid_column} = %s LIMIT 1",
        (uuid_value,),
    )
    row = cursor.fetchone()
    return row["id"] if row else None


def fetch_assigned_users(cursor, field_name, record_id):
    cursor.execute(f"""
        SELECT
            u.user_uuid,
            u.full_name,
            u.username,
            u.mobile,
            COALESCE(CAST(e.extension_number AS CHAR), '') AS extension_name,
            COALESCE(r.role_name, '') AS role_name,
            COALESCE(d.designation_name, '') AS designation_name,
            u.status
        FROM users u
        LEFT JOIN extensions e ON e.id = u.extension_id
        LEFT JOIN roles r ON r.id = u.role_id
        LEFT JOIN designations d ON d.id = u.designation_id
        WHERE u.{field_name} = %s
        ORDER BY u.full_name ASC
    """, (record_id,))
    return serialize_rows(cursor.fetchall())




# Fetch the logged user and reporting hierarchy.
def fetch_user_tree(cursor, logged_user_uuid):
    cursor.execute("""
        SELECT
            u.id,
            u.user_uuid,
            u.full_name,
            r.role_name
        FROM users u
        LEFT JOIN roles r ON r.id = u.role_id
        WHERE u.user_uuid = %s
          AND u.status = 1
        LIMIT 1
    """, (logged_user_uuid,))

    logged_user = cursor.fetchone()

    if not logged_user:
        return [], []

    from utils.permissions import has_permission

    if has_permission('global_access_scope', 'global_data_access'):
        cursor.execute("SELECT id, user_uuid FROM users WHERE status = 1 ORDER BY full_name ASC")
        all_users = cursor.fetchall()
        return [r["id"] for r in all_users], [r["user_uuid"] for r in all_users]

    allowed_user_ids = [
        logged_user["id"]
    ]

    allowed_user_uuids = [
        logged_user["user_uuid"]
    ]

    pending_ids = [
        logged_user["id"]
    ]

    while pending_ids:
        placeholders = ", ".join(
            ["%s"] * len(pending_ids)
        )

        cursor.execute(f"""
            SELECT
                id,
                user_uuid,
                full_name
            FROM users
            WHERE reporting_to_user_id
                IN ({placeholders})
              AND status = 1
            ORDER BY full_name ASC
        """, pending_ids)

        child_users = cursor.fetchall()
        pending_ids = []

        for user in child_users:
            if user["id"] in allowed_user_ids:
                continue

            allowed_user_ids.append(
                user["id"]
            )

            allowed_user_uuids.append(
                user["user_uuid"]
            )

            pending_ids.append(
                user["id"]
            )

    return (
        allowed_user_ids,
        allowed_user_uuids,
    )


# Fetch the logged user's number and calling settings.
def fetch_logged_user_settings(
    cursor,
    logged_user_uuid,
):
    cursor.execute("""
        SELECT
            number_show_hide,
            click_to_call
        FROM users
        WHERE user_uuid = %s
          AND status = 1
        LIMIT 1
    """, (logged_user_uuid,))

    user = cursor.fetchone()

    if not user:
        return {
            "number_show_hide": 1,
            "click_to_call": 0,
        }

    return {
        "number_show_hide": int(
            user.get("number_show_hide")
            or 0
        ),
        "click_to_call": int(
            user.get("click_to_call")
            or 0
        ),
    }


# Mask all mobile digits except the last four.
def mask_mobile_number(mobile_number):
    mobile_number = str(
        mobile_number or ""
    ).strip()

    if not mobile_number:
        return "NA"

    if len(mobile_number) <= 4:
        return mobile_number

    return (
        "*" * (
            len(mobile_number) - 4
        )
        + mobile_number[-4:]
    )


def format_mobile_display(raw_mobile, user_settings=None):
    """
    Central helper: Decrypts and formats mobile number based on user permissions (number_show_hide).
    If number_show_hide == 1 (default) -> Masked (e.g. ******3063).
    If number_show_hide == 0 -> Full decrypted number (e.g. 9876543063).
    """
    if not raw_mobile:
        return "NA", ""

    decrypted = decrypt_mobile(raw_mobile)
    if not decrypted:
        return "NA", ""

    show_hide = int(user_settings.get("number_show_hide", 1)) if user_settings else 1
    if show_hide == 1:
        display_text = mask_mobile_number(decrypted)
    else:
        display_text = decrypted

    return display_text, decrypted


def fetch_last_dialed_lead_uuid(cursor, logged_user_uuid):
    """
    Fetches the lead_uuid of the most recently dialed lead by the logged-in user from lead_activities.
    Optimized 2-step lookup to avoid scanning full leads table.
    """
    if not logged_user_uuid:
        return ""
    try:
        cursor.execute("""
            SELECT lead_id
            FROM lead_activities
            WHERE user_id = (SELECT id FROM users WHERE user_uuid = %s LIMIT 1)
              AND action_type = 'Click to Call'
            ORDER BY id DESC
            LIMIT 1
        """, (logged_user_uuid,))
        la_row = cursor.fetchone()
        if not la_row or not la_row.get("lead_id"):
            return ""

        cursor.execute("SELECT lead_uuid FROM leads WHERE id = %s LIMIT 1", (la_row["lead_id"],))
        l_row = cursor.fetchone()
        return l_row["lead_uuid"] if l_row else ""
    except Exception:
        return ""


def build_mobile_button_context(raw_mobile, lead_uuid, lead_name, call_status=0, user_settings=None, last_dialed_lead_uuid=""):
    """
    Central helper function to generate Click-to-Call button metadata & HTML attributes for any page.
    click_to_call == 1 -> Active (Button enabled)
    click_to_call == 0 -> Inactive (Plain text display)
    """
    display_text, decrypted = format_mobile_display(raw_mobile, user_settings)
    is_called = (call_status == 1 or call_status == "1")
    click_to_call_active = (int(user_settings.get("click_to_call", 0)) == 1) if user_settings else True
    is_last_dialed = bool(lead_uuid and last_dialed_lead_uuid and str(lead_uuid) == str(last_dialed_lead_uuid))

    btn_class = "btn-outline-success" if (is_last_dialed or is_called) else "btn-outline-primary"
    
    if is_last_dialed:
        icon_html = '<span class="spinner-grow spinner-grow-sm text-success last-dialed-dot me-1" role="status" style="width: 8px; height: 8px;"></span>'
    elif is_called:
        icon_html = '<i class="mdi mdi-phone-check-outline me-1"></i>'
    else:
        icon_html = '<i class="mdi mdi-phone-outline me-1"></i>'

    title_text = f"Last Dialed Call: {display_text}" if is_last_dialed else (f"Called: {display_text}" if is_called else f"Click to Call {lead_name or ''}".strip())

    show_hide = int(user_settings.get("number_show_hide", 1)) if user_settings else 1
    safe_mobile = display_text if show_hide == 1 else (raw_mobile or "")
    safe_decrypted = display_text if show_hide == 1 else decrypted

    return {
        "raw_mobile": safe_mobile,
        "decrypted_mobile": safe_decrypted,
        "display_text": display_text,
        "call_status": int(call_status or 0),
        "click_to_call_active": click_to_call_active,
        "is_last_dialed": is_last_dialed,
        "btn_class": f"btn {btn_class} btn-sm btn-click-to-call d-inline-flex align-items-center gap-1",
        "icon_html": icon_html,
        "icon_class": "mdi-phone-check-outline" if is_called else "mdi-phone-outline",
        "title": title_text,
        "lead_uuid": lead_uuid or "",
        "lead_name": lead_name or "Contact",
    }


def apply_mobile_and_last_dialed_context(row_dict, user_settings, last_dialed_lead_uuid):
    """
    Central reusable helper function: Attaches decrypted_mobile, mobile_display,
    click_to_call_active, and is_last_dialed status to any lead/contact row dictionary across any page.
    """
    raw_mobile = str(
        row_dict.get("mobile_number")
        or row_dict.get("mobile")
        or row_dict.get("phone_number")
        or ""
    ).strip()
    lead_uuid = str(
        row_dict.get("lead_uuid")
        or row_dict.get("uuid")
        or ""
    ).strip()

    display_text, decrypted = format_mobile_display(raw_mobile, user_settings)
    click_to_call_active = (int(user_settings.get("click_to_call", 0)) == 1) if user_settings else True
    is_last_dialed = bool(lead_uuid and last_dialed_lead_uuid and str(lead_uuid) == str(last_dialed_lead_uuid))

    show_hide = int(user_settings.get("number_show_hide", 1)) if user_settings else 1
    if show_hide == 1:
        row_dict["mobile_number"] = display_text
        row_dict["decrypted_mobile"] = display_text
    else:
        row_dict["mobile_number"] = raw_mobile
        row_dict["decrypted_mobile"] = decrypted

    row_dict["mobile_display"] = display_text
    row_dict["click_to_call_active"] = click_to_call_active
    row_dict["is_last_dialed"] = is_last_dialed
    return row_dict


def calculate_free_trial_expiry(start_date_val, trial_days=None, cursor=None):
    """
    Calculates free trial expiry date by adding trial_days business days to start_date,
    skipping Saturdays (5) and Sundays (6).
    If trial_days is None, fetches 'free_trial_days' setting from system_settings.
    """
    import datetime

    if cursor and (trial_days is None or not str(trial_days).isdigit()):
        cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'free_trial_days' LIMIT 1")
        row = cursor.fetchone()
        trial_days = int(row["setting_value"]) if (row and str(row.get("setting_value", "")).isdigit()) else 7

    try:
        trial_days = int(trial_days or 7)
    except (ValueError, TypeError):
        trial_days = 7

    if isinstance(start_date_val, str):
        try:
            current_date = datetime.datetime.strptime(start_date_val[:10], "%Y-%m-%d").date()
        except ValueError:
            current_date = datetime.date.today()
    elif isinstance(start_date_val, datetime.datetime):
        current_date = start_date_val.date()
    elif isinstance(start_date_val, datetime.date):
        current_date = start_date_val
    else:
        current_date = datetime.date.today()

    days_counted = 0
    while True:
        if current_date.weekday() < 5:  # Monday to Friday
            days_counted += 1
            if days_counted >= trial_days:
                break
        current_date += datetime.timedelta(days=1)

    return current_date


def fetch_owner_filter_options(cursor, logged_user_uuid):
    """
    Central helper function to fetch reporting hierarchy users for Owner filter.
    Returns list of owner dicts and default selected owner (logged-in user).
    """
    allowed_user_ids, allowed_user_uuids = fetch_user_tree(cursor, logged_user_uuid)
    owners = []

    if allowed_user_uuids:
        placeholders = ", ".join(["%s"] * len(allowed_user_uuids))
        cursor.execute(f"""
            SELECT user_uuid, full_name
            FROM users
            WHERE user_uuid IN ({placeholders}) AND status = 1
            ORDER BY full_name ASC
        """, allowed_user_uuids)
        owners = cursor.fetchall()

    return {
        "owners": owners,
        "default_owner": logged_user_uuid,
        "allowed_user_ids": allowed_user_ids,
        "allowed_user_uuids": allowed_user_uuids,
    }


# Fetch source limits assigned to the logged user's role.
def fetch_lead_source_limit_buttons(
    cursor,
    logged_user_uuid,
):
    cursor.execute("""
        SELECT id, role_id
        FROM users
        WHERE user_uuid = %s
          AND status = 1
        LIMIT 1
    """, (logged_user_uuid,))

    user = cursor.fetchone()

    if (
        not user
        or not user.get("role_id")
    ):
        return []

    user_id = user["id"]

    cursor.execute("""
        SELECT
            l.source_id,
            l.pending_lead_limit,
            l.daily_lead_limit,
            l.fetch_lead_limit,
            s.source_name
        FROM lead_source_limits l
        INNER JOIN lead_sources s
            ON s.id = l.source_id
        WHERE l.role_id = %s
        ORDER BY s.source_name ASC
    """, (user["role_id"],))

    buttons = []

    for row in cursor.fetchall():
        source_name = row.get("source_name") or "Unknown"
        source_id = row["source_id"]

        # Daily fetched count today (using indexed date range)
        cursor.execute("""
            SELECT COUNT(*) AS fetched_today
            FROM leads
            WHERE current_owner_user_id = %s
              AND (lead_source = %s OR lead_source = %s)
              AND assigned_at >= CURDATE() AND assigned_at < CURDATE() + INTERVAL 1 DAY
        """, (user_id, source_name, str(source_id)))
        fetched_res = cursor.fetchone()
        daily_fetched_count = fetched_res["fetched_today"] if fetched_res else 0

        # Pending count for user
        cursor.execute("""
            SELECT COUNT(*) AS pending_count
            FROM leads
            WHERE current_owner_user_id = %s
              AND (lead_source = %s OR lead_source = %s)
              AND (is_disposed = 0 OR is_disposed IS NULL)
              AND (lead_status IS NULL OR lead_status = '' OR lead_status = 'No Status' OR lead_status = 'Pending')
        """, (user_id, source_name, str(source_id)))
        pending_res = cursor.fetchone()
        pending_count = pending_res["pending_count"] if pending_res else 0

        # Unassigned count in system for this lead source
        cursor.execute("""
            SELECT COUNT(*) AS unassigned_count
            FROM leads
            WHERE (current_owner_user_id IS NULL OR current_owner_user_id = 0)
              AND NOT EXISTS (SELECT 1 FROM clients c WHERE c.lead_id = leads.id)
              AND (is_disposed = 0 OR is_disposed IS NULL)
              AND (lead_source = %s OR lead_source = %s)
        """, (source_name, str(source_id)))
        unassigned_res = cursor.fetchone()
        unassigned_count = unassigned_res["unassigned_count"] if unassigned_res else 0

        daily_limit = row["daily_lead_limit"]
        pending_limit = row["pending_lead_limit"]
        fetch_limit = row["fetch_lead_limit"]

        remaining_today = max(0, daily_limit - daily_fetched_count)
        is_limit_reached = (remaining_today <= 0) or (pending_count >= pending_limit)

        buttons.append({
            "source_id": source_id,
            "source_name": source_name,
            "daily_fetched_count": daily_fetched_count,
            "remaining_today": remaining_today,
            "pending_lead_count": pending_count,
            "pending_lead_limit": pending_limit,
            "daily_lead_limit": daily_limit,
            "fetch_lead_limit": fetch_limit,
            "unassigned_count": unassigned_count,
            "is_limit_reached": is_limit_reached,
        })

    return buttons


def resolve_selected_owner(logged_user_uuid=None):
    from flask import request
    owner_req = request.args.get("owner")
    if owner_req is not None and owner_req != "":
        return owner_req
    return "all"

