
import datetime
import re
import uuid
from config import get_db_connection
from routes.click_to_call import (
    trigger_click_to_call,
)
from routes.settings_helpers import (
    decrypt_mobile,
    encrypt_mobile,
    fetch_logged_user_settings,
)


def acquire_user_call_lock(
    user_uuid,
):
    lock_connection = get_db_connection()
    lock_name = f"click_to_call:{user_uuid}"

    try:
        with lock_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT GET_LOCK(%s, 0) AS lock_acquired
                """,
                (lock_name,),
            )

            result = cursor.fetchone() or {}

        lock_acquired = int(
            result.get("lock_acquired")
            or 0
        )

        if lock_acquired != 1:
            lock_connection.close()

            return None, None

        return (
            lock_connection,
            lock_name,
        )

    except Exception:
        lock_connection.close()
        raise


def release_user_call_lock(
    lock_connection,
    lock_name,
):
    if not lock_connection or not lock_name:
        return

    try:
        with lock_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT RELEASE_LOCK(%s)
                """,
                (lock_name,),
            )
    finally:
        lock_connection.close()


def get_lead_mobile_number(
    lead_uuid,
):
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT mobile_number
                FROM leads
                WHERE lead_uuid = %s
                LIMIT 1
                """,
                (lead_uuid,),
            )

            lead = cursor.fetchone()
    finally:
        connection.close()

    if not lead:
        return None

    return decrypt_mobile(
        lead.get("mobile_number")
    )


def process_lead_click_to_call(
    logged_user_uuid,
    lead_uuid,
    ip_address="",
):
    mobile_number = get_lead_mobile_number(
        lead_uuid
    )

    if mobile_number is None:
        return {
            "success": False,
            "message": "Lead not found.",
            "status_code": 404,
        }

    lock_connection = None
    lock_name = None

    try:
        (
            lock_connection,
            lock_name,
        ) = acquire_user_call_lock(
            logged_user_uuid
        )

        if not lock_connection:
            return {
                "success": False,
                "message": (
                    "Another call request is "
                    "already in progress."
                ),
                "status_code": 409,
            }

        result = trigger_click_to_call(
            logged_user_uuid,
            lead_uuid,
            mobile_number,
        )

        if isinstance(result, dict) and not result.get("success", True):
            raw_msg = (result.get("message") or "").strip()
            if "USER_NOT_REGISTERED" in raw_msg:
                user_friendly_msg = "CloudConnect Extension (701) registered nahi hai. Kripya CloudConnect UC app open karke login karein."
            else:
                user_friendly_msg = f"Calling error: {raw_msg}"
            return {
                "success": False,
                "message": user_friendly_msg,
                "status_code": 400,
            }

        # Log activity into lead_activities and user_activities
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, lead_uuid, id AS client_code, name, lead_status
                    FROM leads
                    WHERE lead_uuid = %s LIMIT 1
                """, (lead_uuid,))
                lead = cursor.fetchone()
                if lead:
                    lead_id = lead["id"]
                    client_code = lead.get("client_code") or str(lead_id)
                    lead_name = lead.get("name") or "Lead"
                    curr_status = lead.get("lead_status") or "No Status"

                    if isinstance(result, dict):
                        result["lead_id"] = client_code
                        result["lead_name"] = lead_name
                        result["message"] = f"Dialing Lead {client_code} ({lead_name})..."

                    activity_uuid = f"ACT{uuid.uuid4().hex[:12].upper()}"
                    cursor.execute("""
                        INSERT INTO lead_activities (
                            activity_uuid, lead_id, user_id, action_type, status_name, comment
                        ) VALUES (%s, %s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), 'Click to Call', %s, %s)
                    """, (activity_uuid, lead_id, logged_user_uuid, curr_status, f"Initiated click-to-call to lead {client_code}"))

                    user_act_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
                    act_desc = f"Initiated click-to-call to lead {client_code} ({lead_name})"
                    cursor.execute("""
                        INSERT INTO user_activities (
                            user_activity_uuid, user_id, lead_id, action_type, description, ip_address
                        ) VALUES (%s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), %s, 'Click to Call', %s, %s)
                    """, (user_act_uuid, logged_user_uuid, lead_id, act_desc, ip_address or None))

                conn.commit()
            conn.close()
        except Exception:
            pass

        if isinstance(result, dict):
            result.pop("destination_number", None)
            result.pop("extension_number", None)
            result.pop("final_url", None)

        return {
            "success": True,
            "result": result,
            "status_code": 200,
        }

    except ValueError as error:
        return {
            "success": False,
            "message": str(error),
            "status_code": 400,
        }

    except Exception:
        return {
            "success": False,
            "message": "Call request failed.",
            "status_code": 500,
        }

    finally:
        release_user_call_lock(
            lock_connection,
            lock_name,
        )


def process_fetch_leads_from_source(logged_user_uuid, source_id, ip_address=""):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 1. Get user role_id
            cursor.execute("""
                SELECT role_id
                FROM users
                WHERE user_uuid = %s AND status = 1
                LIMIT 1
            """, (logged_user_uuid,))
            user = cursor.fetchone()
            if not user or not user.get("role_id"):
                return {
                    "success": False,
                    "message": "User role not found or user is inactive.",
                    "status_code": 403,
                }
            role_id = user["role_id"]

            # 2. Get lead source limit config
            cursor.execute("""
                SELECT
                    l.source_id,
                    l.pending_lead_limit,
                    l.daily_lead_limit,
                    l.fetch_lead_limit,
                    s.source_name
                FROM lead_source_limits l
                INNER JOIN lead_sources s ON s.id = l.source_id
                WHERE l.role_id = %s AND l.source_id = %s
                LIMIT 1
            """, (role_id, source_id))
            limit_cfg = cursor.fetchone()

            if not limit_cfg:
                return {
                    "success": False,
                    "message": "No lead source limit configuration found for your role and source.",
                    "status_code": 403,
                }

            source_name = limit_cfg["source_name"]
            pending_lead_limit = limit_cfg["pending_lead_limit"]
            daily_lead_limit = limit_cfg["daily_lead_limit"]
            fetch_lead_limit = limit_cfg["fetch_lead_limit"]

            # 3. Check current pending lead count for this user and source
            # Note: Lead is pending IF AND ONLY IF no feedback is submitted (is_disposed is 0/NULL AND lead_status is NULL/empty).
            cursor.execute("""
                SELECT COUNT(*) AS pending_count
                FROM leads
                WHERE current_owner_user_id = (SELECT id FROM users WHERE user_uuid = %s LIMIT 1)
                  AND (lead_source = %s OR lead_source = %s)
                  AND (is_disposed = 0 OR is_disposed IS NULL)
                  AND (lead_status IS NULL OR lead_status = '' OR lead_status = 'No Status' OR lead_status = 'Pending')
            """, (logged_user_uuid, source_name, str(source_id)))
            pending_res = cursor.fetchone()
            pending_count = pending_res["pending_count"] if pending_res else 0

            if pending_count >= pending_lead_limit:
                return {
                    "success": False,
                    "message": f"You currently have {pending_count} pending lead(s) for {source_name} (Pending Limit: {pending_lead_limit}). Please update status on existing pending leads before fetching new ones.",
                    "status_code": 400,
                }

            # 4. Check daily fetched lead count for this user and source today
            cursor.execute("""
                SELECT COUNT(*) AS fetched_today
                FROM leads
                WHERE current_owner_user_id = (SELECT id FROM users WHERE user_uuid = %s LIMIT 1)
                  AND (lead_source = %s OR lead_source = %s)
                  AND DATE(assigned_at) = CURDATE()
            """, (logged_user_uuid, source_name, str(source_id)))
            fetched_res = cursor.fetchone()
            daily_fetched_count = fetched_res["fetched_today"] if fetched_res else 0

            if daily_fetched_count >= daily_lead_limit:
                return {
                    "success": False,
                    "message": f"Daily fetch limit ({daily_lead_limit}) has been reached for {source_name} today.",
                    "status_code": 400,
                }

            # 5. Calculate how many leads can be fetched right now
            available_pending_slot = pending_lead_limit - pending_count
            available_daily_slot = daily_lead_limit - daily_fetched_count
            limit_to_fetch = min(fetch_lead_limit, available_pending_slot, available_daily_slot)

            if limit_to_fetch <= 0:
                return {
                    "success": False,
                    "message": "No lead fetch quota available at this time.",
                    "status_code": 400,
                }

            # 6. Find unassigned leads in DB with row-level locking (FOR UPDATE) to prevent concurrency race conditions
            cursor.execute("""
                SELECT id
                FROM leads
                WHERE current_owner_user_id IS NULL
                  AND NOT EXISTS (SELECT 1 FROM clients c WHERE c.lead_id = leads.id)
                  AND (lead_source = %s OR lead_source = %s)
                  AND (is_disposed = 0 OR is_disposed IS NULL)
                ORDER BY id ASC
                LIMIT %s
                FOR UPDATE
            """, (source_name, str(source_id), limit_to_fetch))
            unassigned_leads = cursor.fetchall()

            if not unassigned_leads:
                connection.commit()
                return {
                    "success": False,
                    "message": f"No unassigned leads are currently available in the system for {source_name}.",
                    "status_code": 404,
                }

            lead_ids = [row["id"] for row in unassigned_leads]
            placeholders = ", ".join(["%s"] * len(lead_ids))

            # 7. Atomically assign selected leads to the user (verifying current_owner_user_id IS NULL)
            cursor.execute(f"""
                UPDATE leads
                SET current_owner_user_id = (SELECT id FROM users WHERE user_uuid = %s LIMIT 1),
                    assigned_at = NOW()
                WHERE id IN ({placeholders})
                  AND current_owner_user_id IS NULL
            """, [logged_user_uuid] + lead_ids)

            assigned_count = cursor.rowcount
            if assigned_count == 0:
                connection.commit()
                return {
                    "success": False,
                    "message": "Leads were claimed by another agent just now. Please try again.",
                    "status_code": 409,
                }

            # Log fetch leads action into user_activities table
            user_act_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
            act_desc = f"Fetched {len(lead_ids)} lead(s) from source '{source_name}'"
            cursor.execute("""
                INSERT INTO user_activities (
                    user_activity_uuid, user_id, action_type, description, ip_address
                ) VALUES (%s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), 'Fetch Leads', %s, %s)
            """, (user_act_uuid, logged_user_uuid, act_desc, ip_address or None))

            connection.commit()

            return {
                "success": True,
                "message": f"Successfully fetched {len(lead_ids)} new lead(s) for {source_name}.",
                "count": len(lead_ids),
                "status_code": 200,
            }
    finally:
        connection.close()


def process_save_lead_response(logged_user_uuid, lead_uuid, status_name, comment="", ip_address=""):
    if not lead_uuid:
        return {
            "success": False,
            "message": "Lead is required.",
            "status_code": 400,
        }

    if not status_name or status_name == "no_status":
        return {
            "success": False,
            "message": "Please select a valid Lead Status.",
            "status_code": 400,
        }

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, lead_uuid, id AS client_code, name, lead_status
                FROM leads
                WHERE lead_uuid = %s
                  AND (current_owner_user_id = (SELECT id FROM users WHERE user_uuid = %s LIMIT 1) OR current_owner_user_id IS NULL)
                LIMIT 1
            """, (lead_uuid, logged_user_uuid))
            lead = cursor.fetchone()

            if not lead:
                return {
                    "success": False,
                    "message": "Lead not found or access denied.",
                    "status_code": 404,
                }

            lead_id = lead["id"]
            lead_name = lead.get("name") or "Lead"
            client_code = lead.get("client_code") or ""
            old_status = lead.get("lead_status") or "No Status"

            cursor.execute("""
                SELECT id, status_uuid, status_name
                FROM lead_statuses
                WHERE status_uuid = %s OR LOWER(status_name) = LOWER(%s) OR id = %s
                LIMIT 1
            """, (status_name, status_name, int(status_name) if str(status_name).isdigit() else -1))
            status_row = cursor.fetchone()
            
            if status_row:
                actual_status_name = status_row["status_name"]
                status_id_val = status_row["id"]
            elif str(status_name).isdigit():
                status_id_val = int(status_name)
                actual_status_name = f"Status #{status_name}"
            else:
                actual_status_name = str(status_name)
                status_id_val = lead.get("lead_status")

            existing_comment = lead.get("comment") or ""
            final_comment = comment if comment else existing_comment

            # 1. Update leads table (storing status ID in lead_status column, updating comment, and auto un-disposing)
            cursor.execute("""
                UPDATE leads
                SET lead_status = COALESCE(%s, lead_status),
                    comment = %s,
                    is_disposed = 0,
                    disposed_by = NULL,
                    disposed_at = NULL,
                    updated_at = NOW()
                WHERE id = %s
            """, (status_id_val, final_comment or "No comment", lead_id))

            # 3. Insert into lead_activities table
            activity_uuid = f"ACT{uuid.uuid4().hex[:12].upper()}"
            cursor.execute("""
                INSERT INTO lead_activities (
                    activity_uuid, lead_id, user_id, action_type, status_name, comment
                ) VALUES (%s, %s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), 'Status & Comment Updated', %s, %s)
            """, (activity_uuid, lead_id, logged_user_uuid, actual_status_name, comment or None))

            # 3. Insert into user_activities table
            user_act_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
            act_desc = f"Updated status of lead {client_code} ({lead_name}) to '{actual_status_name}'"
            if comment:
                act_desc += f" with comment: '{comment}'"

            cursor.execute("""
                INSERT INTO user_activities (
                    user_activity_uuid, user_id, lead_id, action_type, description, ip_address
                ) VALUES (%s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), %s, 'Lead Response Saved', %s, %s)
            """, (user_act_uuid, logged_user_uuid, lead_id, act_desc, ip_address or None))

            # 4. Insert into lead_timeline table if exists
            timeline_uuid = f"LH{uuid.uuid4().hex[:12].upper()}"
            cursor.execute("""
                INSERT INTO lead_timeline (
                    history_uuid, lead_id, action_type, old_status, new_status, action_by, remark
                ) VALUES (%s, %s, 'Status Submitted', %s, %s, %s, %s)
            """, (timeline_uuid, lead_id, old_status, actual_status_name, logged_user_uuid, comment or None))

            connection.commit()

            return {
                "success": True,
                "message": f"Lead response updated successfully to '{actual_status_name}'.",
                "status_code": 200,
            }
    finally:
        connection.close()


def process_dispose_lead(logged_user_uuid, lead_uuid, status_name="", reason="", ip_address=""):
    if not lead_uuid:
        return {
            "success": False,
            "message": "Lead is required.",
            "status_code": 400,
        }

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check user role & ID
            cursor.execute("SELECT id, role_id, is_admin FROM users WHERE user_uuid = %s LIMIT 1", (logged_user_uuid,))
            u_row = cursor.fetchone()
            if not u_row:
                return {
                    "success": False,
                    "message": "User not found or session expired.",
                    "status_code": 401,
                }

            user_id = u_row["id"]
            is_admin_or_manager = bool(u_row.get("is_admin") == 1 or u_row.get("role_id") in (1, 2))

            if is_admin_or_manager:
                cursor.execute("""
                    SELECT id, lead_uuid, id AS client_code, name, lead_status, comment
                    FROM leads
                    WHERE (lead_uuid = %s OR id = %s)
                    LIMIT 1
                """, (lead_uuid, lead_uuid if str(lead_uuid).isdigit() else -1))
            else:
                cursor.execute("""
                    SELECT id, lead_uuid, id AS client_code, name, lead_status, comment
                    FROM leads
                    WHERE (lead_uuid = %s OR id = %s)
                      AND (current_owner_user_id = %s OR current_owner_user_id IS NULL OR current_owner_user_id = 0)
                    LIMIT 1
                """, (lead_uuid, lead_uuid if str(lead_uuid).isdigit() else -1, user_id))

            lead = cursor.fetchone()

            if not lead:
                return {
                    "success": False,
                    "message": "Lead not found or access denied.",
                    "status_code": 404,
                }

            lead_id = lead["id"]
            lead_name = lead.get("name") or "Lead"
            client_code = lead.get("client_code") or ""
            old_status = lead.get("lead_status") or "No Status"
            disp_reason = reason or "Lead Disposed"

            # Resolve status row from lead_statuses
            actual_status_name = "Disposed"
            status_id_val = None

            if status_name:
                cursor.execute("""
                    SELECT id, status_uuid, status_name
                    FROM lead_statuses
                    WHERE status_uuid = %s OR LOWER(status_name) = LOWER(%s) OR id = %s
                    LIMIT 1
                """, (status_name, status_name, int(status_name) if str(status_name).isdigit() else -1))
                status_row = cursor.fetchone()
                if status_row:
                    actual_status_name = status_row["status_name"]
                    status_id_val = status_row["id"]
                elif str(status_name).isdigit():
                    status_id_val = int(status_name)
                    actual_status_name = f"Status #{status_name}"
                else:
                    actual_status_name = str(status_name)
                    status_id_val = lead.get("lead_status")
            else:
                status_id_val = lead.get("lead_status")
                actual_status_name = str(status_id_val or "Disposed")

            # Update leads table: set is_disposed = 1, disposed_by = user_id, disposed_at = NOW()
            cursor.execute("""
                UPDATE leads
                SET lead_status = COALESCE(%s, lead_status),
                    is_disposed = 1,
                    comment = %s,
                    disposed_by = %s,
                    disposed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (status_id_val, disp_reason, user_id, lead_id))

            # Insert activity logs
            activity_uuid = f"ACT{uuid.uuid4().hex[:12].upper()}"
            cursor.execute("""
                INSERT INTO lead_activities (
                    activity_uuid, lead_id, user_id, action_type, status_name, comment
                ) VALUES (%s, %s, %s, 'Lead Disposed', %s, %s)
            """, (activity_uuid, lead_id, user_id, actual_status_name, disp_reason))

            user_act_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
            act_desc = f"Disposed lead {client_code} ({lead_name}) with status '{actual_status_name}' - Remark: '{disp_reason}'"

            cursor.execute("""
                INSERT INTO user_activities (
                    user_activity_uuid, user_id, lead_id, action_type, description, ip_address
                ) VALUES (%s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), %s, 'Lead Disposed', %s, %s)
            """, (user_act_uuid, logged_user_uuid, lead_id, act_desc, ip_address or None))

            timeline_uuid = f"LH{uuid.uuid4().hex[:12].upper()}"
            cursor.execute("""
                INSERT INTO lead_timeline (
                    history_uuid, lead_id, action_type, old_status, new_status, action_by, remark
                ) VALUES (%s, %s, 'Lead Disposed', %s, %s, %s, %s)
            """, (timeline_uuid, lead_id, old_status, actual_status_name, logged_user_uuid, disp_reason))

            connection.commit()

            return {
                "success": True,
                "message": f"Lead {client_code} has been disposed successfully with status '{actual_status_name}'.",
                "status_code": 200,
            }
    finally:
        connection.close()


def process_resume_lead(logged_user_uuid, lead_uuid, ip_address=""):
    """
    Activate (resume) a disposed lead — sets is_disposed = 0
    and logs the activity in the timeline.
    """
    if not lead_uuid:
        return {
            "success": False,
            "message": "Lead is required.",
            "status_code": 400,
        }

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Check user
            cursor.execute("SELECT id, is_admin, role_id FROM users WHERE user_uuid = %s LIMIT 1", (logged_user_uuid,))
            u_row = cursor.fetchone()
            if not u_row:
                return {
                    "success": False,
                    "message": "User not found or session expired.",
                    "status_code": 401,
                }

            user_id = u_row["id"]
            is_admin_or_manager = bool(u_row.get("is_admin") == 1 or u_row.get("role_id") in (1, 2))

            # Fetch lead
            if is_admin_or_manager:
                cursor.execute("""
                    SELECT id, lead_uuid, id AS client_code, name, lead_status
                    FROM leads
                    WHERE (lead_uuid = %s OR id = %s)
                    LIMIT 1
                """, (lead_uuid, lead_uuid if str(lead_uuid).isdigit() else -1))
            else:
                cursor.execute("""
                    SELECT id, lead_uuid, id AS client_code, name, lead_status
                    FROM leads
                    WHERE (lead_uuid = %s OR id = %s)
                      AND (current_owner_user_id = %s OR current_owner_user_id IS NULL OR current_owner_user_id = 0)
                    LIMIT 1
                """, (lead_uuid, lead_uuid if str(lead_uuid).isdigit() else -1, user_id))

            lead = cursor.fetchone()
            if not lead:
                return {
                    "success": False,
                    "message": "Lead not found or access denied.",
                    "status_code": 404,
                }

            lead_id = lead["id"]
            lead_name = lead.get("name") or "Lead"
            client_code = lead.get("client_code") or ""
            old_status = lead.get("lead_status") or "Disposed"

            # Activate lead
            cursor.execute("""
                UPDATE leads
                SET is_disposed = 0,
                    disposed_by = NULL,
                    disposed_at = NULL,
                    updated_at = NOW()
                WHERE id = %s
            """, (lead_id,))

            # Log activity
            activity_uuid = f"ACT{uuid.uuid4().hex[:12].upper()}"
            cursor.execute("""
                INSERT INTO lead_activities (
                    activity_uuid, lead_id, user_id, action_type, status_name, comment
                ) VALUES (%s, %s, %s, 'Lead Activated', %s, %s)
            """, (activity_uuid, lead_id, user_id, str(old_status), "Lead activated from Disposed state"))

            user_act_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
            act_desc = f"Activated disposed lead {client_code} ({lead_name})"
            cursor.execute("""
                INSERT INTO user_activities (
                    user_activity_uuid, user_id, lead_id, action_type, description, ip_address
                ) VALUES (%s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), %s, 'Lead Activated', %s, %s)
            """, (user_act_uuid, logged_user_uuid, lead_id, act_desc, ip_address or None))

            timeline_uuid = f"LH{uuid.uuid4().hex[:12].upper()}"
            cursor.execute("""
                INSERT INTO lead_timeline (
                    history_uuid, lead_id, action_type, old_status, new_status, action_by, remark
                ) VALUES (%s, %s, 'Lead Activated', %s, 'Active', %s, %s)
            """, (timeline_uuid, lead_id, str(old_status), logged_user_uuid, "Activated from disposed state"))

            connection.commit()

            return {
                "success": True,
                "message": f"Lead {client_code} ({lead_name}) has been activated successfully.",
                "status_code": 200,
            }
    finally:
        connection.close()



def process_delete_lead(logged_user_uuid, lead_uuids, ip_address=None):
    """
    Delete one or multiple leads and record user_activities log for each deletion.
    """
    if not lead_uuids:
        return {
            "success": False,
            "message": "No lead specified for deletion.",
            "status_code": 400,
        }

    if isinstance(lead_uuids, str):
        lead_uuids = [lead_uuids]

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            # 1. Fetch user info
            cursor.execute("""
                SELECT id, full_name
                FROM users
                WHERE user_uuid = %s AND status = 1
                LIMIT 1
            """, (logged_user_uuid,))
            logged_user = cursor.fetchone()

            if not logged_user:
                return {
                    "success": False,
                    "message": "User not found or inactive.",
                    "status_code": 401,
                }

            user_id = logged_user["id"]

            # 2. Fetch leads to delete
            placeholders = ", ".join(["%s"] * len(lead_uuids))
            cursor.execute(f"""
                SELECT id, lead_uuid, name, mobile_number
                FROM leads
                WHERE lead_uuid IN ({placeholders})
            """, lead_uuids)
            leads_to_delete = cursor.fetchall()

            if not leads_to_delete:
                return {
                    "success": False,
                    "message": "No valid leads found to delete.",
                    "status_code": 404,
                }

            lead_ids = [l["id"] for l in leads_to_delete]
            lead_id_placeholders = ", ".join(["%s"] * len(lead_ids))

            # 3. Delete referenced child rows first
            cursor.execute(f"DELETE FROM followups WHERE lead_id IN ({lead_id_placeholders})", lead_ids)
            cursor.execute(f"DELETE FROM contacts WHERE lead_id IN ({lead_id_placeholders})", lead_ids)
            cursor.execute(f"DELETE FROM free_trials WHERE lead_id IN ({lead_id_placeholders})", lead_ids)
            cursor.execute(f"DELETE FROM sales_orders WHERE lead_id IN ({lead_id_placeholders})", lead_ids)
            cursor.execute(f"DELETE FROM clients WHERE lead_id IN ({lead_id_placeholders})", lead_ids)
            cursor.execute(f"UPDATE user_activities SET lead_id = NULL WHERE lead_id IN ({lead_id_placeholders})", lead_ids)

            # 4. Insert single summary log into user_activities BEFORE deleting from leads table
            count = len(leads_to_delete)
            if count == 1:
                l0 = leads_to_delete[0]
                c_code = f"LEAD{l0['id']}"
                desc = f"Deleted 1 lead ({c_code})"
            else:
                desc = f"Deleted {count} leads"

            uact_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
            cursor.execute("""
                INSERT INTO user_activities (
                    user_activity_uuid, user_id, lead_id, action_type, description, ip_address
                ) VALUES (%s, %s, NULL, 'Lead Delete', %s, %s)
            """, (uact_uuid, user_id, desc, ip_address or None))

            # 5. Delete from leads table
            cursor.execute(f"DELETE FROM leads WHERE id IN ({lead_id_placeholders})", lead_ids)

            connection.commit()

            count = len(leads_to_delete)
            return {
                "success": True,
                "message": f"Successfully deleted {count} lead(s).",
                "deleted_count": count,
                "status_code": 200,
            }
    finally:
        connection.close()


def process_assign_leads(
    logged_user_uuid,
    target_user_uuid,
    lead_uuids=None,
    new_source=None,
    reset_data=False,
    apply_all_matching=False,
    filter_params=None,
    ip_address=None,
):
    """
    Assign leads to a target user, with optional source change and reset data options.
    Records lead_activities for each lead and a single summary log in user_activities.
    """
    from utils.permissions import has_permission

    if not has_permission('global_access_scope', 'global_data_access'):
        new_source = None
        reset_data = False
        apply_all_matching = False

    if not target_user_uuid:
        return {
            "success": False,
            "message": "Please select a target user to assign leads.",
            "status_code": 400,
        }

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            # 1. Resolve logged user
            cursor.execute("""
                SELECT id, full_name
                FROM users
                WHERE user_uuid = %s AND status = 1
                LIMIT 1
            """, (logged_user_uuid,))
            logged_user = cursor.fetchone()

            if not logged_user:
                return {
                    "success": False,
                    "message": "Logged-in user not found.",
                    "status_code": 401,
                }

            logged_user_id = logged_user["id"]

            # 2. Resolve target user / option
            target_user_id = None
            target_user_name = "Keep Same"
            is_unassign_mode = False
            is_keep_same_mode = False

            if str(target_user_uuid).strip() in ["unassigned", "no_assign", "null", "none"]:
                is_unassign_mode = True
                target_user_id = None
                target_user_name = "Unassigned"
            elif str(target_user_uuid).strip() in ["keep_same", "keep_current", ""]:
                is_keep_same_mode = True
                target_user_name = "Keep Same"
            else:
                cursor.execute("""
                    SELECT id, full_name
                    FROM users
                    WHERE (user_uuid = %s OR id = %s) AND status = 1
                    LIMIT 1
                """, (target_user_uuid, target_user_uuid if str(target_user_uuid).isdigit() else -1))
                target_user = cursor.fetchone()

                if not target_user:
                    return {
                        "success": False,
                        "message": "Selected target user for assignment was not found.",
                        "status_code": 404,
                    }

                target_user_id = target_user["id"]
                target_user_name = target_user["full_name"]

            # 3. Resolve lead source if provided
            resolved_source_val = None
            resolved_source_name = None
            if new_source and str(new_source).strip() and str(new_source).strip() != "keep_current":
                cursor.execute("""
                    SELECT id, source_name
                    FROM lead_sources
                    WHERE source_name = %s OR id = %s OR source_uuid = %s
                    LIMIT 1
                """, (new_source, new_source if str(new_source).isdigit() else -1, new_source))
                src_row = cursor.fetchone()
                if src_row:
                    resolved_source_val = str(src_row["id"])
                    resolved_source_name = src_row["source_name"]
                else:
                    resolved_source_val = str(new_source).strip()
                    resolved_source_name = str(new_source).strip()

            # 4. Fetch leads to assign
            leads_to_assign = []
            if apply_all_matching:
                from routes.lead.all_leads_table import fetch_lead_rows
                from routes.lead.all_leads_filters import apply_lead_filters, get_filter_request_values

                filter_values = get_filter_request_values(filter_params or {}, logged_user_uuid)
                all_rows = fetch_lead_rows(logged_user_uuid)
                filtered_rows = apply_lead_filters(all_rows, filter_values)

                matching_uuids = [r["lead_uuid"] for r in filtered_rows if r.get("lead_uuid")]
                if matching_uuids:
                    placeholders = ", ".join(["%s"] * len(matching_uuids))
                    cursor.execute(f"""
                        SELECT id, lead_uuid, name, mobile_number, lead_source, lead_status
                        FROM leads
                        WHERE lead_uuid IN ({placeholders})
                    """, matching_uuids)
                    leads_to_assign = cursor.fetchall()
            else:
                if isinstance(lead_uuids, str):
                    lead_uuids = [lead_uuids]
                lead_uuids = [u for u in (lead_uuids or []) if u]

                if lead_uuids:
                    placeholders = ", ".join(["%s"] * len(lead_uuids))
                    cursor.execute(f"""
                        SELECT id, lead_uuid, name, mobile_number, lead_source, lead_status
                        FROM leads
                        WHERE lead_uuid IN ({placeholders})
                    """, lead_uuids)
                    leads_to_assign = cursor.fetchall()

            if not leads_to_assign:
                return {
                    "success": False,
                    "message": "No valid leads found to update.",
                    "status_code": 404,
                }

            lead_ids = [l["id"] for l in leads_to_assign]
            lead_id_placeholders = ", ".join(["%s"] * len(lead_ids))

            # 5. Build UPDATE SQL query
            update_fields = ["updated_at = NOW()"]
            update_values = []

            if is_unassign_mode:
                update_fields.extend(["current_owner_user_id = NULL", "assigned_at = NULL"])
            elif not is_keep_same_mode and target_user_id is not None:
                update_fields.extend(["current_owner_user_id = %s", "call_status = 0", "assigned_at = NOW()"])
                update_values.append(target_user_id)

            if resolved_source_val is not None:
                update_fields.append("lead_source = %s")
                update_values.append(resolved_source_val)

            if reset_data:
                update_fields.extend([
                    "is_disposed = 0",
                    "lead_status = NULL",
                    "comment = ''",
                    "disposed_by = NULL",
                    "disposed_at = NULL",
                ])

            update_values.extend(lead_ids)

            cursor.execute(f"""
                UPDATE leads
                SET {", ".join(update_fields)}
                WHERE id IN ({lead_id_placeholders})
            """, update_values)

            # 6. Insert lead_activities for each lead
            for l in leads_to_assign:
                lead_id = l["id"]
                act_uuid = f"ACT{uuid.uuid4().hex[:12].upper()}"
                
                if is_unassign_mode:
                    remark_parts = ["Lead Unassigned (Owner removed)"]
                elif is_keep_same_mode:
                    remark_parts = ["Lead Owner kept unchanged"]
                else:
                    remark_parts = [f"Assigned to {target_user_name}"]
                if resolved_source_name:
                    remark_parts.append(f"Source changed to '{resolved_source_name}'")
                if reset_data:
                    remark_parts.append("Status & comments reset")
                
                remark_str = " | ".join(remark_parts)

                cursor.execute("""
                    INSERT INTO lead_activities (
                        activity_uuid, lead_id, user_id, action_type, status_name, comment
                    ) VALUES (%s, %s, %s, 'Lead Assigned', 'Assigned', %s)
                """, (act_uuid, lead_id, logged_user_id, remark_str))

            # 7. Insert single summary log in user_activities
            count = len(leads_to_assign)
            uact_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
            
            desc_parts = [f"Assigned {count} lead(s) to '{target_user_name}'"]
            if resolved_source_name:
                desc_parts.append(f"New Source: '{resolved_source_name}'")
            if reset_data:
                desc_parts.append("Reset Data Applied")

            user_act_desc = " - ".join(desc_parts)

            cursor.execute("""
                INSERT INTO user_activities (
                    user_activity_uuid, user_id, lead_id, action_type, description, ip_address
                ) VALUES (%s, %s, NULL, 'Lead Assigned', %s, %s)
            """, (uact_uuid, logged_user_id, user_act_desc, ip_address or None))

            connection.commit()

            return {
                "success": True,
                "message": f"Successfully assigned {count} lead(s) to {target_user_name}.",
                "assigned_count": count,
                "status_code": 200,
            }
    finally:
        connection.close()


def process_get_lead_timeline(logged_user_uuid, lead_uuid, page=1, limit=15):
    """
    Fetch paginated activity timeline for a lead.
    """
    if not lead_uuid:
        return {
            "success": False,
            "message": "Lead identifier is required.",
            "status_code": 400,
        }

    try:
        page = int(page) if int(page) > 0 else 1
    except (ValueError, TypeError):
        page = 1

    try:
        limit = int(limit) if int(limit) > 0 else 15
    except (ValueError, TypeError):
        limit = 15

    offset = (page - 1) * limit
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            # 1. Fetch Lead Details
            cursor.execute("""
                SELECT l.id, l.lead_uuid, l.name, l.mobile_number, l.current_owner_user_id, l.created_by, u.full_name as owner_name
                FROM leads l
                LEFT JOIN users u ON l.current_owner_user_id = u.id
                WHERE l.lead_uuid = %s OR l.id = %s
                LIMIT 1
            """, (lead_uuid, lead_uuid if str(lead_uuid).isdigit() else -1))
            lead = cursor.fetchone()

            if not lead:
                return {
                    "success": False,
                    "message": "Lead not found.",
                    "status_code": 404,
                }

            # Security Permission Check: Verify lead is in logged user's hierarchy
            from routes.settings_helpers import fetch_user_tree
            allowed_user_ids, allowed_user_uuids = fetch_user_tree(cursor, logged_user_uuid)

            if not allowed_user_ids:
                return {
                    "success": False,
                    "message": "Access Denied: Invalid user session.",
                    "status_code": 401,
                }

            lead_owner_id = lead.get("current_owner_user_id")
            lead_creator_id = lead.get("created_by")

            is_authorized = False
            # If lead is unassigned OR lead owner/creator is in logged user's hierarchy tree
            if not lead_owner_id or lead_owner_id == 0:
                is_authorized = True
            elif (lead_owner_id and lead_owner_id in allowed_user_ids) or (lead_creator_id and lead_creator_id in allowed_user_ids):
                is_authorized = True

            if not is_authorized:
                return {
                    "success": False,
                    "message": "Access Denied: You do not have permission to view this lead's timeline.",
                    "status_code": 403,
                }

            lead_id = lead["id"]
            client_code = f"LEAD{lead_id}"
            lead_name = lead.get("name") or "Lead"
            mobile_number = lead.get("mobile_number") or ""
            owner_name = lead.get("owner_name") or "Unassigned"

            # 2. Count Total Activities
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM lead_activities
                WHERE lead_id = %s
            """, (lead_id,))
            cnt_row = cursor.fetchone()
            total_count = cnt_row["cnt"] if cnt_row else 0

            # 3. Fetch Paginated Activities
            cursor.execute("""
                SELECT 
                    la.id, la.activity_uuid, la.action_type, la.status_name, la.comment, la.created_at,
                    u.full_name as user_name
                FROM lead_activities la
                LEFT JOIN users u ON la.user_id = u.id
                WHERE la.lead_id = %s
                ORDER BY la.id DESC
                LIMIT %s OFFSET %s
            """, (lead_id, limit, offset))
            rows = cursor.fetchall()

            formatted_activities = []
            for r in rows:
                dt_str = r["created_at"].strftime("%d %b %Y, %I:%M %p") if r.get("created_at") else ""
                formatted_activities.append({
                    "id": r["id"],
                    "activity_uuid": r.get("activity_uuid") or f"ACT{r['id']}",
                    "action_type": r.get("action_type") or "Activity",
                    "status_name": r.get("status_name") or "",
                    "comment": r.get("comment") or "",
                    "user_name": r.get("user_name") or "System",
                    "created_at": dt_str,
                })

            has_more = (offset + len(formatted_activities)) < total_count

            return {
                "success": True,
                "lead": {
                    "client_code": client_code,
                    "name": lead_name,
                    "mobile_number": mobile_number,
                    "owner_name": owner_name,
                },
                "activities": formatted_activities,
                "page": page,
                "limit": limit,
                "total_count": total_count,
                "has_more": has_more,
                "status_code": 200,
            }
    finally:
        connection.close()


def process_save_contact(
    logged_user_uuid,
    lead_uuid,
    contact_name,
    mobile_number=None,
    email=None,
    address=None,
    product_id=None,
    plan_type=None,
    notes=None,
    status_name=None,
    status_id=None,
    ip_address=None,
):
    """
    Save contact details for a lead, update leads status & has_contact = 1, insert into contacts table,
    and log activity in lead_activities & user_activities.
    """
    if not lead_uuid:
        return {
            "success": False,
            "message": "Lead identifier is required.",
            "status_code": 400,
        }

    if not contact_name or not str(contact_name).strip():
        return {
            "success": False,
            "message": "Contact name is required.",
            "status_code": 400,
        }

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            # 1. Resolve logged user
            cursor.execute("SELECT id, full_name FROM users WHERE user_uuid = %s AND status = 1 LIMIT 1", (logged_user_uuid,))
            logged_user = cursor.fetchone()
            if not logged_user:
                return {
                    "success": False,
                    "message": "Logged-in user not found.",
                    "status_code": 401,
                }
            logged_user_id = logged_user["id"]

            # 2. Resolve lead
            cursor.execute("SELECT id, lead_uuid, name, mobile_number, email, address FROM leads WHERE lead_uuid = %s OR id = %s LIMIT 1", (lead_uuid, lead_uuid if str(lead_uuid).isdigit() else -1))
            lead = cursor.fetchone()
            if not lead:
                return {
                    "success": False,
                    "message": "Target lead not found.",
                    "status_code": 404,
                }
            lead_id = lead["id"]
            client_code = f"LEAD{lead_id}"
            target_mobile = mobile_number or lead.get("mobile_number") or ""

            # Resolve status if provided
            resolved_status_id = None
            resolved_status_name = None
            if status_id or status_name:
                if status_id:
                    cursor.execute("SELECT id, status_name FROM lead_statuses WHERE id = %s OR status_uuid = %s LIMIT 1", (status_id, status_id))
                else:
                    cursor.execute("SELECT id, status_name FROM lead_statuses WHERE LOWER(status_name) = %s LIMIT 1", (str(status_name).strip().lower(),))
                st_row = cursor.fetchone()
                if st_row:
                    resolved_status_id = st_row["id"]
                    resolved_status_name = st_row["status_name"]
                elif status_name:
                    resolved_status_name = str(status_name).strip()

            # Resolve product name if product_id is provided
            product_name = None
            if product_id:
                cursor.execute("SELECT id, product_name FROM products WHERE id = %s LIMIT 1", (product_id,))
                prod = cursor.fetchone()
                if prod:
                    product_name = prod["product_name"]

            # 3. Update leads table: update email, address, & status if provided, and auto un-dispose
            update_lead_fields = ["updated_at = NOW()", "is_disposed = 0", "disposed_by = NULL", "disposed_at = NULL"]
            update_lead_vals = []

            if resolved_status_id:
                update_lead_fields.append("lead_status = %s")
                update_lead_vals.append(resolved_status_id)

            if email and str(email).strip():
                update_lead_fields.append("email = %s")
                update_lead_vals.append(str(email).strip())

            if address and str(address).strip():
                update_lead_fields.append("address = %s")
                update_lead_vals.append(str(address).strip())

            if notes and str(notes).strip():
                clean_notes = str(notes).strip()
                update_lead_fields.append("comment = %s")
                update_lead_vals.append(clean_notes)

            update_lead_vals.append(lead_id)
            cursor.execute(f"UPDATE leads SET {', '.join(update_lead_fields)} WHERE id = %s", update_lead_vals)

            # 4. Insert or Update contacts table
            cursor.execute("SELECT id FROM contacts WHERE lead_id = %s LIMIT 1", (lead_id,))
            existing_contact = cursor.fetchone()

            if existing_contact:
                cursor.execute("""
                    UPDATE contacts
                    SET contact_name = %s, mobile_number = %s, email = %s, address = %s,
                        product_id = %s, plan_type = %s, notes = %s, updated_at = NOW()
                    WHERE id = %s
                """, (contact_name.strip(), target_mobile, email or None, address or None,
                      product_id or None, plan_type or None, notes or None, existing_contact["id"]))
            else:
                cont_uuid = f"CONT{uuid.uuid4().hex[:12].upper()}"
                cursor.execute("""
                    INSERT INTO contacts (
                        contact_uuid, lead_id, created_by_user_id, created_by_name, contact_name, mobile_number, email, address, product_id, plan_type, notes, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW())
                """, (cont_uuid, lead_id, logged_user_id, logged_user.get("full_name") or "System", contact_name.strip(), target_mobile, email or None, address or None,
                      product_id or None, plan_type or None, notes or None))

            # 5. Insert audit log into lead_activities
            act_uuid = f"ACT{uuid.uuid4().hex[:12].upper()}"
            act_remark = f"Saved contact '{contact_name.strip()}'"
            if product_name:
                act_remark += f" | Product: {product_name}"
            if plan_type:
                act_remark += f" | Plan: {plan_type}"

            cursor.execute("""
                INSERT INTO lead_activities (
                    activity_uuid, lead_id, user_id, action_type, status_name, comment
                ) VALUES (%s, %s, %s, 'Contact Saved', %s, %s)
            """, (act_uuid, lead_id, logged_user_id, resolved_status_name or 'Contact Saved', act_remark))

            # 6. Insert summary log into user_activities
            uact_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
            uact_desc = f"Saved contact '{contact_name.strip()}' for lead {client_code}"
            if product_name:
                uact_desc += f" ({product_name})"

            cursor.execute("""
                INSERT INTO user_activities (
                    user_activity_uuid, user_id, lead_id, action_type, description, ip_address
                ) VALUES (%s, %s, NULL, 'Contact Saved', %s, %s)
            """, (uact_uuid, logged_user_id, uact_desc, ip_address or None))

            connection.commit()

            return {
                "success": True,
                "message": f"Successfully saved contact for lead {client_code}.",
                "status_code": 200,
            }
    finally:
        connection.close()


def process_get_lead_contacts(logged_user_uuid, lead_uuid):
    """
    Fetch contact list for a lead.
    """
    if not lead_uuid:
        return {
            "success": False,
            "message": "Lead identifier is required.",
            "status_code": 400,
        }

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            from routes.settings_helpers import fetch_user_tree
            allowed_user_ids, _ = fetch_user_tree(cursor, logged_user_uuid)

            cursor.execute("""
                SELECT id, name, mobile_number, current_owner_user_id, created_by
                FROM leads
                WHERE lead_uuid = %s OR id = %s
                LIMIT 1
            """, (lead_uuid, lead_uuid if str(lead_uuid).isdigit() else -1))
            lead = cursor.fetchone()

            if not lead:
                return {
                    "success": False,
                    "message": "Lead not found.",
                    "status_code": 404,
                }

            lead_id = lead["id"]
            lead_owner_id = lead.get("current_owner_user_id")
            lead_creator_id = lead.get("created_by")

            is_auth = False
            if not lead_owner_id or lead_owner_id == 0 or (allowed_user_ids and (lead_owner_id in allowed_user_ids or lead_creator_id in allowed_user_ids)):
                is_auth = True

            if not is_auth:
                return {
                    "success": False,
                    "message": "Access Denied.",
                    "status_code": 403,
                }

            cursor.execute("""
                SELECT 
                    c.id, c.contact_uuid, c.contact_name, c.mobile_number, c.email, c.address,
                    c.plan_type, c.notes, c.created_at,
                    p.product_name
                FROM contacts c
                LEFT JOIN products p ON c.product_id = p.id
                WHERE c.lead_id = %s
                ORDER BY c.id DESC
            """, (lead_id,))
            contacts = cursor.fetchall()

            formatted_contacts = []
            for c in contacts:
                dt_str = c["created_at"].strftime("%d %b %Y, %I:%M %p") if c.get("created_at") else ""
                formatted_contacts.append({
                    "id": c["id"],
                    "contact_name": c.get("contact_name") or "",
                    "mobile_number": c.get("mobile_number") or "",
                    "email": c.get("email") or "",
                    "address": c.get("address") or "",
                    "product_name": c.get("product_name") or "None",
                    "plan_type": c.get("plan_type") or "None",
                    "notes": c.get("notes") or "",
                    "created_at": dt_str,
                })

            return {
                "success": True,
                "lead": {
                    "client_code": f"LEAD{lead_id}",
                    "name": lead.get("name") or "Lead",
                    "mobile_number": lead.get("mobile_number") or "",
                },
                "contacts": formatted_contacts,
                "status_code": 200,
            }
    finally:
        connection.close()


def process_add_followup(
    logged_user_uuid,
    lead_uuid,
    followup_date,
    remarks,
    name=None,
    email=None,
    address=None,
    lead_status=None,
    ip_address=None,
):
    """
    Schedules a new follow-up for a lead:
    1. Inserts into followups table.
    2. Updates leads table (comment = remarks, name, email, address, lead_status, updated_at).
    3. Logs activity into lead_activities and user_activities.
    """
    if not lead_uuid:
        return {
            "success": False,
            "message": "Lead identifier is required.",
            "status_code": 400,
        }

    if not followup_date:
        return {
            "success": False,
            "message": "Follow-up date and time is required.",
            "status_code": 400,
        }

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, lead_uuid, name, id AS client_code, lead_status
                FROM leads
                WHERE lead_uuid = %s LIMIT 1
            """, (lead_uuid,))
            lead = cursor.fetchone()

            if not lead:
                return {
                    "success": False,
                    "message": "Target lead not found.",
                    "status_code": 444,
                }

            lead_id = lead["id"]
            client_code = f"LEAD{lead_id}"
            lead_name = (name.strip() if name and str(name).strip() else None) or lead.get("name") or "Lead"
            curr_status = lead.get("lead_status") or "No Status"

            cursor.execute("SELECT id, full_name FROM users WHERE user_uuid = %s LIMIT 1", (logged_user_uuid,))
            logged_user_row = cursor.fetchone()
            logged_user_id = logged_user_row["id"] if logged_user_row else None
            logged_user_name = logged_user_row["full_name"] if logged_user_row else "System"

            followup_uuid = f"FOL{uuid.uuid4().hex[:12].upper()}"
            cursor.execute("""
                INSERT INTO followups (
                    followup_uuid, lead_id, created_by_user_id, created_by_name, followup_date, followup_type, followup_status, notes, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, 'General', 'pending', %s, NOW()
                )
            """, (followup_uuid, lead_id, logged_user_id, logged_user_name, followup_date, remarks or None))

            update_fields = ["updated_at = NOW()", "is_disposed = 0", "disposed_by = NULL", "disposed_at = NULL"]
            update_params = []

            if remarks:
                update_fields.append("comment = %s")
                update_params.append(remarks)

            if name is not None and str(name).strip() != "":
                update_fields.append("name = %s")
                update_params.append(str(name).strip())

            if email is not None and str(email).strip() != "":
                update_fields.append("email = %s")
                update_params.append(str(email).strip())

            if address is not None and str(address).strip() != "":
                update_fields.append("address = %s")
                update_params.append(str(address).strip())

            if lead_status is not None and str(lead_status).strip() != "":
                try:
                    st_val = int(lead_status)
                except Exception:
                    st_val = str(lead_status).strip()
                update_fields.append("lead_status = %s")
                update_params.append(st_val)

            update_params.append(lead_id)
            cursor.execute(f"UPDATE leads SET {', '.join(update_fields)} WHERE id = %s", update_params)

            activity_uuid = f"ACT{uuid.uuid4().hex[:12].upper()}"
            act_comment = f"Scheduled follow-up for {followup_date}" + (f": {remarks}" if remarks else "")
            cursor.execute("""
                INSERT INTO lead_activities (
                    activity_uuid, lead_id, user_id, action_type, status_name, comment
                ) VALUES (%s, %s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), 'Follow-up Scheduled', %s, %s)
            """, (activity_uuid, lead_id, logged_user_uuid, curr_status, act_comment))

            user_act_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
            user_desc = f"Scheduled follow-up for lead {client_code} ({lead_name}) at {followup_date}"
            cursor.execute("""
                INSERT INTO user_activities (
                    user_activity_uuid, user_id, lead_id, action_type, description, ip_address
                ) VALUES (%s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), %s, 'Add Follow-up', %s, %s)
            """, (user_act_uuid, logged_user_uuid, lead_id, user_desc, ip_address or "127.0.0.1"))

            connection.commit()

            return {
                "success": True,
                "message": f"Follow-up scheduled for lead {client_code} successfully.",
                "status_code": 200,
            }
    except Exception as e:
        connection.rollback()
        return {
            "success": False,
            "message": f"Database error: {str(e)}",
            "status_code": 500,
        }
    finally:
        connection.close()


def process_add_free_trial(
    logged_user_uuid,
    lead_uuid,
    product_id,
    start_date,
    notes=None,
    lead_status=None,
    name=None,
    ip_address=None,
):
    """
    Activates a free trial for a lead:
    1. Fetches configured free_trial_days setting from system_settings.
    2. Auto-calculates end_date (expiry) skipping Saturdays and Sundays.
    3. Inserts into free_trials table.
    4. Updates leads table (name, lead_status, updated_at = NOW()).
    5. Logs activity into lead_activities and user_activities.
    """
    if not lead_uuid:
        return {
            "success": False,
            "message": "Lead identifier is required.",
            "status_code": 400,
        }

    if not product_id:
        return {
            "success": False,
            "message": "Product selection is required.",
            "status_code": 400,
        }

    if not start_date:
        return {
            "success": False,
            "message": "Trial start date is required.",
            "status_code": 400,
        }

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, lead_uuid, name, id AS client_code, lead_status
                FROM leads
                WHERE lead_uuid = %s LIMIT 1
            """, (lead_uuid,))
            lead = cursor.fetchone()

            if not lead:
                return {
                    "success": False,
                    "message": "Target lead not found.",
                    "status_code": 444,
                }

            lead_id = lead["id"]
            client_code = f"LEAD{lead_id}"
            lead_name = (name.strip() if name and str(name).strip() else None) or lead.get("name") or "Lead"
            curr_status = lead.get("lead_status") or "No Status"

            product_name = f"Product #{product_id}"
            cursor.execute("SELECT product_name FROM products WHERE id = %s LIMIT 1", (product_id,))
            prod = cursor.fetchone()
            if prod and prod.get("product_name"):
                product_name = prod["product_name"]

            from routes.settings_helpers import calculate_free_trial_expiry
            expiry_date_obj = calculate_free_trial_expiry(start_date, cursor=cursor)
            expiry_date_str = expiry_date_obj.strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("SELECT id, full_name FROM users WHERE user_uuid = %s LIMIT 1", (logged_user_uuid,))
            logged_user_row = cursor.fetchone()
            logged_user_id = logged_user_row["id"] if logged_user_row else None
            logged_user_name = logged_user_row["full_name"] if logged_user_row else "System"

            trial_uuid = f"TRL{uuid.uuid4().hex[:12].upper()}"
            cursor.execute("""
                INSERT INTO free_trials (
                    free_trial_uuid, lead_id, created_by_user_id, created_by_name, trial_name, start_date, end_date, trial_status, notes, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, 'active', %s, NOW()
                )
            """, (trial_uuid, lead_id, logged_user_id, logged_user_name, product_name, start_date, expiry_date_str, notes or None))

            update_fields = ["updated_at = NOW()", "is_disposed = 0", "disposed_by = NULL", "disposed_at = NULL"]
            update_params = []

            if lead_status is not None and str(lead_status).strip() != "":
                try:
                    st_val = int(lead_status)
                except Exception:
                    st_val = str(lead_status).strip()
                update_fields.append("lead_status = %s")
                update_params.append(st_val)

            if name is not None and str(name).strip() != "":
                update_fields.append("name = %s")
                update_params.append(str(name).strip())

            update_params.append(lead_id)
            cursor.execute(f"UPDATE leads SET {', '.join(update_fields)} WHERE id = %s", update_params)

            activity_uuid = f"ACT{uuid.uuid4().hex[:12].upper()}"
            act_comment = f"Started free trial for '{product_name}' from {start_date[:10]} to {expiry_date_obj.strftime('%d/%m/%Y')} (Skips weekends)"
            if notes:
                act_comment += f": {notes}"
            cursor.execute("""
                INSERT INTO lead_activities (
                    activity_uuid, lead_id, user_id, action_type, status_name, comment
                ) VALUES (%s, %s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), 'Free Trial Started', %s, %s)
            """, (activity_uuid, lead_id, logged_user_uuid, curr_status, act_comment))

            user_act_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
            user_desc = f"Activated free trial of {product_name} for lead {client_code} ({lead_name}) until {expiry_date_obj.strftime('%d/%m/%Y')}"
            cursor.execute("""
                INSERT INTO user_activities (
                    user_activity_uuid, user_id, lead_id, action_type, description, ip_address
                ) VALUES (%s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), %s, 'Add Free Trial', %s, %s)
            """, (user_act_uuid, logged_user_uuid, lead_id, user_desc, ip_address or None))

            connection.commit()

            return {
                "success": True,
                "message": f"Free trial for '{product_name}' started successfully until {expiry_date_obj.strftime('%d/%m/%Y')}.",
                "status_code": 200,
            }
    finally:
        connection.close()


def process_get_lead_details_for_so(logged_user_uuid, lead_uuid):
    """
    Fetches lead info (name, decrypted mobile, email, address) and active products list
    with plan prices for sales order form auto-population.
    """
    if not lead_uuid:
        return {"success": False, "message": "Lead identifier is required.", "status_code": 400}

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, lead_uuid, name, mobile_number, email, address, state, city, comment
                FROM leads
                WHERE lead_uuid = %s LIMIT 1
            """, (lead_uuid,))
            lead = cursor.fetchone()

            if not lead:
                return {"success": False, "message": "Lead not found.", "status_code": 444}

            user_settings = fetch_logged_user_settings(cursor, logged_user_uuid)
            from routes.settings_helpers import format_mobile_display
            from utils.product_helpers import get_plan_label
            raw_mobile = lead.get("mobile_number") or ""
            masked_mobile, decrypted_mobile = format_mobile_display(raw_mobile, user_settings)

            raw_name = str(lead.get("name") or "").strip()
            if not raw_name or raw_name.lower() in ("none", "no name", "none none", "null", "n/a", "na"):
                lead["name"] = ""
            else:
                lead["name"] = raw_name

            lead["decrypted_mobile"] = decrypted_mobile or raw_mobile
            lead["masked_mobile"] = masked_mobile or raw_mobile

            cursor.execute("""
                SELECT id, product_name, weekly, two_weekly, monthly, two_monthly, quarterly, six_monthly, nine_monthly, yearly, eighteen_monthly, twenty_four_monthly
                FROM products
                WHERE status = 1
                ORDER BY product_name ASC
            """)
            products = cursor.fetchall()
            for p in products:
                for k, v in p.items():
                    if k == "id" and v is not None:
                        p[k] = int(v)
                    elif hasattr(v, '__float__') and not isinstance(v, (int, bool)):
                        p[k] = float(v)

            cursor.execute("SELECT setting_key, setting_value FROM system_settings WHERE setting_key IN ('tax_percentage', 'product_expiry_mode')")
            settings_rows = cursor.fetchall()
            settings_dict = {s["setting_key"]: s["setting_value"] for s in settings_rows}

            tax_percentage = float(settings_dict.get("tax_percentage") or 18.0)
            product_expiry_mode = settings_dict.get("product_expiry_mode") or "auto"

            cursor.execute("""
                SELECT id, sales_order_uuid, order_number, invoice_name, email, address, state, city, gst_number,
                       pan_number, aadhaar_number, product_name, plan_name,
                       net_amount, tax_percentage, tax_amount, gross_amount, order_status,
                       payment_mode, reference_number, notes,
                       DATE_FORMAT(dob, '%%d/%%m/%%Y') AS dob,
                       DATE_FORMAT(dob, '%%Y-%%m-%%d') AS dob_iso,
                       DATE_FORMAT(created_at, '%%d/%%m/%%Y') AS created_date,
                       DATE_FORMAT(service_start_date, '%%d/%%m/%%Y') AS start_date,
                       DATE_FORMAT(service_expiry_date, '%%d/%%m/%%Y') AS expiry_date
                FROM sales_orders
                WHERE lead_id = %s
                ORDER BY id DESC
            """, (int(lead["id"]),))
            existing_orders = cursor.fetchall()
            has_pending_so = False
            pending_order_number = ""
            pending_so = None
            for o in existing_orders:
                for k in ["net_amount", "tax_amount", "gross_amount"]:
                    if o.get(k) is not None:
                        o[k] = float(o[k])
                if o.get("order_status") == "pending":
                    has_pending_so = True
                    if not pending_order_number:
                        pending_order_number = o.get("order_number") or ""
                        pending_so = o

            latest_so = existing_orders[0] if existing_orders else {}

            return {
                "success": True,
                "lead": lead,
                "products": products,
                "tax_percentage": tax_percentage,
                "product_expiry_mode": product_expiry_mode,
                "existing_orders": existing_orders,
                "has_pending_so": has_pending_so,
                "pending_order_number": pending_order_number,
                "pending_so": pending_so,
                "latest_so": latest_so,
                "status_code": 200,
            }
    finally:
        connection.close()


def process_add_sales_order(
    logged_user_uuid,
    lead_uuid,
    invoice_name,
    email=None,
    address=None,
    state=None,
    city=None,
    gst_number=None,
    pan_number=None,
    aadhaar_number=None,
    dob=None,
    product_id=None,
    plan_name=None,
    service_start_date=None,
    service_expiry_date=None,
    gross_amount=0.0,
    tax_percentage=18.0,
    tax_amount=0.0,
    net_amount=0.0,
    payment_mode=None,
    reference_number=None,
    payment_date=None,
    service_mode=None,
    notes=None,
    ip_address=None,
):
    """
    Submits a new Sales Order with initial order_status = 'pending' (pending approval).
    Inserts record into sales_orders, updates leads.has_so = 1, and logs activities.
    Blocks creation if a pending sales order already exists for the lead.
    """
    if not lead_uuid:
        return {"success": False, "message": "Lead identifier is required.", "status_code": 400}
    if not invoice_name or not str(invoice_name).strip():
        return {"success": False, "message": "Invoice name is required.", "status_code": 400}
    if not email or not str(email).strip():
        return {"success": False, "message": "Email address is required.", "status_code": 400}
    if not address or not str(address).strip():
        return {"success": False, "message": "Billing address is required.", "status_code": 400}
    if not product_id:
        return {"success": False, "message": "Product selection is required.", "status_code": 400}
    if not plan_name:
        return {"success": False, "message": "Plan selection is required.", "status_code": 400}

    try:
        gross_amount = float(gross_amount or 0.0)
        tax_percentage = float(tax_percentage or 0.0)
        tax_amount = float(tax_amount or 0.0)
        net_amount = float(net_amount or 0.0)
    except (ValueError, TypeError):
        pass

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Fetch authoritative tax percentage from system_settings
            cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'tax_percentage' LIMIT 1")
            tax_row = cursor.fetchone()
            tax_percentage = float(tax_row["setting_value"]) if (tax_row and tax_row.get("setting_value")) else 18.0

            if gross_amount > 0:
                net_amount = round(gross_amount / (1.0 + (tax_percentage / 100.0)), 2)
                tax_amount = round(gross_amount - net_amount, 2)

            cursor.execute("""
                SELECT id, lead_uuid, name, id AS client_code, lead_status
                FROM leads
                WHERE lead_uuid = %s LIMIT 1
            """, (lead_uuid,))
            lead = cursor.fetchone()

            if not lead:
                return {"success": False, "message": "Lead not found.", "status_code": 444}

            lead_id = lead["id"]

            cursor.execute("""
                SELECT id, order_number FROM sales_orders
                WHERE lead_id = %s AND order_status = 'pending'
                LIMIT 1
            """, (lead_id,))
            pending_so = cursor.fetchone()
            if pending_so:
                return {
                    "success": False,
                    "message": f"Sales Order '{pending_so['order_number']}' is already pending approval for this lead. A new sales order cannot be created until it is approved or rejected.",
                    "status_code": 400
                }

            client_code = f"LEAD{lead_id}"
            lead_name = lead.get("name") or "Lead"
            curr_status = lead.get("lead_status") or "No Status"

            # Clean input string values
            email = (email or "").strip().lower()
            gst_number = (gst_number or "").strip().upper()
            pan_number = (pan_number or "").strip().upper()
            clean_aadhaar = re.sub(r"\s+", "", (aadhaar_number or "").strip())
            dob = (dob or "").strip()

            # 1. Email Format & Duplicate Check across different leads
            if email:
                if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
                    return {"success": False, "message": "Invalid email address format.", "status_code": 400}
                
                cursor.execute("""
                    SELECT lead_id FROM sales_orders 
                    WHERE LOWER(email) = %s AND lead_id != %s LIMIT 1
                """, (email, lead_id))
                other_so_email = cursor.fetchone()
                if other_so_email:
                    return {"success": False, "message": f"Email '{email}' is already registered with another lead.", "status_code": 400}

                cursor.execute("""
                    SELECT id FROM leads 
                    WHERE LOWER(email) = %s AND id != %s LIMIT 1
                """, (email, lead_id))
                other_lead_email = cursor.fetchone()
                if other_lead_email:
                    return {"success": False, "message": f"Email '{email}' is already registered with another lead (Lead #{other_lead_email['id']}).", "status_code": 400}

            # 2. DOB Age Check (Customer must be 18+ years old & Required)
            clean_dob = None
            if dob:
                d_str = str(dob).strip()
                if re.match(r"^\d{4}-\d{2}-\d{2}$", d_str):
                    clean_dob = d_str
                else:
                    match_d = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", d_str)
                    if match_d:
                        dd, mm, yyyy = match_d.groups()
                        clean_dob = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
                if clean_dob:
                    try:
                        dob_date = datetime.datetime.strptime(clean_dob, "%Y-%m-%d").date()
                        today_date = datetime.date.today()
                        age = today_date.year - dob_date.year - ((today_date.month, today_date.day) < (dob_date.month, dob_date.day))
                        if age < 18:
                            return {"success": False, "message": f"Customer age is {age} years. Date of Birth must indicate customer is 18 years or older.", "status_code": 400}
                    except ValueError:
                        return {"success": False, "message": "Invalid Date of Birth format.", "status_code": 400}
                else:
                    return {"success": False, "message": "Invalid Date of Birth format. Expected DD/MM/YYYY.", "status_code": 400}
            else:
                return {"success": False, "message": "Date of Birth is required.", "status_code": 400}

            # 3. PAN Format & Duplicate Check across different leads
            if pan_number:
                if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", pan_number):
                    return {"success": False, "message": "Invalid PAN format. Must be 10 characters (e.g. ABCDE1234F).", "status_code": 400}

                cursor.execute("""
                    SELECT lead_id FROM sales_orders 
                    WHERE UPPER(pan_number) = %s AND lead_id != %s LIMIT 1
                """, (pan_number, lead_id))
                other_so_pan = cursor.fetchone()
                if other_so_pan:
                    return {"success": False, "message": f"PAN Card Number '{pan_number}' is already registered with another lead.", "status_code": 400}

            # 4. Aadhaar Format & Duplicate Check across different leads
            if clean_aadhaar:
                if not re.match(r"^\d{12}$", clean_aadhaar):
                    return {"success": False, "message": "Invalid Aadhaar format. Must be exactly 12 digits.", "status_code": 400}

                cursor.execute("""
                    SELECT lead_id FROM sales_orders 
                    WHERE REPLACE(aadhaar_number, ' ', '') = %s AND lead_id != %s LIMIT 1
                """, (clean_aadhaar, lead_id))
                other_so_aadhaar = cursor.fetchone()
                if other_so_aadhaar:
                    return {"success": False, "message": f"Aadhaar Number '{aadhaar_number}' is already registered with another lead.", "status_code": 400}

            # 5. GST Format & Duplicate Check across different leads
            if gst_number:
                cursor.execute("""
                    SELECT lead_id FROM sales_orders 
                    WHERE UPPER(gst_number) = %s AND lead_id != %s LIMIT 1
                """, (gst_number, lead_id))
                other_so_gst = cursor.fetchone()
                if other_so_gst:
                    return {"success": False, "message": f"GST Number '{gst_number}' is already registered with another lead.", "status_code": 400}

            # Clean and parse service_start_date and service_expiry_date to strict YYYY-MM-DD
            clean_start_date = None
            if service_start_date:
                try:
                    s_str = service_start_date.strip()
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", s_str):
                        clean_start_date = s_str
                    else:
                        match_d = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s_str)
                        if match_d:
                            dd, mm, yyyy = match_d.groups()
                            clean_start_date = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
                except Exception:
                    pass

            if not clean_start_date:
                clean_start_date = datetime.date.today().strftime("%Y-%m-%d")

            from utils.permissions import has_permission
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            if clean_start_date < today_str and not has_permission("payments", "back_date_sales_order"):
                return {"success": False, "message": "Access Denied: You do not have permission to create back-dated Sales Orders.", "status_code": 403}

            clean_expiry_date = None
            if service_expiry_date:
                try:
                    e_str = service_expiry_date.strip()
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", e_str):
                        clean_expiry_date = e_str
                    else:
                        match_e = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", e_str)
                        if match_e:
                            dd, mm, yyyy = match_e.groups()
                            clean_expiry_date = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
                except Exception:
                    pass

            if not clean_expiry_date:
                plan_days_map = {
                    'weekly': 7, 'two_weekly': 14, 'monthly': 30, 'two_monthly': 60,
                    'quarterly': 90, 'six_monthly': 180, 'nine_monthly': 270,
                    'yearly': 365, 'eighteen_monthly': 545, 'twenty_four_monthly': 730
                }
                days = plan_days_map.get(plan_name, 30)
                try:
                    s_dt = datetime.datetime.strptime(clean_start_date, "%Y-%m-%d").date()
                    clean_expiry_date = (s_dt + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
                except Exception:
                    clean_expiry_date = (datetime.date.today() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")

            product_name = f"Product #{product_id}"
            cursor.execute("SELECT product_name FROM products WHERE id = %s LIMIT 1", (product_id,))
            prod = cursor.fetchone()
            if prod and prod.get("product_name"):
                product_name = prod["product_name"]

            so_seq = uuid.uuid4().hex[:6].upper()
            order_number = f"SO{datetime.date.today().strftime('%Y%m%d')}{so_seq}"
            sales_order_uuid = f"SO{uuid.uuid4().hex[:12].upper()}"

            from utils.product_helpers import get_plan_label
            clean_plan_label = get_plan_label(plan_name) if plan_name else "N/A"
            raw_inv = str(invoice_name or "").strip()
            if not raw_inv or raw_inv.lower() in ("none", "no name", "none none", "null", "n/a", "na"):
                clean_invoice_name = ""
            else:
                clean_invoice_name = raw_inv

            clean_payment_date = None
            if payment_date:
                try:
                    p_str = str(payment_date).strip()
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", p_str):
                        clean_payment_date = p_str
                    else:
                        match_p = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", p_str)
                        if match_p:
                            dd, mm, yyyy = match_p.groups()
                            clean_payment_date = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
                except Exception:
                    pass
            if not clean_payment_date:
                clean_payment_date = datetime.date.today().strftime("%Y-%m-%d")

            if clean_payment_date < today_str and not has_permission("payments", "back_date_sales_order"):
                clean_payment_date = today_str

            clean_service_mode = str(service_mode or "").strip() or None

            clean_state = str(state or "").strip() or None
            clean_city = str(city or "").strip() or None
            clean_address = str(address or "").strip() or None

            cursor.execute("SELECT id, full_name FROM users WHERE user_uuid = %s LIMIT 1", (logged_user_uuid,))
            so_creator = cursor.fetchone()
            so_creator_id = so_creator["id"] if so_creator else None
            so_creator_name = so_creator["full_name"] if so_creator else "System"

            cursor.execute("""
                INSERT INTO sales_orders (
                    sales_order_uuid, lead_id, created_by_user_id, created_by_name, order_number, order_amount,
                    order_status, notes, invoice_name, email,
                    address, state, city, gst_number, pan_number, aadhaar_number, dob, product_name, plan_name, gross_amount,
                    tax_percentage, tax_amount, net_amount, service_start_date, service_expiry_date,
                    payment_mode, reference_number, payment_date, service_mode, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    'pending', %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, NOW()
                )
            """, (
                sales_order_uuid, lead_id, so_creator_id, so_creator_name, order_number, net_amount,
                notes or None, clean_invoice_name, email or None,
                clean_address, clean_state, clean_city, gst_number or None, pan_number or None, clean_aadhaar or None, clean_dob or None,
                product_name, clean_plan_label, gross_amount,
                tax_percentage, tax_amount, net_amount, clean_start_date, clean_expiry_date,
                payment_mode or None, reference_number or None, clean_payment_date, clean_service_mode
            ))

            cursor.execute("""
                UPDATE leads
                SET address = COALESCE(%s, address),
                    state = COALESCE(%s, state),
                    city = COALESCE(%s, city),
                    is_disposed = 0,
                    disposed_by = NULL,
                    disposed_at = NULL,
                    updated_at = NOW()
                WHERE id = %s
            """, (clean_address, clean_state, clean_city, lead_id))

            activity_uuid = f"ACT{uuid.uuid4().hex[:12].upper()}"
            act_comment = f"Created Pending Sales Order '{order_number}' for {product_name} ({plan_name}) - Total: ₹{net_amount:,.2f}"
            if notes:
                act_comment += f": {notes}"
            cursor.execute("""
                INSERT INTO lead_activities (
                    activity_uuid, lead_id, user_id, action_type, status_name, comment
                ) VALUES (%s, %s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), 'Sales Order Created', %s, %s)
            """, (activity_uuid, lead_id, logged_user_uuid, curr_status, act_comment))

            user_act_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
            user_desc = f"Submitted Pending Sales Order {order_number} for lead {client_code} ({lead_name}) - Amount: ₹{net_amount:,.2f}"
            cursor.execute("""
                INSERT INTO user_activities (
                    user_activity_uuid, user_id, lead_id, action_type, description, ip_address
                ) VALUES (%s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), %s, 'Create Sales Order', %s, %s)
            """, (user_act_uuid, logged_user_uuid, lead_id, user_desc, ip_address or None))

            connection.commit()

            return {
                "success": True,
                "message": f"Sales Order '{order_number}' submitted successfully in PENDING status for approval.",
                "status_code": 200,
            }
    finally:
        connection.close()


def process_update_sales_order(
    logged_user_uuid,
    sales_order_uuid,
    invoice_name=None,
    email=None,
    address=None,
    state=None,
    city=None,
    gst_number=None,
    pan_number=None,
    aadhaar_number=None,
    dob=None,
    product_id=None,
    product_name=None,
    plan_name=None,
    gross_amount=None,
    tax_percentage=18.0,
    service_start_date=None,
    service_expiry_date=None,
    service_mode=None,
    payment_mode=None,
    payment_date=None,
    reference_number=None,
    notes=None,
    order_status=None,
    kyc_status=None,
):
    if not sales_order_uuid:
        return {"success": False, "message": "Sales order UUID is required.", "status_code": 400}

    clean_plan = plan_name.strip() if plan_name else None
    clean_state = str(state or "").strip() or None
    clean_city = str(city or "").strip() or None
    clean_address = str(address or "").strip() or None

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, order_status, lead_id FROM sales_orders
                WHERE sales_order_uuid = %s LIMIT 1
            """, (sales_order_uuid,))
            so = cursor.fetchone()
            if not so:
                return {"success": False, "message": "Sales order not found.", "status_code": 404}

            lead_id = so["lead_id"]
            clean_aadhaar = re.sub(r"\s+", "", (aadhaar_number or "").strip()) if aadhaar_number else None

            # Duplicate checks for Email, PAN, Aadhaar, GST across other leads
            if email:
                cursor.execute("""
                    SELECT lead_id FROM sales_orders
                    WHERE LOWER(email) = %s AND lead_id != %s AND sales_order_uuid != %s LIMIT 1
                """, (email.lower(), lead_id, sales_order_uuid))
                if cursor.fetchone():
                    return {"success": False, "message": f"Email '{email}' is already registered with another lead.", "status_code": 400}

            if pan_number:
                cursor.execute("""
                    SELECT lead_id FROM sales_orders
                    WHERE UPPER(pan_number) = %s AND lead_id != %s AND sales_order_uuid != %s LIMIT 1
                """, (pan_number.upper(), lead_id, sales_order_uuid))
                if cursor.fetchone():
                    return {"success": False, "message": f"PAN Card '{pan_number}' is already registered with another lead.", "status_code": 400}

            if clean_aadhaar:
                cursor.execute("""
                    SELECT lead_id FROM sales_orders
                    WHERE REPLACE(aadhaar_number, ' ', '') = %s AND lead_id != %s AND sales_order_uuid != %s LIMIT 1
                """, (clean_aadhaar, lead_id, sales_order_uuid))
                if cursor.fetchone():
                    return {"success": False, "message": f"Aadhaar Number '{aadhaar_number}' is already registered with another lead.", "status_code": 400}

            if gst_number:
                cursor.execute("""
                    SELECT lead_id FROM sales_orders
                    WHERE UPPER(gst_number) = %s AND lead_id != %s AND sales_order_uuid != %s LIMIT 1
                """, (gst_number.upper(), lead_id, sales_order_uuid))
                if cursor.fetchone():
                    return {"success": False, "message": f"GST Number '{gst_number}' is already registered with another lead.", "status_code": 400}

            if not product_name and product_id:
                cursor.execute("SELECT product_name FROM products WHERE id = %s LIMIT 1", (product_id,))
                prod = cursor.fetchone()
                if prod:
                    product_name = prod["product_name"]

            net_amt = None
            tax_amt = None
            try:
                if gross_amount is not None and float(gross_amount) > 0:
                    g_val = float(gross_amount)
                    tax_rate = float(tax_percentage or 18.0)
                    net_amt = round(g_val / (1 + (tax_rate / 100)), 2)
                    tax_amt = round(g_val - net_amt, 2)
            except Exception:
                pass
            clean_start = None
            if service_start_date:
                s_str = str(service_start_date).strip()
                if re.match(r"^\d{4}-\d{2}-\d{2}$", s_str):
                    clean_start = s_str
                else:
                    match_s = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", s_str)
                    if match_s:
                        dd, mm, yyyy = match_s.groups()
                        clean_start = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"

            from utils.permissions import has_permission
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            if clean_start and clean_start < today_str and not has_permission("payments", "back_date_sales_order"):
                return {"success": False, "message": "Access Denied: You do not have permission to select a back-date for Sales Orders.", "status_code": 403}

            if order_status and str(order_status).lower() == "approved" and not has_permission("payments", "so_approve"):
                return {"success": False, "message": "Access Denied: You do not have permission to approve Sales Orders.", "status_code": 403}

            clean_exp = None
            if service_expiry_date:
                e_str = str(service_expiry_date).strip()
                if re.match(r"^\d{4}-\d{2}-\d{2}$", e_str):
                    clean_exp = e_str
                else:
                    match_e = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", e_str)
                    if match_e:
                        dd, mm, yyyy = match_e.groups()
                        clean_exp = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"

            clean_payment_date = None
            if payment_date:
                p_str = str(payment_date).strip()
                if re.match(r"^\d{4}-\d{2}-\d{2}$", p_str):
                    clean_payment_date = p_str
                else:
                    match_p = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", p_str)
                    if match_p:
                        dd, mm, yyyy = match_p.groups()
                        clean_payment_date = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"

            clean_dob = None
            if dob:
                d_str = str(dob).strip()
                if re.match(r"^\d{4}-\d{2}-\d{2}$", d_str):
                    clean_dob = d_str
                else:
                    match_d = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", d_str)
                    if match_d:
                        dd, mm, yyyy = match_d.groups()
                        clean_dob = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"

            cursor.execute("""
                UPDATE sales_orders
                SET invoice_name = COALESCE(%s, invoice_name),
                    email = COALESCE(%s, email),
                    address = COALESCE(%s, address),
                    state = COALESCE(%s, state),
                    city = COALESCE(%s, city),
                    gst_number = COALESCE(%s, gst_number),
                    pan_number = COALESCE(%s, pan_number),
                    aadhaar_number = COALESCE(%s, aadhaar_number),
                    dob = COALESCE(%s, dob),
                    product_name = COALESCE(%s, product_name),
                    plan_name = COALESCE(%s, plan_name),
                    gross_amount = COALESCE(%s, gross_amount),
                    order_amount = COALESCE(%s, order_amount),
                    net_amount = COALESCE(%s, net_amount),
                    tax_amount = COALESCE(%s, tax_amount),
                    service_start_date = COALESCE(%s, service_start_date),
                    service_expiry_date = COALESCE(%s, service_expiry_date),
                    service_mode = COALESCE(%s, service_mode),
                    payment_mode = COALESCE(%s, payment_mode),
                    payment_date = COALESCE(%s, payment_date),
                    reference_number = COALESCE(%s, reference_number),
                    notes = COALESCE(%s, notes),
                    order_status = COALESCE(%s, order_status),
                    approved_by_user_id = CASE WHEN LOWER(COALESCE(%s, '')) = 'approved' THEN (SELECT id FROM users WHERE user_uuid = %s LIMIT 1) ELSE approved_by_user_id END,
                    approved_at = CASE WHEN LOWER(COALESCE(%s, '')) = 'approved' THEN NOW() ELSE approved_at END,
                    kyc_status = COALESCE(%s, kyc_status),
                    updated_at = NOW()
                WHERE sales_order_uuid = %s
            """, (
                invoice_name or None, email or None, clean_address, clean_state, clean_city, gst_number or None, pan_number or None,
                clean_aadhaar or None, clean_dob or None, product_name or None, clean_plan or None,
                gross_amount or None, gross_amount or None, net_amt or None, tax_amt or None,
                clean_start or None, clean_exp or None, service_mode or None, payment_mode or None, clean_payment_date or None, reference_number or None, notes or None,
                order_status or None, order_status or None, logged_user_uuid, order_status or None, kyc_status or None,
                sales_order_uuid
            ))

            is_approved = bool(order_status and str(order_status).strip().lower() == "approved")
            if is_approved:
                cursor.execute("""
                    UPDATE leads
                    SET address = COALESCE(%s, address),
                        state = COALESCE(%s, state),
                        city = COALESCE(%s, city),
                        is_disposed = 0,
                        disposed_by = NULL,
                        disposed_at = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                """, (clean_address, clean_state, clean_city, lead_id))
            else:
                cursor.execute("""
                    UPDATE leads
                    SET address = COALESCE(%s, address),
                        state = COALESCE(%s, state),
                        city = COALESCE(%s, city),
                        updated_at = NOW()
                    WHERE id = %s
                """, (clean_address, clean_state, clean_city, lead_id))
            
            # Sync to clients table if approved
            sync_approved_sales_order_to_clients(cursor, sales_order_uuid)

            connection.commit()
            return {"success": True, "message": "Sales order updated successfully.", "status_code": 200}
    finally:
        connection.close()


def sync_approved_sales_order_to_clients(cursor, sales_order_identifier):
    """
    Syncs an approved Sales Order into the `clients` table.
    Ensures duplicate entries for the SAME Sales Order are never created.
    """
    if not sales_order_identifier:
        return

    cursor.execute("""
        SELECT so.*, l.name AS lead_name, l.mobile_number, l.email AS lead_email, l.address AS lead_address
        FROM sales_orders so
        JOIN leads l ON l.id = so.lead_id
        WHERE (so.sales_order_uuid = %s OR so.id = %s) AND (LOWER(so.order_status) = 'approved')
        LIMIT 1
    """, (sales_order_identifier, sales_order_identifier))
    so = cursor.fetchone()
    if not so:
        return

    so_id = so["id"]
    so_uuid = so["sales_order_uuid"]
    lead_id = so["lead_id"]

    # Ensure lead is active (is_disposed = 0) whenever Sales Order is approved
    cursor.execute("""
        UPDATE leads
        SET is_disposed = 0,
            disposed_by = NULL,
            disposed_at = NULL,
            updated_at = NOW()
        WHERE id = %s
    """, (lead_id,))

    cursor.execute("""
        SELECT id FROM clients WHERE sales_order_uuid = %s OR sales_order_id = %s LIMIT 1
    """, (so_uuid, so_id))
    existing_client = cursor.fetchone()

    total_amount = float(so.get("net_amount") or so.get("order_amount") or 0.0)
    tax_amount = float(so.get("tax_amount") or 0.0)
    grand_total = float(so.get("gross_amount") or (total_amount + tax_amount))

    if existing_client:
        cursor.execute("""
            UPDATE clients
            SET client_name = %s,
                email = %s,
                mobile_number = %s,
                address = %s,
                state = %s,
                city = %s,
                product_name = %s,
                plan_name = %s,
                service_start_date = %s,
                service_expiry_date = %s,
                total_amount = %s,
                tax_amount = %s,
                grand_total = %s,
                so_status = %s,
                client_status = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (
            so.get("invoice_name") or so.get("lead_name"),
            so.get("email") or so.get("lead_email"),
            so.get("mobile_number"),
            so.get("address") or so.get("lead_address"),
            so.get("state"),
            so.get("city"),
            so.get("product_name"),
            so.get("plan_name"),
            so.get("service_start_date"),
            so.get("service_expiry_date"),
            total_amount,
            tax_amount,
            grand_total,
            so.get("order_status") or "approved",
            "active",
            existing_client["id"]
        ))
    else:
        cursor.execute("""
            SELECT client_code FROM clients WHERE lead_id = %s LIMIT 1
        """, (lead_id,))
        lead_client_row = cursor.fetchone()
        client_code = lead_client_row["client_code"] if lead_client_row else f"{lead_id}"

        cursor.execute("""
            INSERT INTO clients (
                client_uuid, lead_id, sales_order_id, sales_order_uuid, created_by_user_id, created_by_name,
                client_code, client_name, mobile_number, email, address, state, city, product_name, plan_name,
                service_start_date, service_expiry_date, total_amount, tax_amount, grand_total,
                so_status, client_status, created_at, updated_at
            ) VALUES (
                CONCAT('CLI', UPPER(SUBSTRING(MD5(RAND()), 1, 12))),
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, NOW(), NOW()
            )
        """, (
            lead_id, so_id, so_uuid, so.get("created_by_user_id") or 1, so.get("created_by_name") or "",
            client_code,
            so.get("invoice_name") or so.get("lead_name"),
            so.get("mobile_number"),
            so.get("email") or so.get("lead_email"),
            so.get("address") or so.get("lead_address"),
            so.get("state"),
            so.get("city"),
            so.get("product_name"),
            so.get("plan_name"),
            so.get("service_start_date"),
            so.get("service_expiry_date"),
            total_amount,
            tax_amount,
            grand_total,
            so.get("order_status") or "approved",
            "active"
        ))



def process_check_field_duplicate(lead_uuid, field_name, field_value):
    """
    Real-time AJAX duplicate check for email, pan_number, aadhaar_number, and gst_number.
    Allows re-use for the SAME lead_uuid, but returns is_duplicate=True for DIFFERENT leads.
    """
    if not field_name or not field_value:
        return {"is_duplicate": False, "message": ""}

    field_value = str(field_value).strip()
    if not field_value:
        return {"is_duplicate": False, "message": ""}

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM leads WHERE lead_uuid = %s LIMIT 1", (lead_uuid,))
            lead = cursor.fetchone()
            current_lead_id = lead["id"] if lead else 0

            if field_name == "mobile_number":
                val = field_value.strip()
                enc_val = encrypt_mobile(val)
                cursor.execute("""
                    SELECT id FROM leads
                    WHERE (mobile_number = %s OR (mobile_number = %s AND %s IS NOT NULL)) AND id != %s LIMIT 1
                """, (val, enc_val, enc_val, current_lead_id))
                other_lead = cursor.fetchone()
                if other_lead:
                    return {"is_duplicate": True, "message": f"Mobile Number '{field_value}' is already registered with another lead (Lead #{other_lead['id']})."}

            elif field_name == "email":
                val = field_value.lower()
                cursor.execute("""
                    SELECT lead_id FROM sales_orders
                    WHERE LOWER(email) = %s AND lead_id != %s LIMIT 1
                """, (val, current_lead_id))
                if cursor.fetchone():
                    return {"is_duplicate": True, "message": f"Email '{field_value}' is already registered with another lead."}

                cursor.execute("""
                    SELECT id FROM leads
                    WHERE LOWER(email) = %s AND id != %s LIMIT 1
                """, (val, current_lead_id))
                other_lead = cursor.fetchone()
                if other_lead:
                    return {"is_duplicate": True, "message": f"Email '{field_value}' is already registered with another lead (Lead #{other_lead['id']})."}

            elif field_name == "pan_number":
                val = field_value.upper()
                cursor.execute("""
                    SELECT lead_id FROM sales_orders
                    WHERE UPPER(pan_number) = %s AND lead_id != %s LIMIT 1
                """, (val, current_lead_id))
                if cursor.fetchone():
                    return {"is_duplicate": True, "message": f"PAN Card '{field_value}' is already registered with another lead."}

            elif field_name == "aadhaar_number":
                clean_aadhaar = re.sub(r"\s+", "", field_value)
                if clean_aadhaar:
                    cursor.execute("""
                        SELECT lead_id FROM sales_orders
                        WHERE REPLACE(aadhaar_number, ' ', '') = %s AND lead_id != %s LIMIT 1
                    """, (clean_aadhaar, current_lead_id))
                    if cursor.fetchone():
                        return {"is_duplicate": True, "message": f"Aadhaar Number '{field_value}' is already registered with another lead."}

            elif field_name == "gst_number":
                val = field_value.upper()
                cursor.execute("""
                    SELECT lead_id FROM sales_orders
                    WHERE UPPER(gst_number) = %s AND lead_id != %s LIMIT 1
                """, (val, current_lead_id))
                if cursor.fetchone():
                    return {"is_duplicate": True, "message": f"GST Number '{field_value}' is already registered with another lead."}

            return {"is_duplicate": False, "message": "Available"}
    except Exception as e:
        return {"is_duplicate": False, "message": str(e)}
    finally:
        connection.close()


def process_get_sales_order_for_edit(logged_user_uuid, sales_order_uuid):
    if not sales_order_uuid:
        return {"success": False, "message": "Sales order UUID is required.", "status_code": 400}

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT so.id, so.sales_order_uuid, so.order_number, so.lead_id,
                       COALESCE(so.invoice_name, '') AS invoice_name,
                       COALESCE(so.email, '') AS email,
                       COALESCE(so.address, '') AS address,
                       COALESCE(so.state, '') AS state,
                       COALESCE(so.city, '') AS city,
                       COALESCE(so.gst_number, '') AS gst_number,
                       COALESCE(so.pan_number, '') AS pan_number,
                       COALESCE(so.aadhaar_number, '') AS aadhaar_number,
                       COALESCE(so.product_name, 'N/A') AS product_name,
                       COALESCE(so.plan_name, 'N/A') AS plan_name,
                       COALESCE(so.gross_amount, 0.0) AS gross_amount,
                       COALESCE(so.order_amount, 0.0) AS order_amount,
                       COALESCE(so.tax_percentage, 18.0) AS tax_percentage,
                       COALESCE(so.tax_amount, 0.0) AS tax_amount,
                       COALESCE(so.net_amount, 0.0) AS net_amount,
                       COALESCE(so.order_status, 'pending') AS order_status,
                       COALESCE(so.kyc_status, 'Pending') AS kyc_status,
                       COALESCE(so.payment_mode, '') AS payment_mode,
                       COALESCE(so.service_mode, 'App & Web') AS service_mode,
                       COALESCE(so.reference_number, '') AS reference_number,
                       COALESCE(so.notes, '') AS notes,
                       DATE_FORMAT(so.dob, '%%d/%%m/%%Y') AS dob,
                       DATE_FORMAT(so.service_start_date, '%%d/%%m/%%Y') AS service_start_date,
                       DATE_FORMAT(so.service_expiry_date, '%%d/%%m/%%Y') AS service_expiry_date,
                       COALESCE(DATE_FORMAT(so.payment_date, '%%d/%%m/%%Y'), DATE_FORMAT(so.created_at, '%%d/%%m/%%Y')) AS payment_date
                FROM sales_orders so
                WHERE so.sales_order_uuid = %s LIMIT 1
            """, (sales_order_uuid,))
            so = cursor.fetchone()
            if not so:
                return {"success": False, "message": "Sales order not found.", "status_code": 404}

            for k in ["gross_amount", "order_amount", "tax_percentage", "tax_amount", "net_amount"]:
                if so.get(k) is not None:
                    so[k] = float(so[k])

            cursor.execute("""
                SELECT id, name, mobile_number, email, address, state, city
                FROM leads WHERE id = %s LIMIT 1
            """, (so["lead_id"],))
            lead = cursor.fetchone() or {}
            if lead:
                lead["client_code"] = f"{lead['id']}"

            cursor.execute("""
                SELECT id, product_name, weekly, two_weekly, monthly, two_monthly, quarterly,
                       six_monthly, nine_monthly, yearly, eighteen_monthly, twenty_four_monthly
                FROM products WHERE status = 1 ORDER BY product_name ASC
            """)
            products = cursor.fetchall() or []
            for p in products:
                for k, v in p.items():
                    if k == "id" and v is not None:
                        p[k] = int(v)
                    elif hasattr(v, '__float__') and not isinstance(v, (int, bool)):
                        p[k] = float(v)

            return {
                "success": True,
                "sales_order": so,
                "lead": lead,
                "products": products,
                "status_code": 200,
            }
    finally:
        connection.close()




