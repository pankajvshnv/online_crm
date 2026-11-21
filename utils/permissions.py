import json
from functools import wraps
from flask import session, g, redirect, url_for, flash, request, jsonify
from config import get_db_connection


UNIVERSAL_SECURITY_RULES = [
    # 1. Settings Sub-Categories (Prefix matching)
    ("/settings/user/", ("settings", "user_management")),
    ("/settings/lead/", ("settings", "lead_management")),
    ("/settings/calling/", ("settings", "calling_management")),
    ("/settings/system/", ("settings", "system_controls")),
    ("/settings", ("settings", "view")),

    # 2. Operations / Reports Sub-Pages
    ("/reports/user-report", ("reports", "user_report")),
    ("/reports/lead-report", ("reports", "lead_report")),
    ("/reports/sales-report", ("reports", "sales_report")),
    ("/reports/sales", ("reports", "sales_report")),
    ("/reports/employee-report", ("reports", "employee_report")),
    ("/operations/lead-monitor", ("operations", "lead_monitor")),
    ("/operations/upload-leads", ("operations", "upload_leads")),
    ("/operations/paste-leads", ("operations", "paste_leads")),
    ("/operations/free-trials-operation", ("operations", "free_trials_operation")),
    ("/operations/followups-operation", ("operations", "followups_operation")),
    ("/operations/client-operation", ("operations", "client_operation")),
    ("/operations/contact-operation", ("operations", "contact_operation")),
    ("/operations", ("operations", "view")),

    # 3. Main Application Modules
    ("/leads/add", ("leads", "add")),
    ("/leads/edit", ("leads", "edit")),
    ("/leads/delete", ("leads", "delete")),
    ("/leads/export", ("leads", "export")),
    ("/leads/transfer", ("leads", "transfer")),
    ("/leads/dispose", ("leads", "dispose")),
    ("/leads", ("leads", "view")),

    ("/followups", ("followups", "view")),
    ("/free-trials", ("free_trials", "view")),
    ("/sales-orders", ("payments", "view")),
    ("/payments", ("payments", "view")),
    ("/clients", ("clients", "view")),
    ("/contacts", ("contacts", "view")),
    ("/email/compose", ("email", "send")),
    ("/email", ("email", "view")),
    ("/whatsapp", ("whatsapp", "view")),
    ("/chat", ("chat", "view")),
    ("/research", ("research", "view")),
    ("/handbook", ("handbook", "view")),
    ("/calldesk/summary", ("call_summary", "view")),
    ("/calldesk/history", ("call_history", "view")),
    ("/reports", ("reports", "view")),
]


def set_user_session(user_uuid):
    """
    Queries the DB ONCE (e.g. at login time or after profile update) to store 
    user details and permissions into Flask's session object.
    """
    session["user_uuid"] = user_uuid
    conn = get_db_connection()
    if not conn:
        print("[WARNING] set_user_session: Could not connect to database")
        return {}
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    u.id AS user_id,
                    u.user_uuid,
                    u.full_name,
                    u.username,
                    u.mobile,
                    u.is_admin,
                    u.role_id,
                    u.designation_id,
                    u.reporting_to_user_id,
                    r.role_name,
                    d.designation_name,
                    manager.full_name AS reporting_to_name,
                    manager.user_uuid AS reporting_to_uuid,
                    r.permissions
                FROM users u
                LEFT JOIN roles r ON r.id = u.role_id
                LEFT JOIN designations d ON d.id = u.designation_id
                LEFT JOIN users manager ON manager.id = u.reporting_to_user_id
                WHERE u.user_uuid = %s
            """, (user_uuid,))
            row = cursor.fetchone()
            
            if row:
                perms = {}
                if row.get("permissions"):
                    try:
                        if isinstance(row["permissions"], str):
                            perms = json.loads(row["permissions"])
                        else:
                            perms = row["permissions"]
                    except Exception:
                        perms = {}
                
                # Save into Flask session
                session["permissions"] = perms
                session["user"] = {
                    "id": row["user_id"],
                    "user_uuid": row["user_uuid"],
                    "full_name": row["full_name"],
                    "username": row["username"],
                    "mobile": row["mobile"],
                    "is_admin": int(row.get("is_admin") or 0),
                    "role_id": row["role_id"],
                    "role_name": row.get("role_name") or "N/A",
                    "designation_id": row["designation_id"],
                    "designation_name": row.get("designation_name") or "N/A",
                    "reporting_to_user_id": row["reporting_to_user_id"],
                    "reporting_to_name": row.get("reporting_to_name") or "N/A",
                    "reporting_to_uuid": row.get("reporting_to_uuid") or "N/A"
                }
                return perms
    except Exception as e:
        print(f"Error initializing user session: {e}")
    finally:
        if conn:
            conn.close()
    return {}


import time
from datetime import datetime


def update_user_last_active(user_id=None):
    """
    Throttled user presence tracker: Updates users.last_active_at in DB at most once every 30s.
    """
    if not user_id:
        user_info = session.get("user") or {}
        user_id = user_info.get("id")
    if not user_id:
        return

    now_ts = time.time()
    last_update_ts = session.get("_last_active_db_ts", 0)

    # Throttling: Update DB at most once every 15 seconds
    if now_ts - last_update_ts >= 15:
        session["_last_active_db_ts"] = now_ts
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE users 
                        SET last_active_at = NOW(), live_status = 'online' 
                        WHERE id = %s
                    """, (user_id,))
                    cursor.execute("""
                        UPDATE users
                        SET live_status = CASE
                            WHEN last_active_at IS NULL THEN 'offline'
                            WHEN TIMESTAMPDIFF(SECOND, last_active_at, NOW()) <= 120 THEN 'online'
                            WHEN TIMESTAMPDIFF(SECOND, last_active_at, NOW()) <= 600 THEN 'idle'
                            ELSE 'offline'
                        END
                    """)
                    conn.commit()
            except Exception as e:
                pass
            finally:
                conn.close()


def calculate_presence_status(last_active_at):
    """
    Calculates user presence status (online, idle, offline) from last_active_at timestamp.
    - Online: <= 2 minutes -> Green (bg-success)
    - Idle: 2 to 10 minutes -> Yellow (bg-warning)
    - Offline: > 10 minutes or NULL -> Red (bg-danger)
    """
    if not last_active_at:
        return {
            "status": "offline",
            "dot_class": "bg-danger",
            "badge_class": "bg-danger-subtle text-danger border border-danger-subtle",
            "label": "Offline",
            "order": 3
        }

    now = datetime.now()
    if isinstance(last_active_at, str):
        try:
            last_active_at = datetime.strptime(last_active_at[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return {
                "status": "offline",
                "dot_class": "bg-danger",
                "badge_class": "bg-danger-subtle text-danger border border-danger-subtle",
                "label": "Offline",
                "order": 3
            }

    diff_seconds = (now - last_active_at).total_seconds()
    if diff_seconds < 0:
        diff_seconds = 0

    if diff_seconds <= 120:  # <= 2 minutes
        return {
            "status": "online",
            "dot_class": "bg-success",
            "badge_class": "bg-success-subtle text-success border border-success-subtle",
            "label": "Online",
            "order": 1
        }
    elif diff_seconds <= 600:  # 2 to 10 minutes
        mins = max(2, int(diff_seconds // 60))
        return {
            "status": "idle",
            "dot_class": "bg-warning",
            "badge_class": "bg-warning-subtle text-dark border border-warning-subtle",
            "label": f"Away ({mins}m ago)",
            "order": 2
        }
    else:
        return {
            "status": "offline",
            "dot_class": "bg-danger",
            "badge_class": "bg-danger-subtle text-danger border border-danger-subtle",
            "label": "Offline",
            "order": 3
        }


def load_user_permissions():
    """
    Loads user details and permissions from the database into Flask's session and `g.permissions`.
    Fetches fresh data so role updates in UI take effect INSTANTLY without logging out.
    """
    if "user_uuid" not in session:
        g.permissions = {}
        session.pop("permissions", None)
        session.pop("user", None)
        return

    # Always sync fresh permissions from DB (takes < 0.5ms)
    set_user_session(session["user_uuid"])
    g.permissions = session.get("permissions", {})
    update_user_last_active()


def has_permission(module_key, action_key):
    """
    Check if the current user has the specified action for the given module.
    """
    # 1. Super Admin / Admin Bypass: If user is_admin == 1 or Admin role or ID 1/20, bypass all permission checks!
    user_info = session.get("user", {})
    role_name = str(user_info.get("role_name") or "").lower()
    user_id = user_info.get("id")
    if user_info.get("is_admin") == 1 or role_name in ["admin", "super admin", "superadmin"] or user_id in [1, 20]:
        return True

    # 2. Dashboard is always accessible to all logged-in users
    if module_key == "dashboard":
        return True

    perms = getattr(g, "permissions", None)
    if perms is None or not perms:
        perms = session.get("permissions", {})

    if not perms:
        return False
        
    module_perms = perms.get(module_key, [])
    
    # 1. Master Toggle (Parent Menu Check):
    if module_key != "global_access_scope" and "view" not in module_perms:
        return False
            
    # 2. Sub-Feature Check:
    if action_key in module_perms:
        return True
    if module_key == "email" and action_key in ["compose", "send"]:
        return "send" in module_perms or "compose" in module_perms
    return False


def require_permission(module_key, action_key):
    """
    Decorator to protect Flask routes based on role permissions.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not has_permission(module_key, action_key):
                if request.path.startswith("/api/") or request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": False, "message": f"Access Denied: You do not have '{action_key}' permission for {module_key}."}), 403
                else:
                    flash(f"Access Denied: You do not have permission to access this page.", "danger")
                    return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_user_team_users(cursor, user_id):
    """
    Returns list of user dicts (id, full_name, username) in team of user_id (self + all reportees recursively).
    """
    if not user_id:
        return []
    team_ids = {user_id}
    to_process = [user_id]
    
    while to_process:
        curr = to_process.pop(0)
        cursor.execute("SELECT id FROM users WHERE reporting_to_user_id = %s AND status = 1", (curr,))
        reportees = cursor.fetchall()
        for r in reportees:
            r_id = r["id"]
            if r_id not in team_ids:
                team_ids.add(r_id)
                to_process.append(r_id)
                
    team_ids_str = ",".join(map(str, team_ids))
    cursor.execute(f"SELECT id, full_name, username FROM users WHERE id IN ({team_ids_str}) AND status = 1 ORDER BY full_name ASC")
    return cursor.fetchall()


def get_assignable_users(cursor, user_id):
    """
    Universal reusable helper to fetch assignable users based on Global Data Access permission:
    - If user has Global Data Access permission (or is_admin=1): returns ALL active CRM users.
    - Otherwise: returns ONLY team users (self + reportees).
    """
    if has_permission('global_access_scope', 'global_data_access'):
        cursor.execute("SELECT id, full_name, username FROM users WHERE status = 1 ORDER BY full_name ASC")
        return cursor.fetchall()
    return get_user_team_users(cursor, user_id)


def get_assignable_user_ids(cursor, user_id):
    """
    Returns set of allowed user IDs (int) for data filtering queries.
    """
    users = get_assignable_users(cursor, user_id)
    return {u["id"] for u in users}
