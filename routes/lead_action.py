import json
from urllib.parse import urlencode
from urllib.request import urlopen
from datetime import date, datetime
from decimal import Decimal

from routes.settings_helpers import (
    clean_email,
    clean_name,
    decrypt_mobile,
    make_unique_code,
)


CALLBACK_STATUS_KEYWORD = "callback"


def serialize_value(value):
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y %I:%M %p")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        return float(value)
    return value


def serialize_rows(rows):
    return [
        {key: serialize_value(value) for key, value in dict(row).items()}
        for row in rows
    ]


def mask_mobile(encrypted_or_plain_mobile):
    plain = decrypt_mobile(encrypted_or_plain_mobile)
    digits = "".join(ch for ch in plain if ch.isdigit())
    if len(digits) <= 4:
        return "Hidden"
    return f"XXXXXX{digits[-4:]}"


def get_current_user(cursor, user_uuid):
    if not user_uuid:
        return None
    try:
        cursor.execute("""
            SELECT
                u.user_uuid,
                u.full_name,
                u.number_show_hide,
                u.click_to_call,
                e.extension_number,
                ca.api_link AS calling_api_url,
                COALESCE(ca.source_variable, 'from') AS calling_source_param,
                COALESCE(ca.destination_variable, 'to') AS calling_destination_param,
                COALESCE(r.role_name, '') AS role_name,
                COALESCE(r.permissions, '') AS permissions,
                COALESCE(r.lead_limit_per_user, 10) AS lead_limit_per_user
            FROM users u
            LEFT JOIN roles r ON r.id = u.role_id
            LEFT JOIN extensions e ON e.id = u.extension_id
            LEFT JOIN calling_apis ca ON ca.status = 1
            WHERE u.user_uuid = %s AND u.status = 1
            LIMIT 1
        """, (user_uuid,))
        return cursor.fetchone()
    except Exception:
        cursor.execute("""
            SELECT
                u.user_uuid,
                u.full_name,
                u.number_show_hide,
                u.click_to_call,
                COALESCE(r.role_name, '') AS role_name,
                COALESCE(r.permissions, '') AS permissions,
                COALESCE(r.lead_limit_per_user, 10) AS lead_limit_per_user
            FROM users u
            LEFT JOIN roles r ON r.id = u.role_id
            WHERE u.user_uuid = %s AND u.status = 1
            LIMIT 1
        """, (user_uuid,))
        return cursor.fetchone()


def parse_permissions(raw_permissions):
    if not raw_permissions:
        return {}
    if isinstance(raw_permissions, dict):
        return raw_permissions
    try:
        parsed = json.loads(raw_permissions)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def is_admin(user):
    return bool(user and str(user.get("role_name") or "").strip().lower() == "admin")


def has_permission(user, module_name, action="view"):
    if is_admin(user):
        return True
    permissions = parse_permissions(user.get("permissions") if user else "")
    allowed_actions = permissions.get(module_name) or []
    return action in allowed_actions


def get_action_permissions(user):
    return {
        "can_view_mobile": bool(user and int(user.get("number_show_hide") or 0) == 0),
        "can_click_to_call": bool(user and int(user.get("click_to_call") or 0) == 1),
        "can_edit_more": has_permission(user, "Can Edit Lead Info") or has_permission(user, "Leads", "edit"),
        "can_suspend": has_permission(user, "Can Suspend Lead") or has_permission(user, "Can Dispose Lead") or has_permission(user, "Leads", "delete"),
        "can_create_so": has_permission(user, "Can Create SO") or has_permission(user, "Sales Orders", "create"),
        "can_transfer": has_permission(user, "Can Transfer Lead") or has_permission(user, "Leads", "edit"),
        "can_add_contact": has_permission(user, "Contacts", "create") or has_permission(user, "Leads", "edit"),
        "can_add_followup": has_permission(user, "Follow-ups", "create") or has_permission(user, "Leads", "edit"),
        "can_start_trial": has_permission(user, "Free Trials", "create") or has_permission(user, "Leads", "edit"),
        "can_view_history": has_permission(user, "View Lead History") or has_permission(user, "Leads", "view"),
    }


def get_active_limit(user):
    try:
        return max(int(user.get("lead_limit_per_user") or 10), 0)
    except (TypeError, ValueError):
        return 10


def lead_working_status(lead):
    if int(lead.get("is_called") or 0) == 1 and not lead.get("lead_status"):
        return "Called - Status Pending"
    return "Fresh"


def fetch_calling_queue(cursor, user_uuid):
    user = get_current_user(cursor, user_uuid)
    if not user:
        return [], 0, get_action_permissions(None)

    limit = get_active_limit(user)
    permissions = get_action_permissions(user)
    if limit <= 0:
        return [], 0, permissions

    cursor.execute("""
        SELECT
            l.lead_uuid,
            COALESCE(l.name, '') AS name,
            l.mobile_number,
            COALESCE(l.email, '') AS email,
            COALESCE(l.lead_source, '') AS lead_source,
            a.lead_status,
            COALESCE(a.is_called, 0) AS is_called,
            (CASE WHEN EXISTS (SELECT 1 FROM contacts c WHERE c.lead_id = l.id) THEN 1 ELSE 0 END) AS has_contact,
            (CASE WHEN EXISTS (SELECT 1 FROM followups f WHERE f.lead_id = l.id) THEN 1 ELSE 0 END) AS has_followup,
            (CASE WHEN EXISTS (SELECT 1 FROM free_trials ft WHERE ft.lead_id = l.id) THEN 1 ELSE 0 END) AS has_free_trial,
            (CASE WHEN EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id AND so.order_status = 'approved') THEN 1 ELSE 0 END) AS has_so,
            (CASE WHEN EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id AND so.order_status = 'approved') THEN 1 ELSE 0 END) AS is_paid_client,
            COALESCE(l.is_disposed, 0) AS is_disposed,
            COALESCE(s.status_tone, 'slate') AS status_tone,
            COALESCE(b.batch_name, '') AS batch_name,
            COALESCE(owner.full_name, '') AS current_owner,
            l.created_at,
            l.updated_at,
            a.assignment_uuid,
            a.call_started_at
        FROM lead_assignments a
        INNER JOIN leads l ON l.id = a.lead_id
        LEFT JOIN lead_statuses s ON s.status_name = a.lead_status
        LEFT JOIN lead_batches b ON (b.id = l.lead_batch_id OR b.batch_uuid = l.lead_batch_uuid)
        LEFT JOIN users owner ON (owner.id = l.current_owner_user_id OR owner.user_uuid = l.current_owner_user_uuid)
        WHERE a.assigned_to_user_uuid = %s
          AND a.is_current = 1
          AND (l.current_owner_user_id = (SELECT id FROM users WHERE user_uuid = %s LIMIT 1) OR l.current_owner_user_uuid = a.assigned_to_user_uuid)
          AND COALESCE(l.is_disposed, 0) = 0
          AND NOT EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id AND so.order_status = 'approved')
          AND (
                COALESCE(a.is_called, 0) = 0
                OR (a.is_called = 1 AND a.lead_status IS NULL)
          )
        ORDER BY
            CASE WHEN a.is_called = 1 AND a.lead_status IS NULL THEN 0 ELSE 1 END,
            COALESCE(a.call_started_at, l.created_at) ASC,
            l.id ASC
        LIMIT %s
    """, (user_uuid, user_uuid, limit))
    rows = cursor.fetchall()
    for row in rows:
        row["mobile_display"] = decrypt_mobile(row["mobile_number"]) if permissions["can_view_mobile"] else mask_mobile(row["mobile_number"])
        row.pop("mobile_number", None)
        row["working_status"] = lead_working_status(row)
        row["is_status_pending"] = row["working_status"] == "Called - Status Pending"
        row["can_call"] = permissions["can_click_to_call"]
    return serialize_rows(rows), limit, permissions


def get_status_options(cursor):
    cursor.execute("""
        SELECT status_name, status_tone
        FROM lead_statuses
        WHERE status = 1
        ORDER BY status_name ASC
    """)
    return serialize_rows(cursor.fetchall())


def add_timeline(cursor, lead_id, assignment_id, action_type, action_by=None, old_status=None,
                 new_status=None, from_user=None, to_user=None, remark=None, metadata=None):
    cursor.execute("""
        INSERT INTO lead_timeline (
            history_uuid, lead_id, assignment_id, action_type, old_status, new_status,
            action_by, from_user_uuid, to_user_uuid, remark, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        make_unique_code(cursor, "lead_timeline", "history_uuid", "LH"),
        lead_id,
        assignment_id,
        action_type,
        old_status,
        new_status,
        action_by,
        from_user,
        to_user,
        remark,
        json.dumps(metadata or {}),
    ))


def fetch_lead_for_user(cursor, lead_uuid, user_uuid):
    cursor.execute("""
        SELECT *
        FROM leads
        WHERE lead_uuid = %s
          AND current_owner_user_uuid = %s
        LIMIT 1
    """, (lead_uuid, user_uuid))
    return cursor.fetchone()


def fetch_lead_any(cursor, lead_uuid):
    cursor.execute("SELECT * FROM leads WHERE lead_uuid = %s LIMIT 1", (lead_uuid,))
    return cursor.fetchone()


def ensure_current_assignment(cursor, lead, user_uuid, assigned_by=None):
    cursor.execute("""
        SELECT *
        FROM lead_assignments
        WHERE lead_id = %s
          AND assigned_to_user_uuid = %s
          AND is_current = 1
        ORDER BY id DESC
        LIMIT 1
    """, (lead["id"], user_uuid))
    assignment = cursor.fetchone()
    if assignment:
        return assignment

    assignment_uuid = make_unique_code(cursor, "lead_assignments", "assignment_uuid", "LASG")
    cursor.execute("""
        INSERT INTO lead_assignments (
            assignment_uuid, lead_id, lead_batch_uuid, assigned_to_user_uuid,
            assigned_by_user_uuid, call_state, is_called, lead_status, is_current
        )
        VALUES (%s, %s, %s, %s, %s, NULL, 0, NULL, 1)
    """, (
        assignment_uuid,
        lead["id"],
        lead.get("lead_batch_uuid"),
        user_uuid,
        assigned_by,
    ))
    cursor.execute("SELECT * FROM lead_assignments WHERE id = %s", (cursor.lastrowid,))
    return cursor.fetchone()


def lead_badges(lead):
    return {
        "has_contact": int(lead.get("has_contact") or 0),
        "has_followup": int(lead.get("has_followup") or 0),
        "has_free_trial": int(lead.get("has_free_trial") or 0),
        "has_so": int(lead.get("has_so") or 0),
        "is_paid_client": int(lead.get("is_paid_client") or 0),
        "is_suspended": int(lead.get("is_suspended") or 0),
    }


def get_lead_action_payload(cursor, lead_uuid, user_uuid):
    user = get_current_user(cursor, user_uuid)
    permissions = get_action_permissions(user)
    lead = fetch_lead_for_user(cursor, lead_uuid, user_uuid)
    if not lead:
        raise ValueError("Lead not found in your assignment.")
    assignment = ensure_current_assignment(cursor, lead, user_uuid)

    return {
        "lead": {
            "lead_uuid": lead["lead_uuid"],
            "assignment_uuid": assignment["assignment_uuid"],
            "name": lead.get("name") or "",
            "email": lead.get("email") or "",
            "mobile_display": decrypt_mobile(lead["mobile_number"]) if permissions["can_view_mobile"] else mask_mobile(lead["mobile_number"]),
            "lead_source": lead.get("lead_source") or "",
            "lead_status": assignment.get("lead_status") or "",
            "is_called": int(assignment.get("is_called") or 0),
            "working_status": lead_working_status(assignment),
            "lead_state": lead.get("lead_state") or "Lead",
            "badges": lead_badges(lead),
        },
        "permissions": permissions,
        "statuses": get_status_options(cursor),
    }


def click_to_call_api(plain_mobile, user):
    api_url = (user.get("calling_api_url") if user else "") or ""
    extension_number = (user.get("extension_number") if user else "") or ""
    if not api_url or not extension_number:
        return True, "Calling API not mapped for this extension. Call marked in CRM only."

    query = urlencode({
        user.get("calling_source_param") or "from": extension_number,
        user.get("calling_destination_param") or "to": plain_mobile,
    })
    separator = "&" if "?" in api_url else "?"
    full_url = f"{api_url}{separator}{query}"
    try:
        with urlopen(full_url, timeout=8) as response:
            body = response.read().decode("utf-8", errors="replace")[:500]
        return True, body or "Calling API success."
    except Exception as error:
        return False, f"Calling API failed: {error}"


def start_call(conn, lead_uuid, user_uuid):
    with conn.cursor() as cursor:
        user = get_current_user(cursor, user_uuid)
        permissions = get_action_permissions(user)
        if not permissions["can_click_to_call"]:
            raise PermissionError("Click to Call is not enabled for your user.")

        lead = fetch_lead_for_user(cursor, lead_uuid, user_uuid)
        if not lead:
            raise ValueError("Lead not found in your assignment.")
        if int(lead.get("is_suspended") or 0) == 1:
            raise ValueError("Suspended lead cannot be called.")
        if int(lead.get("has_so") or 0) == 1 or int(lead.get("is_paid_client") or 0) == 1:
            raise ValueError("SO/Paid Client lead cannot be called from lead queue.")
        assignment = ensure_current_assignment(cursor, lead, user_uuid)
        if assignment.get("lead_status") and int(assignment.get("is_called") or 0) == 1:
            raise ValueError("This lead already has a submitted status.")

        plain_mobile = decrypt_mobile(lead["mobile_number"])
        api_success, api_message = click_to_call_api(plain_mobile, user)
        if not api_success:
            raise ValueError(api_message or "Calling API failed.")

        old_call_status = "Called" if int(assignment.get("is_called") or 0) == 1 else None
        cursor.execute("""
            UPDATE lead_assignments
            SET is_called = 1,
                call_state = 'Called',
                call_started_at = COALESCE(call_started_at, NOW())
            WHERE id = %s
        """, (assignment["id"],))
        cursor.execute("UPDATE leads SET updated_at = NOW() WHERE id = %s", (lead["id"],))
        cursor.execute("""
            INSERT INTO lead_call_attempts (
                call_uuid, lead_id, assignment_id, initiated_by, api_status, api_response
            )
            VALUES (%s, %s, %s, %s, 'Success', %s)
        """, (
            make_unique_code(cursor, "lead_call_attempts", "call_uuid", "LCALL"),
            lead["id"],
            assignment["id"],
            user_uuid,
            api_message,
        ))
        add_timeline(
            cursor,
            lead["id"],
            assignment["id"],
            "Call Started",
            action_by=user_uuid,
            old_status=old_call_status,
            new_status="Called",
            metadata={"state_type": "assignment_call_status"},
        )
        payload = get_lead_action_payload(cursor, lead_uuid, user_uuid)

    conn.commit()
    return payload


def is_callback_status(status_name):
    return CALLBACK_STATUS_KEYWORD in str(status_name or "").strip().lower()


def submit_status(conn, lead_uuid, user_uuid, status_name, remark="", callback_date=None, callback_time=None):
    status_name = (status_name or "").strip()
    remark = (remark or "").strip()
    if not status_name:
        raise ValueError("Lead status is required.")
    if is_callback_status(status_name) and (not callback_date or not callback_time):
        raise ValueError("Callback date and time are required.")

    with conn.cursor() as cursor:
        cursor.execute("SELECT status_name FROM lead_statuses WHERE status = 1 AND status_name = %s", (status_name,))
        if not cursor.fetchone():
            raise ValueError("Invalid lead status.")

        lead = fetch_lead_for_user(cursor, lead_uuid, user_uuid)
        if not lead:
            raise ValueError("Lead not found in your assignment.")
        assignment = ensure_current_assignment(cursor, lead, user_uuid)
        old_status = assignment.get("lead_status")

        cursor.execute("""
            UPDATE lead_assignments
            SET is_called = 1,
                lead_status = %s,
                call_state = 'Completed',
                action_completed_at = NOW(),
                acted_by_user_uuid = %s,
                last_remark = %s
            WHERE id = %s
        """, (status_name, user_uuid, remark or None, assignment["id"]))
        cursor.execute("""
            UPDATE leads
            SET is_suspended = 0,
                updated_at = NOW()
            WHERE id = %s
        """, (lead["id"],))
        add_timeline(
            cursor,
            lead["id"],
            assignment["id"],
            "Status Submitted",
            action_by=user_uuid,
            old_status=old_status,
            new_status=status_name,
            remark=remark or None,
        )
        if remark:
            add_timeline(cursor, lead["id"], assignment["id"], "Remark Added", action_by=user_uuid, remark=remark)
        if is_callback_status(status_name):
            add_timeline(
                cursor,
                lead["id"],
                assignment["id"],
                "Callback Scheduled",
                action_by=user_uuid,
                remark=remark or None,
                metadata={"callback_date": callback_date, "callback_time": callback_time},
            )

    conn.commit()


def add_contact(conn, lead_uuid, user_uuid, name="", email="", note=""):
    with conn.cursor() as cursor:
        user = get_current_user(cursor, user_uuid)
        if not get_action_permissions(user)["can_add_contact"]:
            raise PermissionError("You do not have permission to add contacts.")
        lead = fetch_lead_for_user(cursor, lead_uuid, user_uuid)
        if not lead:
            raise ValueError("Lead not found in your assignment.")
        assignment = ensure_current_assignment(cursor, lead, user_uuid)
        cursor.execute("""
            INSERT INTO lead_contacts (
                contact_uuid, lead_id, name, email, phone, note, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            make_unique_code(cursor, "lead_contacts", "contact_uuid", "LCNT"),
            lead["id"],
            clean_name(name or lead.get("name") or ""),
            clean_email(email or lead.get("email") or ""),
            lead.get("mobile_number"),
            (note or "").strip() or None,
            user_uuid,
        ))
        cursor.execute("UPDATE leads SET updated_at = NOW() WHERE id = %s", (lead["id"],))
        add_timeline(cursor, lead["id"], assignment["id"], "Contact Added", action_by=user_uuid, remark=(note or "").strip() or None)
    conn.commit()


def add_followup(conn, lead_uuid, user_uuid, followup_date, followup_time, note="", priority="", followup_type=""):
    if not followup_date or not followup_time:
        raise ValueError("Follow-up date and time are required.")
    with conn.cursor() as cursor:
        user = get_current_user(cursor, user_uuid)
        if not get_action_permissions(user)["can_add_followup"]:
            raise PermissionError("You do not have permission to add follow-ups.")
        lead = fetch_lead_for_user(cursor, lead_uuid, user_uuid)
        if not lead:
            raise ValueError("Lead not found in your assignment.")
        assignment = ensure_current_assignment(cursor, lead, user_uuid)
        cursor.execute("""
            INSERT INTO followups (
                followup_uuid, lead_id, followup_date, followup_time,
                priority, followup_type, note, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            make_unique_code(cursor, "followups", "followup_uuid", "LFU"),
            lead["id"],
            followup_date,
            followup_time,
            (priority or "").strip() or None,
            (followup_type or "").strip() or None,
            (note or "").strip() or None,
            user_uuid,
        ))
        cursor.execute("UPDATE leads SET updated_at = NOW() WHERE id = %s", (lead["id"],))
        add_timeline(cursor, lead["id"], assignment["id"], "Follow-up Added", action_by=user_uuid, remark=(note or "").strip() or None)
    conn.commit()


def start_free_trial(conn, lead_uuid, user_uuid, service, duration="", start_date=None, end_date=None, note=""):
    service = (service or "").strip()
    if not service:
        raise ValueError("Service is required.")
    with conn.cursor() as cursor:
        user = get_current_user(cursor, user_uuid)
        if not get_action_permissions(user)["can_start_trial"]:
            raise PermissionError("You do not have permission to start free trials.")
        lead = fetch_lead_for_user(cursor, lead_uuid, user_uuid)
        if not lead:
            raise ValueError("Lead not found in your assignment.")
        assignment = ensure_current_assignment(cursor, lead, user_uuid)
        cursor.execute("""
            INSERT INTO free_trials (
                trial_uuid, lead_id, service, duration, start_date, end_date, note, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            make_unique_code(cursor, "free_trials", "trial_uuid", "LFT"),
            lead["id"],
            service,
            (duration or "").strip() or None,
            start_date or None,
            end_date or None,
            (note or "").strip() or None,
            user_uuid,
        ))
        cursor.execute("UPDATE leads SET updated_at = NOW() WHERE id = %s", (lead["id"],))
        add_timeline(cursor, lead["id"], assignment["id"], "Free Trial Started", action_by=user_uuid, remark=(note or "").strip() or None)
    conn.commit()


def create_sales_order(conn, lead_uuid, user_uuid, service="", plan="", price=None, amount=None, customer_name="", customer_email=""):
    with conn.cursor() as cursor:
        user = get_current_user(cursor, user_uuid)
        if not get_action_permissions(user)["can_create_so"]:
            raise PermissionError("You do not have permission to create SO from lead.")
        lead = fetch_lead_for_user(cursor, lead_uuid, user_uuid) or fetch_lead_any(cursor, lead_uuid)
        if not lead:
            raise ValueError("Lead not found.")
        owner_uuid = lead.get("current_owner_user_uuid") or user_uuid
        assignment = ensure_current_assignment(cursor, lead, owner_uuid, assigned_by=user_uuid)
        so_uuid = make_unique_code(cursor, "sales_orders", "so_uuid", "SO")
        cursor.execute("""
            INSERT INTO sales_orders (
                so_uuid, lead_id, service, plan, price, amount,
                customer_name, customer_email, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            so_uuid,
            lead["id"],
            (service or "").strip() or None,
            (plan or "").strip() or None,
            price or None,
            amount or None,
            clean_name(customer_name or lead.get("name") or ""),
            clean_email(customer_email or lead.get("email") or ""),
            user_uuid,
        ))
        cursor.execute("""
            UPDATE leads
            SET updated_at = NOW()
            WHERE id = %s
        """, (lead["id"],))
        cursor.execute("""
            UPDATE lead_assignments
            SET call_state = 'Completed',
                action_completed_at = COALESCE(action_completed_at, NOW()),
                acted_by_user_uuid = %s
            WHERE id = %s
        """, (user_uuid, assignment["id"]))
        add_timeline(
            cursor,
            lead["id"],
            assignment["id"],
            "SO Created",
            action_by=user_uuid,
            new_status="SO",
            metadata={"so_uuid": so_uuid},
        )
    conn.commit()
    return so_uuid


def suspend_lead(conn, lead_uuid, user_uuid, reason, remark=""):
    reason = (reason or "").strip()
    remark = (remark or "").strip()
    if not reason:
        raise ValueError("Suspend reason is required.")
    if not remark:
        raise ValueError("Suspend comment is required.")

    with conn.cursor() as cursor:
        user = get_current_user(cursor, user_uuid)
        if not get_action_permissions(user)["can_suspend"]:
            raise PermissionError("You do not have permission to suspend leads.")
        lead = fetch_lead_for_user(cursor, lead_uuid, user_uuid)
        if not lead:
            raise ValueError("Lead not found in your assignment.")
        assignment = ensure_current_assignment(cursor, lead, user_uuid)
        old_status = assignment.get("lead_status")
        cursor.execute("""
            UPDATE lead_assignments
            SET is_called = 1,
                lead_status = %s,
                call_state = 'Completed',
                action_completed_at = NOW(),
                acted_by_user_uuid = %s,
                last_remark = %s
            WHERE id = %s
        """, (reason, user_uuid, remark, assignment["id"]))
        cursor.execute("""
            UPDATE leads
            SET is_disposed = 1,
                comment = %s,
                disposed_by = (SELECT id FROM users WHERE user_uuid = %s LIMIT 1),
                disposed_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """, (reason, user_uuid, lead["id"]))
        add_timeline(
            cursor,
            lead["id"],
            assignment["id"],
            "Lead Suspended",
            action_by=user_uuid,
            old_status=old_status,
            new_status=reason,
            remark=remark,
        )
    conn.commit()


def dispose_lead(conn, lead_uuid, user_uuid, reason, remark=""):
    return suspend_lead(conn, lead_uuid, user_uuid, reason, remark)


def resume_lead(conn, lead_uuid, user_uuid, remark=""):
    with conn.cursor() as cursor:
        user = get_current_user(cursor, user_uuid)
        if not get_action_permissions(user)["can_suspend"]:
            raise PermissionError("You do not have permission to resume leads.")
        lead = fetch_lead_for_user(cursor, lead_uuid, user_uuid)
        if not lead:
            raise ValueError("Lead not found in your assignment.")
        assignment = ensure_current_assignment(cursor, lead, user_uuid)
        cursor.execute("""
            UPDATE leads
            SET is_disposed = 0,
                updated_at = NOW()
            WHERE id = %s
        """, (lead["id"],))
        add_timeline(
            cursor,
            lead["id"],
            assignment["id"],
            "Lead Resumed",
            action_by=user_uuid,
            remark=(remark or "").strip() or None,
        )
    conn.commit()


def transfer_lead(conn, lead_uuid, user_uuid, to_user_uuid, remark=""):
    to_user_uuid = (to_user_uuid or "").strip()
    remark = (remark or "").strip()
    if not to_user_uuid:
        raise ValueError("New owner is required.")
    if to_user_uuid == user_uuid:
        raise ValueError("New owner must be different from current owner.")

    with conn.cursor() as cursor:
        user = get_current_user(cursor, user_uuid)
        if not get_action_permissions(user)["can_transfer"]:
            raise PermissionError("You do not have permission to transfer leads.")
        cursor.execute("SELECT user_uuid FROM users WHERE user_uuid = %s AND status = 1 LIMIT 1", (to_user_uuid,))
        if not cursor.fetchone():
            raise ValueError("New owner not found.")
        lead = fetch_lead_for_user(cursor, lead_uuid, user_uuid)
        if not lead:
            raise ValueError("Lead not found in your assignment.")
        assignment = ensure_current_assignment(cursor, lead, user_uuid)

        cursor.execute("""
            UPDATE lead_assignments
            SET is_current = 0,
                call_state = 'Completed',
                action_completed_at = NOW(),
                acted_by_user_uuid = %s,
                last_remark = %s
            WHERE id = %s
        """, (user_uuid, remark or None, assignment["id"]))
        cursor.execute("""
            INSERT INTO lead_assignments (
                assignment_uuid, lead_id, lead_batch_uuid, assigned_to_user_uuid,
                assigned_by_user_uuid, call_state, is_called, lead_status, is_current
            )
            VALUES (%s, %s, %s, %s, %s, NULL, 0, NULL, 1)
        """, (
            make_unique_code(cursor, "lead_assignments", "assignment_uuid", "LASG"),
            lead["id"],
            lead.get("lead_batch_uuid"),
            to_user_uuid,
            user_uuid,
        ))
        new_assignment_id = cursor.lastrowid
        cursor.execute("""
            UPDATE leads
            SET current_owner_user_uuid = %s,
                current_owner_user_id = (SELECT id FROM users WHERE user_uuid = %s LIMIT 1),
                is_disposed = 0,
                updated_at = NOW()
            WHERE id = %s
        """, (to_user_uuid, to_user_uuid, lead["id"]))
        add_timeline(
            cursor,
            lead["id"],
            new_assignment_id,
            "Lead Transferred",
            action_by=user_uuid,
            old_status=assignment.get("lead_status"),
            new_status=None,
            from_user=user_uuid,
            to_user=to_user_uuid,
            remark=remark or None,
            metadata={"new_assignment": {"is_called": 0, "lead_status": None}},
        )
    conn.commit()


def mark_so_created(conn, lead_uuid, user_uuid, so_reference=None):
    return create_sales_order(conn, lead_uuid, user_uuid, service=so_reference or "")


def fetch_transfer_users(cursor, current_user_uuid):
    cursor.execute("""
        SELECT user_uuid, full_name
        FROM users
        WHERE status = 1 AND user_uuid <> %s
        ORDER BY full_name ASC
    """, (current_user_uuid,))
    return serialize_rows(cursor.fetchall())


def fetch_timeline(cursor, lead_id):
    cursor.execute("""
        SELECT
            t.action_type,
            t.old_status,
            t.new_status,
            t.remark,
            t.created_at,
            COALESCE(actor.full_name, '') AS action_by_name,
            COALESCE(from_user.full_name, '') AS from_user_name,
            COALESCE(to_user.full_name, '') AS to_user_name
        FROM lead_timeline t
        LEFT JOIN users actor ON actor.user_uuid = t.action_by
        LEFT JOIN users from_user ON from_user.user_uuid = t.from_user_uuid
        LEFT JOIN users to_user ON to_user.user_uuid = t.to_user_uuid
        WHERE t.lead_id = %s
        ORDER BY t.id DESC
        LIMIT 50
    """, (lead_id,))
    return serialize_rows(cursor.fetchall())
