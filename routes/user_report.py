from functools import wraps
from flask import render_template, session, jsonify, request, flash, redirect, url_for
from config import get_db_connection
from utils.permissions import require_permission, has_permission
from routes.lead_action import get_action_permissions, get_current_user
from routes.settings_helpers import decrypt_mobile
from routes.lead.all_leads_actions import process_assign_leads, process_delete_lead
from routes.lead_upload_common import csv_response
import uuid
import re


def require_user_report_permission(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_info = session.get("user", {})
        role_name = str(user_info.get("role_name") or "").lower()
        if user_info.get("is_admin") == 1 or role_name in ["admin", "super admin", "superadmin"] or user_info.get("id") in [1, 20]:
            return f(*args, **kwargs)
        if not (has_permission("reports", "user_report") or has_permission("operations", "lead_monitor")):
            if request.path.startswith("/api/") or request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "message": "Access Denied: You do not have permission for User Report."}), 403
            flash("Access Denied: You do not have permission to access User Report.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function


def user_report_routes(app):
    @app.route("/reports/user-report", endpoint="user_report")
    @app.route("/leads/user-report", endpoint="leads_user_report")
    @app.route("/leads/lead-operation", endpoint="lead_monitor")
    @require_user_report_permission
    def user_report():
        """
        Instant page load: returns page shell immediately with skeleton loader.
        Data is fetched asynchronously via AJAX.
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, user_uuid, full_name, username 
                    FROM users 
                    WHERE status = 1 
                    ORDER BY full_name ASC
                """)
                active_users = cursor.fetchall() or []

                cursor.execute("""
                    SELECT id, source_name 
                    FROM lead_sources 
                    ORDER BY source_name ASC
                """)
                lead_sources = cursor.fetchall() or []

                cursor.execute("""
                    SELECT id, batch_uuid, batch_name 
                    FROM lead_batches 
                    ORDER BY id DESC
                """)
                lead_batches = cursor.fetchall() or []
        finally:
            conn.close()

        user_info = session.get("user", {})
        user_role = str(session.get("role_name") or "")
        is_admin = user_info.get("is_admin") == 1 or user_role.lower() in ("admin", "super admin", "superadmin") or user_info.get("id") in [1, 20]
        can_assign = has_permission("leads", "assign_leads") or is_admin
        can_delete = has_permission("leads", "delete_leads") or is_admin
        can_export = has_permission("global_access_scope", "global_data_export") or is_admin or has_permission("reports", "user_report")

        return render_template(
            "reports/user_report.html",
            active_users=active_users,
            lead_sources=lead_sources,
            lead_batches=lead_batches,
            can_assign=can_assign,
            can_delete=can_delete,
            can_export=can_export,
            active_group="reports",
            active_page="user_report",
            page_title="User Report",
        )

    @app.route("/api/user-report/users")
    @app.route("/api/lead-operations/users")
    @require_user_report_permission
    def api_user_report_users():
        """
        Fetches all users (active and inactive) with comprehensive breakdown metrics:
        - Leads (total_assigned, active_leads, disposed_leads)
        - Follow-ups (followup_count)
        - Free Trials (trial_count)
        - Sales Orders (so_count)
        - Paid Clients (paid_client_count)
        Also aggregates:
        - Unassigned Leads
        - Disabled User Data
        - Deleted User Data
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                batch_id = (request.args.get("batch_id") or "all").strip()
                source_id = (request.args.get("source_id") or "all").strip()

                lead_where = ["1=1"]
                lead_params = []
                lead_join = ""

                if batch_id and batch_id != "all":
                    lead_where.append("(l.lead_batch_id = %s OR CAST(l.lead_batch_id AS CHAR) = %s)")
                    lead_params.extend([batch_id, batch_id])

                if source_id and source_id != "all":
                    lead_join = "LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_uuid = l.lead_source OR ls.source_name = l.lead_source)"
                    lead_where.append("(l.lead_source = %s OR ls.id = %s OR ls.source_name = %s)")
                    lead_params.extend([source_id, source_id, source_id])

                lead_where_sql = " AND ".join(lead_where)

                # 1. Total pure leads and disposed leads in system (Pure leads only: no followup, trial, so, client)
                cursor.execute(f"""
                    SELECT 
                        COUNT(l.id) AS total_leads, 
                        SUM(CASE WHEN l.is_disposed = 1 THEN 1 ELSE 0 END) AS total_disposed 
                    FROM leads l
                    {lead_join}
                    WHERE {lead_where_sql}
                      AND NOT EXISTS (SELECT 1 FROM followups f WHERE f.lead_id = l.id)
                      AND NOT EXISTS (SELECT 1 FROM free_trials ft WHERE ft.lead_id = l.id)
                      AND NOT EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id)
                      AND NOT EXISTS (SELECT 1 FROM clients c WHERE c.lead_id = l.id)
                """, lead_params)
                total_leads_row = cursor.fetchone()
                total_leads = int(total_leads_row["total_leads"]) if total_leads_row else 0
                total_disposed_system = int(total_leads_row["total_disposed"] or 0) if total_leads_row else 0
                total_active_system = total_leads - total_disposed_system

                # 2. All users with status and role
                cursor.execute("""
                    SELECT 
                        u.id AS user_id,
                        u.user_uuid,
                        u.full_name,
                        u.username,
                        COALESCE(u.status, 1) AS status,
                        COALESCE(r.role_name, 'Team Member') AS role_name
                    FROM users u
                    LEFT JOIN roles r ON r.id = u.role_id
                    ORDER BY u.status DESC, u.full_name ASC
                """)
                all_users = cursor.fetchall() or []

                user_map = {}
                for u in all_users:
                    uid = u["user_id"]
                    st = int(u.get("status") if u.get("status") is not None else 1)
                    user_map[uid] = {
                        "user_id": uid,
                        "user_uuid": u.get("user_uuid") or "",
                        "full_name": u.get("full_name") or u.get("username") or f"User #{uid}",
                        "username": u.get("username") or "",
                        "status": st,
                        "role_name": u.get("role_name") or "Team Member",
                        "total_assigned": 0,
                        "active_leads": 0,
                        "disposed_leads": 0,
                        "contact_count": 0,
                        "followup_count": 0,
                        "trial_count": 0,
                        "so_count": 0,
                        "paid_client_count": 0,
                    }

                active_user_ids = {u["user_id"] for u in all_users if int(u.get("status") if u.get("status") is not None else 1) == 1}
                disabled_user_ids = {u["user_id"] for u in all_users if int(u.get("status") if u.get("status") is not None else 1) == 0}

                unassigned = {
                    "user_id": "unassigned",
                    "user_uuid": "unassigned",
                    "full_name": "Unassigned Leads",
                    "username": "pool",
                    "role_name": "System Pool",
                    "status": 1,
                    "total_assigned": 0,
                    "active_leads": 0,
                    "disposed_leads": 0,
                    "contact_count": 0,
                    "followup_count": 0,
                    "trial_count": 0,
                    "so_count": 0,
                    "paid_client_count": 0,
                }

                disposed_data = {
                    "user_id": "disposed",
                    "user_uuid": "disposed",
                    "full_name": "Disposed Leads",
                    "username": "disposed",
                    "role_name": "System Disposed Pool",
                    "status": 1,
                    "total_assigned": total_disposed_system,
                    "active_leads": 0,
                    "disposed_leads": total_disposed_system,
                    "contact_count": 0,
                    "followup_count": 0,
                    "trial_count": 0,
                    "so_count": 0,
                    "paid_client_count": 0,
                }

                disabled_data = {
                    "user_id": "disabled_data",
                    "user_uuid": "disabled_data",
                    "full_name": "Disabled User Data",
                    "username": "disabled",
                    "role_name": "Deactivated Accounts",
                    "status": 0,
                    "total_assigned": 0,
                    "active_leads": 0,
                    "disposed_leads": 0,
                    "contact_count": 0,
                    "followup_count": 0,
                    "trial_count": 0,
                    "so_count": 0,
                    "paid_client_count": 0,
                }

                deleted_data = {
                    "user_id": "deleted_data",
                    "user_uuid": "deleted_data",
                    "full_name": "Deleted User Data",
                    "username": "deleted",
                    "role_name": "Deleted Accounts",
                    "status": 0,
                    "total_assigned": 0,
                    "active_leads": 0,
                    "disposed_leads": 0,
                    "contact_count": 0,
                    "followup_count": 0,
                    "trial_count": 0,
                    "so_count": 0,
                    "paid_client_count": 0,
                }

                # 3. High-performance lead counts (All active leads assigned to user)
                cursor.execute(f"""
                    SELECT 
                        l.current_owner_user_id, 
                        COUNT(l.id) AS total_cnt,
                        SUM(CASE WHEN l.is_disposed = 1 THEN 1 ELSE 0 END) AS disposed_cnt
                    FROM leads l
                    {lead_join}
                    WHERE {lead_where_sql}
                    GROUP BY l.current_owner_user_id
                """, lead_params)
                lead_stat_rows = cursor.fetchall() or []
                for r in lead_stat_rows:
                    owner_id = r.get("current_owner_user_id")
                    tot = int(r.get("total_cnt") or 0)
                    disp = int(r.get("disposed_cnt") or 0)
                    act = tot - disp
                    # Total assigned counts only active leads now (disposed removed from user buckets)
                    if owner_id is None or owner_id == 0:
                        unassigned["total_assigned"] += act
                        unassigned["disposed_leads"] += disp
                        unassigned["active_leads"] += act
                    elif owner_id in active_user_ids:
                        user_map[owner_id]["total_assigned"] += act
                        user_map[owner_id]["disposed_leads"] += disp
                        user_map[owner_id]["active_leads"] += act
                    elif owner_id in disabled_user_ids:
                        user_map[owner_id]["total_assigned"] += act
                        user_map[owner_id]["disposed_leads"] += disp
                        user_map[owner_id]["active_leads"] += act
                        disabled_data["total_assigned"] += act
                        disabled_data["disposed_leads"] += disp
                        disabled_data["active_leads"] += act
                    else:
                        # User ID does not exist in users table (deleted user)
                        deleted_data["total_assigned"] += act
                        deleted_data["disposed_leads"] += disp
                        deleted_data["active_leads"] += act

                # 4. Other metrics aggregations (Direct from respective tables by created_by_user_id)
                metric_queries = [
                    ("contact_count", f"SELECT c.created_by_user_id, COUNT(DISTINCT c.lead_id) AS cnt FROM contacts c JOIN leads l ON l.id = c.lead_id {lead_join} WHERE {lead_where_sql} GROUP BY c.created_by_user_id"),
                    ("followup_count", f"SELECT f.created_by_user_id, COUNT(DISTINCT f.lead_id) AS cnt FROM followups f JOIN leads l ON l.id = f.lead_id {lead_join} WHERE {lead_where_sql} GROUP BY f.created_by_user_id"),
                    ("trial_count", f"SELECT ft.created_by_user_id, COUNT(DISTINCT ft.lead_id) AS cnt FROM free_trials ft JOIN leads l ON l.id = ft.lead_id {lead_join} WHERE {lead_where_sql} GROUP BY ft.created_by_user_id"),
                    ("so_count", f"SELECT so.created_by_user_id, COUNT(so.id) AS cnt FROM sales_orders so JOIN leads l ON l.id = so.lead_id {lead_join} WHERE {lead_where_sql} GROUP BY so.created_by_user_id"),
                    ("paid_client_count", f"SELECT c.created_by_user_id, COUNT(DISTINCT c.lead_id) AS cnt FROM clients c JOIN leads l ON l.id = c.lead_id {lead_join} WHERE {lead_where_sql} GROUP BY c.created_by_user_id"),
                ]

                for metric_field, sql in metric_queries:
                    try:
                        cursor.execute(sql, lead_params)
                        for r in (cursor.fetchall() or []):
                            owner_id = r.get("created_by_user_id") if "created_by_user_id" in r else r.get("current_owner_user_id")
                            cnt = int(r.get("cnt") or 0)
                            if owner_id is None or owner_id == 0:
                                unassigned[metric_field] += cnt
                            elif owner_id in active_user_ids:
                                user_map[owner_id][metric_field] += cnt
                            elif owner_id in disabled_user_ids:
                                user_map[owner_id][metric_field] += cnt
                                disabled_data[metric_field] += cnt
                            else:
                                deleted_data[metric_field] += cnt
                    except Exception as q_err:
                        app.logger.warning(f"Error querying {metric_field} in user report: {q_err}")

                cursor.execute(f"SELECT COUNT(DISTINCT c.lead_id) AS cnt FROM contacts c JOIN leads l ON l.id = c.lead_id {lead_join} WHERE l.is_disposed = 1", lead_params)
                disposed_data["contact_count"] = int((cursor.fetchone() or {}).get("cnt") or 0)

                cursor.execute(f"SELECT COUNT(DISTINCT f.lead_id) AS cnt FROM followups f JOIN leads l ON l.id = f.lead_id {lead_join} WHERE l.is_disposed = 1", lead_params)
                disposed_data["followup_count"] = int((cursor.fetchone() or {}).get("cnt") or 0)

                cursor.execute(f"SELECT COUNT(DISTINCT ft.lead_id) AS cnt FROM free_trials ft JOIN leads l ON l.id = ft.lead_id {lead_join} WHERE l.is_disposed = 1", lead_params)
                disposed_data["trial_count"] = int((cursor.fetchone() or {}).get("cnt") or 0)

                cursor.execute(f"SELECT COUNT(so.id) AS cnt FROM sales_orders so JOIN leads l ON l.id = so.lead_id {lead_join} WHERE l.is_disposed = 1", lead_params)
                disposed_data["so_count"] = int((cursor.fetchone() or {}).get("cnt") or 0)

                cursor.execute(f"SELECT COUNT(DISTINCT c.lead_id) AS cnt FROM clients c JOIN leads l ON l.id = c.lead_id {lead_join} WHERE l.is_disposed = 1", lead_params)
                disposed_data["paid_client_count"] = int((cursor.fetchone() or {}).get("cnt") or 0)

                cursor.execute(f"SELECT COUNT(DISTINCT c.lead_id) AS cnt FROM contacts c JOIN leads l ON l.id = c.lead_id {lead_join} WHERE {lead_where_sql}", lead_params)
                total_system_contacts = int((cursor.fetchone() or {}).get("cnt") or 0)

                cursor.execute(f"SELECT COUNT(DISTINCT f.lead_id) AS cnt FROM followups f JOIN leads l ON l.id = f.lead_id {lead_join} WHERE {lead_where_sql}", lead_params)
                total_system_followups = int((cursor.fetchone() or {}).get("cnt") or 0)

                cursor.execute(f"SELECT COUNT(DISTINCT ft.lead_id) AS cnt FROM free_trials ft JOIN leads l ON l.id = ft.lead_id {lead_join} WHERE {lead_where_sql}", lead_params)
                total_system_trials = int((cursor.fetchone() or {}).get("cnt") or 0)

                cursor.execute(f"SELECT COUNT(so.id) AS cnt FROM sales_orders so JOIN leads l ON l.id = so.lead_id {lead_join} WHERE {lead_where_sql}", lead_params)
                total_system_so = int((cursor.fetchone() or {}).get("cnt") or 0)

                cursor.execute(f"SELECT COUNT(DISTINCT c.lead_id) AS cnt FROM clients c JOIN leads l ON l.id = c.lead_id {lead_join} WHERE {lead_where_sql}", lead_params)
                total_system_clients = int((cursor.fetchone() or {}).get("cnt") or 0)

                active_users = [u for u in user_map.values() if u["status"] == 1]
                active_users.sort(key=lambda x: (-x["total_assigned"], x["full_name"]))

                disabled_data["total_records"] = (
                    disabled_data["so_count"] + 
                    disabled_data["paid_client_count"] + 
                    disabled_data["contact_count"] + 
                    disabled_data["followup_count"] + 
                    disabled_data["trial_count"]
                )
                if disabled_data["active_leads"] == 0 and disabled_data["total_records"] > 0:
                    disabled_data["total_assigned"] = disabled_data["total_records"]
                elif disabled_data["active_leads"] > 0:
                    disabled_data["total_assigned"] = disabled_data["active_leads"] + disabled_data["total_records"]

                deleted_data["total_records"] = (
                    deleted_data["so_count"] + 
                    deleted_data["paid_client_count"] + 
                    deleted_data["contact_count"] + 
                    deleted_data["followup_count"] + 
                    deleted_data["trial_count"]
                )
                if deleted_data["active_leads"] == 0 and deleted_data["total_records"] > 0:
                    deleted_data["total_assigned"] = deleted_data["total_records"]
                elif deleted_data["active_leads"] > 0:
                    deleted_data["total_assigned"] = deleted_data["active_leads"] + deleted_data["total_records"]

                disabled_users = [u for u in user_map.values() if u["status"] == 0]
                for u in disabled_users:
                    u_rec = u["so_count"] + u["paid_client_count"] + u["contact_count"] + u["followup_count"] + u["trial_count"]
                    u["total_records"] = u_rec
                    if u["active_leads"] == 0 and u_rec > 0:
                        u["total_assigned"] = u_rec
                    elif u["active_leads"] > 0:
                        u["total_assigned"] = u["active_leads"] + u_rec

                disabled_users.sort(key=lambda x: (-x["total_assigned"], -x["disposed_leads"], x["full_name"]))

                all_users_list = active_users + disabled_users
                total_assigned_sum = sum(u["total_assigned"] for u in active_users)

            return jsonify({
                "success": True,
                "users": active_users,
                "active_users": active_users,
                "disabled_users": disabled_users,
                "all_users": all_users_list,
                "unassigned": unassigned,
                "disposed": disposed_data,
                "disposed_data": disposed_data,
                "disabled_data": disabled_data,
                "deleted_data": deleted_data,
                "old_disabled": disabled_data,
                "total_leads": total_active_system,
                "total_active_leads": total_active_system,
                "total_disposed_leads": total_disposed_system,
                "total_contacts": total_system_contacts,
                "total_followups": total_system_followups,
                "total_trials": total_system_trials,
                "total_so": total_system_so,
                "total_clients": total_system_clients,
                "active_users_count": len(active_users),
                "disabled_users_count": len(disabled_users),
                "total_assigned": total_assigned_sum,
                "total_unassigned": unassigned["total_assigned"],
                "total_disposed": total_disposed_system,
                "total_disabled_data": disabled_data["total_assigned"],
                "total_deleted_data": deleted_data["total_assigned"],
            })
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

    @app.route("/api/user-report/user-status-breakdown")
    @app.route("/api/lead-operations/user-status-breakdown")
    @require_user_report_permission
    def api_user_report_status_breakdown():
        """
        Returns simple tabular breakdown of lead statuses with active & disposed counts.
        """
        user_id_raw = (request.args.get("user_id") or "").strip()
        batch_id = (request.args.get("batch_id") or "all").strip()
        source_id = (request.args.get("source_id") or "all").strip()
        view_type = (request.args.get("view_type") or request.args.get("type") or "").strip().lower()
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                user_row = None
                user_title = "User"
                user_role = "Team Member"
                where_clause = ""
                params = []

                if user_id_raw == "disposed" or view_type == "disposed":
                    if user_id_raw == "disposed":
                        user_title = "Disposed Leads"
                        user_role = "System Disposed Pool"
                        where_clause = "l.is_disposed = 1"
                    elif user_id_raw == "unassigned":
                        user_title = "Unassigned Leads (Disposed)"
                        user_role = "System Pool"
                        where_clause = "(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND l.is_disposed = 1"
                    elif user_id_raw == "disabled_data":
                        user_title = "Disabled User Data (Disposed)"
                        user_role = "Deactivated Accounts"
                        where_clause = """
                            (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                                l.current_owner_user_id IN (SELECT id FROM users WHERE status = 0)
                            )) AND l.is_disposed = 1
                        """
                    elif user_id_raw in ["deleted_data", "old_disabled"]:
                        user_title = "Deleted User Data (Disposed)"
                        user_role = "Deleted Accounts"
                        where_clause = """
                            (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                                l.current_owner_user_id NOT IN (SELECT id FROM users)
                            )) AND l.is_disposed = 1
                        """
                    else:
                        cursor.execute("""
                            SELECT u.id, u.user_uuid, u.full_name, u.username, COALESCE(r.role_name, 'Team Member') AS role_name, COALESCE(u.status, 1) AS status
                            FROM users u
                            LEFT JOIN roles r ON r.id = u.role_id
                            WHERE u.id = %s OR u.user_uuid = %s
                            LIMIT 1
                        """, (user_id_raw if user_id_raw.isdigit() else -1, user_id_raw))
                        user_row = cursor.fetchone()
                        if user_row:
                            user_title = (user_row.get("full_name") or user_row.get("username") or f"User #{user_row['id']}") + " (Disposed Leads)"
                            user_role = user_row.get("role_name") or "Team Member"
                            where_clause = "l.current_owner_user_id = %s AND l.is_disposed = 1"
                            params.append(user_row["id"])
                        else:
                            user_title = "Unassigned Leads"
                            user_role = "System Pool"
                            where_clause = "(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND l.is_disposed = 1"
                elif user_id_raw == "unassigned":
                    user_title = "Unassigned Leads"
                    user_role = "System Pool"
                    where_clause = "(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)"
                elif user_id_raw == "disabled_data":
                    user_title = "Disabled User Data"
                    user_role = "Deactivated Accounts"
                    where_clause = """
                        (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                            l.current_owner_user_id IN (SELECT id FROM users WHERE status = 0)
                        )) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)
                    """
                elif user_id_raw in ["deleted_data", "old_disabled"]:
                    user_title = "Deleted User Data"
                    user_role = "Deleted Accounts"
                    where_clause = """
                        (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                            l.current_owner_user_id NOT IN (SELECT id FROM users)
                        )) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)
                    """
                else:
                    cursor.execute("""
                        SELECT u.id, u.user_uuid, u.full_name, u.username, COALESCE(r.role_name, 'Team Member') AS role_name, COALESCE(u.status, 1) AS status
                        FROM users u
                        LEFT JOIN roles r ON r.id = u.role_id
                        WHERE u.id = %s OR u.user_uuid = %s
                        LIMIT 1
                    """, (user_id_raw if user_id_raw.isdigit() else -1, user_id_raw))
                    user_row = cursor.fetchone()
                    if user_row:
                        user_title = user_row.get("full_name") or user_row.get("username") or f"User #{user_row['id']}"
                        user_role = user_row.get("role_name") or "Team Member"
                        where_clause = "l.current_owner_user_id = %s AND (l.is_disposed = 0 OR l.is_disposed IS NULL)"
                        params.append(user_row["id"])
                    else:
                        user_title = "Unassigned Leads"
                        user_role = "System Pool"
                        where_clause = "(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)"

                if batch_id and batch_id != "all":
                    where_clause += " AND (l.lead_batch_id = %s OR CAST(l.lead_batch_id AS CHAR) = %s)"
                    params.extend([batch_id, batch_id])

                if source_id and source_id != "all":
                    where_clause += " AND (l.lead_source = %s OR ls_b.id = %s OR ls_b.source_name = %s)"
                    params.extend([source_id, source_id, source_id])

                # Status breakdown query
                status_sql = f"""
                    SELECT 
                        CASE 
                            WHEN st.status_name IS NOT NULL THEN st.status_name
                            WHEN l.lead_status IS NULL OR l.lead_status = '' OR l.lead_status = '0' OR l.lead_status = 'No Status' THEN 'Fresh' 
                            WHEN l.lead_status REGEXP '^[0-9]+$' THEN CONCAT('Status id ', l.lead_status, ' Deleted')
                            ELSE CONCAT('Status ', l.lead_status, ' Deleted')
                        END AS display_status,
                        COUNT(l.id) AS total_leads
                    FROM leads l
                    LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_name = l.lead_status)
                    LEFT JOIN lead_sources ls_b ON (ls_b.id = l.lead_source OR ls_b.source_uuid = l.lead_source OR ls_b.source_name = l.lead_source)
                    WHERE {where_clause}
                    GROUP BY display_status
                    ORDER BY total_leads DESC
                """
                cursor.execute(status_sql, params)
                breakdown_rows = cursor.fetchall() or []

                total_leads = sum(int(r["total_leads"] or 0) for r in breakdown_rows)

                statuses = []
                for r in breakdown_rows:
                    s_name = r["display_status"]
                    is_deleted_status = "Deleted" in s_name
                    statuses.append({
                        "status_name": s_name,
                        "is_deleted": is_deleted_status,
                        "total_leads": int(r["total_leads"] or 0)
                    })

                # Also include standalone / linked records (Sales Orders, Paid Clients, Follow-ups, Free Trials) across all segments
                record_categories = []
                rec_where_sql = None
                rec_params = []

                if user_id_raw == "disposed" or view_type == "disposed":
                    if user_row:
                        rec_where_sql = "lead_id IN (SELECT id FROM leads WHERE current_owner_user_id = %s AND is_disposed = 1)"
                        rec_params = [user_row["id"]]
                    elif user_id_raw == "disabled_data":
                        rec_where_sql = "lead_id IN (SELECT id FROM leads WHERE current_owner_user_id IN (SELECT id FROM users WHERE status = 0) AND is_disposed = 1)"
                    elif user_id_raw in ("deleted_data", "old_disabled"):
                        rec_where_sql = "lead_id IN (SELECT id FROM leads WHERE current_owner_user_id NOT IN (SELECT id FROM users) AND is_disposed = 1)"
                    elif user_id_raw == "unassigned":
                        rec_where_sql = "lead_id IN (SELECT id FROM leads WHERE (current_owner_user_id IS NULL OR current_owner_user_id = 0) AND is_disposed = 1)"
                    else:
                        rec_where_sql = "lead_id IN (SELECT id FROM leads WHERE is_disposed = 1)"
                elif user_id_raw == "disabled_data":
                    rec_where_sql = "created_by_user_id IN (SELECT id FROM users WHERE status = 0)"
                elif user_id_raw in ("deleted_data", "old_disabled"):
                    rec_where_sql = "created_by_user_id IS NOT NULL AND created_by_user_id != 0 AND created_by_user_id NOT IN (SELECT id FROM users)"
                elif user_id_raw == "unassigned":
                    rec_where_sql = "(created_by_user_id IS NULL OR created_by_user_id = 0)"
                elif user_row:
                    rec_where_sql = "created_by_user_id = %s"
                    rec_params = [user_row["id"]]
                elif user_id_raw and user_id_raw.isdigit():
                    rec_where_sql = "created_by_user_id = %s"
                    rec_params = [int(user_id_raw)]

                if rec_where_sql:
                    cursor.execute(f"SELECT COUNT(DISTINCT lead_id) AS cnt FROM contacts WHERE {rec_where_sql}", rec_params)
                    contact_c = int((cursor.fetchone() or {}).get("cnt") or 0)
                    if contact_c > 0:
                        record_categories.append({
                            "status_name": "Contacts",
                            "is_record_category": True,
                            "record_type": "contacts",
                            "badge_color": "#fd7e14",
                            "total_leads": contact_c
                        })

                    cursor.execute(f"SELECT COUNT(id) AS cnt FROM sales_orders WHERE {rec_where_sql}", rec_params)
                    so_c = int((cursor.fetchone() or {}).get("cnt") or 0)
                    if so_c > 0:
                        record_categories.append({
                            "status_name": "Sales Orders",
                            "is_record_category": True,
                            "record_type": "sales_orders",
                            "badge_color": "#0d9488",
                            "total_leads": so_c
                        })

                    cursor.execute(f"SELECT COUNT(DISTINCT lead_id) AS cnt FROM clients WHERE {rec_where_sql}", rec_params)
                    client_c = int((cursor.fetchone() or {}).get("cnt") or 0)
                    if client_c > 0:
                        record_categories.append({
                            "status_name": "Paid Clients",
                            "is_record_category": True,
                            "record_type": "clients",
                            "badge_color": "#198754",
                            "total_leads": client_c
                        })

                    cursor.execute(f"SELECT COUNT(DISTINCT lead_id) AS cnt FROM followups WHERE {rec_where_sql}", rec_params)
                    fup_c = int((cursor.fetchone() or {}).get("cnt") or 0)
                    if fup_c > 0:
                        record_categories.append({
                            "status_name": "Follow-ups",
                            "is_record_category": True,
                            "record_type": "followups",
                            "badge_color": "#0dcaf0",
                            "total_leads": fup_c
                        })

                    cursor.execute(f"SELECT COUNT(DISTINCT lead_id) AS cnt FROM free_trials WHERE {rec_where_sql}", rec_params)
                    ft_c = int((cursor.fetchone() or {}).get("cnt") or 0)
                    if ft_c > 0:
                        record_categories.append({
                            "status_name": "Free Trials",
                            "is_record_category": True,
                            "record_type": "free_trials",
                            "badge_color": "#6f42c1",
                            "total_leads": ft_c
                        })

                # Put user record categories at TOP so they are immediately visible
                statuses = record_categories + statuses
                total_records_count = sum(int(s["total_leads"] or 0) for s in record_categories)
                total_all_records = total_leads + total_records_count

                cursor.execute("SELECT id, source_name FROM lead_sources ORDER BY source_name ASC")
                sources_list = cursor.fetchall() or []

                cursor.execute("SELECT id, user_uuid, full_name FROM users WHERE status = 1 ORDER BY full_name ASC")
                active_users_list = cursor.fetchall() or []

                return jsonify({
                    "success": True,
                    "user_id": user_id_raw,
                    "user_title": user_title,
                    "user_role": user_role,
                    "total_leads": total_leads,
                    "total_records": total_records_count,
                    "total_all_records": total_all_records,
                    "total_active": total_leads if (user_id_raw != "disposed" and view_type != "disposed") else 0,
                    "total_disposed": total_leads if (user_id_raw == "disposed" or view_type == "disposed") else 0,
                    "statuses": statuses,
                    "active_users": active_users_list,
                    "lead_sources": sources_list,
                })
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

    @app.route("/api/user-report/user-leads")
    @app.route("/api/lead-operations/user-leads")
    @require_user_report_permission
    def api_user_report_user_leads():
        """
        Fetches paginated list of leads assigned to a specific user (or unassigned).
        Supports status filtering and search.
        """
        user_id_raw = (request.args.get("user_id") or "").strip()
        status_filter = (request.args.get("status") or "").strip()
        search_query = (request.args.get("search") or "").strip()
        batch_id = (request.args.get("batch_id") or "all").strip()
        source_id = (request.args.get("source_id") or "all").strip()
        view_type = (request.args.get("view_type") or request.args.get("type") or "").strip().lower()
        page = max(1, int(request.args.get("page", 1)))
        limit = min(100, max(10, int(request.args.get("limit", 25))))
        offset = (page - 1) * limit

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                user_info = None
                if user_id_raw and user_id_raw != "unassigned":
                    cursor.execute("""
                        SELECT u.id, u.user_uuid, u.full_name, u.username, COALESCE(r.role_name, 'Team Member') AS role_name, COALESCE(u.status, 1) AS status
                        FROM users u
                        LEFT JOIN roles r ON r.id = u.role_id
                        WHERE u.id = %s OR u.user_uuid = %s
                        LIMIT 1
                    """, (user_id_raw if user_id_raw.isdigit() else -1, user_id_raw))
                    user_info = cursor.fetchone()

                if not user_info and user_id_raw not in ("unassigned", "old_disabled", "disabled_data", "deleted_data", "disposed"):
                    user_id_raw = "unassigned"

                where_clauses = []
                params = []

                if user_id_raw == "disposed" or view_type == "disposed":
                    if user_id_raw == "disposed":
                        user_info = {
                            "id": "disposed",
                            "full_name": "Disposed Leads",
                            "username": "disposed",
                            "role_name": "System Disposed Pool"
                        }
                        where_clauses.append("l.is_disposed = 1")
                    elif user_id_raw == "unassigned":
                        where_clauses.append("(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND l.is_disposed = 1")
                    elif user_id_raw == "disabled_data":
                        where_clauses.append("""
                            (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                                l.current_owner_user_id IN (SELECT id FROM users WHERE status = 0)
                            )) AND l.is_disposed = 1
                        """)
                    elif user_id_raw in ("deleted_data", "old_disabled"):
                        where_clauses.append("""
                            (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                                l.current_owner_user_id NOT IN (SELECT id FROM users)
                            )) AND l.is_disposed = 1
                        """)
                    else:
                        where_clauses.append("l.current_owner_user_id = %s AND l.is_disposed = 1")
                        params.append(user_info["id"])
                elif user_id_raw == "unassigned":
                    where_clauses.append("(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)")
                elif user_id_raw == "disabled_data":
                    where_clauses.append("""
                        (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                            l.current_owner_user_id IN (SELECT id FROM users WHERE status = 0)
                        )) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)
                    """)
                elif user_id_raw in ("deleted_data", "old_disabled"):
                    where_clauses.append("""
                        (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                            l.current_owner_user_id NOT IN (SELECT id FROM users)
                        )) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)
                    """)
                else:
                    where_clauses.append("l.current_owner_user_id = %s AND (l.is_disposed = 0 OR l.is_disposed IS NULL)")
                    params.append(user_info["id"])

                # Batch & Source filter
                if batch_id and batch_id != "all":
                    where_clauses.append("(l.lead_batch_id = %s OR CAST(l.lead_batch_id AS CHAR) = %s)")
                    params.extend([batch_id, batch_id])

                if source_id and source_id != "all":
                    where_clauses.append("(l.lead_source = %s OR ls.id = %s OR ls.source_name = %s)")
                    params.extend([source_id, source_id, source_id])

                # Status filter
                if status_filter:
                    sl = status_filter.lower()
                    if sl in ("fresh", "no status", "no_status"):
                        where_clauses.append("(l.lead_status IS NULL OR l.lead_status = '' OR l.lead_status = '0' OR l.lead_status = 'No Status' OR st.status_name = 'Fresh')")
                    elif sl == "disposed":
                        where_clauses.append("l.is_disposed = 1")
                    elif sl == "contacts":
                        where_clauses.append("EXISTS (SELECT 1 FROM contacts cnt WHERE cnt.lead_id = l.id)")
                    elif sl == "followups":
                        where_clauses.append("EXISTS (SELECT 1 FROM followups f WHERE f.lead_id = l.id)")
                    elif sl in ("free_trials", "trials"):
                        where_clauses.append("EXISTS (SELECT 1 FROM free_trials ft WHERE ft.lead_id = l.id)")
                    elif sl in ("so", "converted", "sales_orders"):
                        where_clauses.append("EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id)")
                    elif sl in ("clients", "paid_clients", "paid"):
                        where_clauses.append("EXISTS (SELECT 1 FROM clients c WHERE c.lead_id = l.id)")
                    else:
                        where_clauses.append("(st.status_name = %s OR l.lead_status = %s)")
                        params.extend([status_filter, status_filter])

                # Search filter
                if search_query:
                    where_clauses.append("""
                        (l.name LIKE %s OR l.mobile_number LIKE %s OR l.email LIKE %s OR l.id LIKE %s OR l.lead_uuid LIKE %s)
                    """)
                    s_term = f"%{search_query}%"
                    params.extend([s_term, s_term, s_term, s_term, s_term])

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                # Count query
                count_query = f"""
                    SELECT COUNT(l.id) AS total_count
                    FROM leads l
                    LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_name = l.lead_status)
                    LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_uuid = l.lead_source OR ls.source_name = l.lead_source)
                    WHERE {where_sql}
                """
                cursor.execute(count_query, params)
                total_count_row = cursor.fetchone()
                total_count = int(total_count_row["total_count"]) if total_count_row else 0

                # Data query
                data_query = f"""
                    SELECT 
                        l.id AS lead_id,
                        l.lead_uuid,
                        COALESCE(l.name, 'N/A') AS name,
                        l.mobile_number,
                        COALESCE(l.email, '') AS email,
                        COALESCE(ls.source_name, 'No Source') AS lead_source,
                        COALESCE(st.status_name, 'Fresh') AS lead_status,
                        COALESCE(st.status_tone, 'secondary') AS status_tone,
                        COALESCE(l.is_disposed, 0) AS is_disposed,
                        (CASE WHEN EXISTS (SELECT 1 FROM contacts cnt WHERE cnt.lead_id = l.id) THEN 1 ELSE 0 END) AS has_contact,
                        (CASE WHEN EXISTS (SELECT 1 FROM followups f WHERE f.lead_id = l.id) THEN 1 ELSE 0 END) AS has_followup,
                        (CASE WHEN EXISTS (SELECT 1 FROM free_trials ft WHERE ft.lead_id = l.id) THEN 1 ELSE 0 END) AS has_free_trial,
                        (CASE WHEN EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id) THEN 1 ELSE 0 END) AS has_so,
                        (CASE WHEN EXISTS (SELECT 1 FROM clients c WHERE c.lead_id = l.id) THEN 1 ELSE 0 END) AS has_client,
                        DATE_FORMAT(l.assigned_at, '%%d %%b %%Y, %%I:%%i %%p') AS assigned_at_fmt,
                        DATE_FORMAT(l.created_at, '%%d %%b %%Y, %%I:%%i %%p') AS created_at_fmt
                    FROM leads l
                    LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)
                    LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_name = l.lead_status)
                    WHERE {where_sql}
                    ORDER BY l.id DESC
                    LIMIT %s OFFSET %s
                """
                fetch_params = list(params) + [limit, offset]
                cursor.execute(data_query, fetch_params)
                leads = cursor.fetchall() or []

                # Format leads
                user = get_current_user(cursor, session.get("user_uuid"))
                permissions = get_action_permissions(user)
                can_view_mobile = permissions.get("can_view_mobile")

                for ld in leads:
                    ld["client_code"] = str(ld["lead_id"])
                    raw_mob = ld.get("mobile_number") or ""
                    if can_view_mobile:
                        ld["mobile"] = decrypt_mobile(raw_mob)
                    else:
                        mob_dec = decrypt_mobile(raw_mob)
                        ld["mobile"] = mob_dec[:2] + "******" + mob_dec[-2:] if len(mob_dec) >= 6 else "******"
                    ld.pop("mobile_number", None)

            return jsonify({
                "success": True,
                "leads": leads,
                "total_count": total_count,
                "page": page,
                "limit": limit,
                "total_pages": (total_count + limit - 1) // limit if limit else 1,
                "user_info": user_info or {
                    "id": "unassigned",
                    "full_name": "Unassigned Leads",
                    "username": "pool",
                    "role_name": "System Pool"
                }
            })
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

    @app.route("/api/user-report/assign", methods=["POST"])
    @app.route("/api/lead-operations/assign", methods=["POST"])
    @require_user_report_permission
    def api_user_report_assign():
        """
        Assigns selected lead UUIDs or top N leads from a specific user to a target user.
        """
        data = request.get_json() or {}
        target_user_id = data.get("target_user_id")
        lead_uuids = data.get("lead_uuids") or []
        from_user_id = data.get("from_user_id")
        count = data.get("count")
        reset_data = bool(data.get("reset_data", False))
        is_unassign_mode = bool(data.get("is_unassign_mode", False))

        if not target_user_id and not is_unassign_mode:
            return jsonify({"success": False, "message": "Please select a target user to assign leads."}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # If count provided and no specific lead_uuids, fetch top N leads from from_user_id
                if count and not lead_uuids:
                    try:
                        count = int(count)
                    except ValueError:
                        return jsonify({"success": False, "message": "Invalid count specified."}), 400

                    if count <= 0:
                        return jsonify({"success": False, "message": "Count must be greater than 0."}), 400

                    if from_user_id == "disposed":
                        cursor.execute("""
                            SELECT lead_uuid FROM leads 
                            WHERE is_disposed = 1
                            ORDER BY id DESC LIMIT %s
                        """, (count,))
                    elif from_user_id == "unassigned":
                        cursor.execute("""
                            SELECT lead_uuid FROM leads 
                            WHERE (current_owner_user_id IS NULL OR current_owner_user_id = 0) AND (is_disposed = 0 OR is_disposed IS NULL)
                            ORDER BY id DESC LIMIT %s
                        """, (count,))
                    elif from_user_id == "disabled_data":
                        cursor.execute("""
                            SELECT lead_uuid FROM leads 
                            WHERE current_owner_user_id IS NOT NULL AND current_owner_user_id != 0
                              AND (current_owner_user_id IN (SELECT id FROM users WHERE status = 0))
                              AND (is_disposed = 0 OR is_disposed IS NULL)
                            ORDER BY id DESC LIMIT %s
                        """, (count,))
                    elif from_user_id in ("deleted_data", "old_disabled"):
                        cursor.execute("""
                            SELECT lead_uuid FROM leads 
                            WHERE current_owner_user_id IS NOT NULL AND current_owner_user_id != 0
                              AND (current_owner_user_id NOT IN (SELECT id FROM users))
                              AND (is_disposed = 0 OR is_disposed IS NULL)
                            ORDER BY id DESC LIMIT %s
                        """, (count,))
                    else:
                        cursor.execute("""
                            SELECT lead_uuid FROM leads 
                            WHERE current_owner_user_id = %s AND (is_disposed = 0 OR is_disposed IS NULL)
                            ORDER BY id DESC LIMIT %s
                        """, (from_user_id, count))
                    rows = cursor.fetchall() or []
                    lead_uuids = [r["lead_uuid"] for r in rows if r.get("lead_uuid")]

            if not lead_uuids:
                return jsonify({"success": False, "message": "No leads found or selected to assign."}), 400

            target_identifier = "unassigned" if is_unassign_mode else target_user_id
            result = process_assign_leads(
                logged_user_uuid=session.get("user_uuid"),
                target_user_uuid=target_identifier,
                lead_uuids=lead_uuids,
                reset_data=reset_data,
                ip_address=request.remote_addr
            )
            return jsonify(result), (200 if result.get("success") else 400)
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

    @app.route("/api/user-report/delete", methods=["POST"])
    @app.route("/api/lead-operations/delete", methods=["POST"])
    @require_user_report_permission
    def api_user_report_delete():
        """
        Deletes selected lead UUIDs with permission check and user_activities logging.
        """
        data = request.get_json() or {}
        lead_uuids = data.get("lead_uuids") or []

        if not lead_uuids:
            return jsonify({"success": False, "message": "No leads selected for deletion."}), 400

        result = process_delete_lead(
            logged_user_uuid=session.get("user_uuid"),
            lead_uuids=lead_uuids,
            ip_address=request.remote_addr
        )
        return jsonify(result), (200 if result.get("success") else 400)

    @app.route("/api/user-report/move-status-leads", methods=["POST"])
    @app.route("/api/lead-operations/move-status-leads", methods=["POST"])
    @require_user_report_permission
    def api_user_report_move_status_leads():
        """
        Moves (reassigns) or deletes pure leads matching selected statuses for a given source user.
        Strict guarantee: Leads with followups, free trials, sales orders, or clients are NEVER moved or deleted!
        """
        data = request.get_json() or {}
        source_user_id = str(data.get("source_user_id") or "").strip()
        selected_statuses = data.get("statuses") or []
        action = str(data.get("action") or "assign").strip().lower()
        target_user_id = data.get("target_user_id")
        new_source = data.get("new_source")
        reset_data = bool(data.get("reset_data", False))
        batch_id = str(data.get("batch_id") or "all").strip()
        source_id = str(data.get("source_id") or "all").strip()
        view_type = str(data.get("view_type") or data.get("type") or "").strip().lower()

        move_followups = bool(data.get("move_followups", False))
        move_trials = bool(data.get("move_trials", False))
        move_so = bool(data.get("move_so", False))
        move_clients = bool(data.get("move_clients", False))
        move_contacts = bool(data.get("move_contacts", False))

        # Do NOT apply linked moves for disposed view
        if view_type == "disposed" or source_user_id == "disposed":
            move_followups = move_trials = move_so = move_clients = move_contacts = False

        RECORD_CAT_MAP = {
            "contacts": "contacts",
            "contact": "contacts",
            "contacts user record": "contacts",
            "contact user record": "contacts",
            "sales orders": "sales_orders",
            "sales order": "sales_orders",
            "sales orders user record": "sales_orders",
            "paid clients": "clients",
            "paid client": "clients",
            "paid clients user record": "clients",
            "follow-ups": "followups",
            "followups": "followups",
            "follow-up": "followups",
            "follow-ups user record": "followups",
            "followups user record": "followups",
            "free trials": "free_trials",
            "free trial": "free_trials",
            "free trials user record": "free_trials"
        }

        pure_lead_statuses = []
        record_types_to_process = set()

        if move_contacts: record_types_to_process.add("contacts")
        if move_so: record_types_to_process.add("sales_orders")
        if move_clients: record_types_to_process.add("clients")
        if move_followups: record_types_to_process.add("followups")
        if move_trials: record_types_to_process.add("free_trials")

        for s in selected_statuses:
            s_clean = str(s).strip()
            s_lower = s_clean.lower()
            if s_lower in RECORD_CAT_MAP:
                record_types_to_process.add(RECORD_CAT_MAP[s_lower])
            else:
                pure_lead_statuses.append(s_clean)

        if not pure_lead_statuses and not record_types_to_process:
            return jsonify({"success": False, "message": "Please select at least one status or record category to proceed."}), 400

        if action == "assign" and not target_user_id:
            return jsonify({"success": False, "message": "Please select a target user to assign to."}), 400

        if action == "assign" and target_user_id == "unassigned" and not pure_lead_statuses and record_types_to_process:
            return jsonify({"success": False, "message": "Sales Orders and Paid Clients must be assigned to an active user."}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Resolve destination user
                target_ident = "unassigned" if target_user_id == "unassigned" else target_user_id
                dest_user_id = None
                dest_user_name = "Unassigned"
                if action == "assign" and target_ident != "unassigned":
                    cursor.execute("""
                        SELECT id, full_name, username 
                        FROM users 
                        WHERE id = %s OR user_uuid = %s 
                        LIMIT 1
                    """, (target_ident if str(target_ident).isdigit() else -1, target_ident))
                    tgt_u = cursor.fetchone()
                    if tgt_u:
                        dest_user_id = tgt_u["id"]
                        dest_user_name = tgt_u.get("full_name") or tgt_u.get("username") or f"User #{dest_user_id}"

                # Resolve source user details
                source_user_db_id = None
                source_user_name = "User"
                if source_user_id.isdigit():
                    source_user_db_id = int(source_user_id)
                    cursor.execute("SELECT id, full_name, username FROM users WHERE id = %s LIMIT 1", (source_user_db_id,))
                    s_row = cursor.fetchone()
                    if s_row:
                        source_user_name = s_row.get("full_name") or s_row.get("username") or f"User #{source_user_db_id}"
                elif source_user_id not in ("unassigned", "disposed", "disabled_data", "deleted_data", "old_disabled"):
                    cursor.execute("SELECT id, full_name, username FROM users WHERE user_uuid = %s LIMIT 1", (source_user_id,))
                    s_row = cursor.fetchone()
                    if s_row:
                        source_user_db_id = s_row["id"]
                        source_user_name = s_row.get("full_name") or s_row.get("username") or f"User #{source_user_db_id}"

                lead_uuids = []
                lead_ids = []

                if pure_lead_statuses:
                    where_clauses = []
                    params = []

                    # 1. Source user filtering
                    if source_user_id == "disposed" or view_type == "disposed":
                        if source_user_id == "disposed":
                            where_clauses.append("l.is_disposed = 1")
                        elif source_user_id == "unassigned":
                            where_clauses.append("(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND l.is_disposed = 1")
                        elif source_user_id == "disabled_data":
                            where_clauses.append("""
                                (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                                    l.current_owner_user_id IN (SELECT id FROM users WHERE status = 0)
                                )) AND l.is_disposed = 1
                            """)
                        elif source_user_id in ("deleted_data", "old_disabled"):
                            where_clauses.append("""
                                (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                                    l.current_owner_user_id NOT IN (SELECT id FROM users)
                                )) AND l.is_disposed = 1
                            """)
                        else:
                            if source_user_db_id:
                                where_clauses.append("l.current_owner_user_id = %s AND l.is_disposed = 1")
                                params.append(source_user_db_id)
                            else:
                                where_clauses.append("(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND l.is_disposed = 1")
                    elif source_user_id == "unassigned":
                        where_clauses.append("(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)")
                    elif source_user_id == "disabled_data":
                        where_clauses.append("""
                            (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                                l.current_owner_user_id IN (SELECT id FROM users WHERE status = 0)
                            )) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)
                        """)
                    elif source_user_id in ("deleted_data", "old_disabled"):
                        where_clauses.append("""
                            (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                                l.current_owner_user_id NOT IN (SELECT id FROM users)
                            )) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)
                        """)
                    else:
                        if source_user_db_id:
                            where_clauses.append("l.current_owner_user_id = %s AND (l.is_disposed = 0 OR l.is_disposed IS NULL)")
                            params.append(source_user_db_id)
                        else:
                            where_clauses.append("(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)")

                    # Batch & Source filter
                    if batch_id and batch_id != "all":
                        where_clauses.append("(l.lead_batch_id = %s OR CAST(l.lead_batch_id AS CHAR) = %s)")
                        params.extend([batch_id, batch_id])

                    if source_id and source_id != "all":
                        where_clauses.append("(l.lead_source = %s OR ls_move.id = %s OR ls_move.source_name = %s)")
                        params.extend([source_id, source_id, source_id])

                    # 2. Status matching clause
                    status_or_parts = []
                    for s_clean in pure_lead_statuses:
                        if s_clean.lower() in ("fresh", "no status", "no_status", ""):
                            status_or_parts.append("(l.lead_status IS NULL OR l.lead_status = '' OR l.lead_status = '0' OR l.lead_status = 'No Status' OR st.status_name = 'Fresh')")
                        elif s_clean.startswith("Status id ") and s_clean.endswith(" Deleted"):
                            stat_id = s_clean.replace("Status id ", "").replace(" Deleted", "").strip()
                            status_or_parts.append("l.lead_status = %s")
                            params.append(stat_id)
                        elif s_clean.startswith("Status ") and s_clean.endswith(" Deleted"):
                            stat_id = s_clean.replace("Status ", "").replace(" Deleted", "").strip()
                            status_or_parts.append("l.lead_status = %s")
                            params.append(stat_id)
                        else:
                            status_or_parts.append("(st.status_name = %s OR l.lead_status = %s)")
                            params.extend([s_clean, s_clean])

                    if status_or_parts:
                        where_clauses.append(f"({' OR '.join(status_or_parts)})")

                    where_sql = " AND ".join(where_clauses)

                    cursor.execute(f"""
                        SELECT l.id, l.lead_uuid
                        FROM leads l
                        LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_name = l.lead_status)
                        LEFT JOIN lead_sources ls_move ON (ls_move.id = l.lead_source OR ls_move.source_uuid = l.lead_source OR ls_move.source_name = l.lead_source)
                        WHERE {where_sql}
                    """, params)
                    rows = cursor.fetchall() or []
                    lead_uuids = [r["lead_uuid"] for r in rows if r.get("lead_uuid")]
                    lead_ids = [r["id"] for r in rows if r.get("id")]

                logged_uuid = session.get("user_uuid")
                ip = request.remote_addr
                total_updated = 0
                total_deleted = 0

                # Standalone / user-created records matching clause across all segments
                rec_where_sql = None
                rec_params = []

                if source_user_id == "disposed" or view_type == "disposed":
                    if source_user_db_id:
                        rec_where_sql = "lead_id IN (SELECT id FROM leads WHERE current_owner_user_id = %s AND is_disposed = 1)"
                        rec_params = [source_user_db_id]
                    elif source_user_id == "disabled_data":
                        rec_where_sql = "lead_id IN (SELECT id FROM leads WHERE current_owner_user_id IN (SELECT id FROM users WHERE status = 0) AND is_disposed = 1)"
                    elif source_user_id in ("deleted_data", "old_disabled"):
                        rec_where_sql = "lead_id IN (SELECT id FROM leads WHERE current_owner_user_id NOT IN (SELECT id FROM users) AND is_disposed = 1)"
                    elif source_user_id == "unassigned":
                        rec_where_sql = "lead_id IN (SELECT id FROM leads WHERE (current_owner_user_id IS NULL OR current_owner_user_id = 0) AND is_disposed = 1)"
                    else:
                        rec_where_sql = "lead_id IN (SELECT id FROM leads WHERE is_disposed = 1)"
                elif source_user_id == "disabled_data":
                    rec_where_sql = "created_by_user_id IN (SELECT id FROM users WHERE status = 0)"
                elif source_user_id in ("deleted_data", "old_disabled"):
                    rec_where_sql = "created_by_user_id IS NOT NULL AND created_by_user_id != 0 AND created_by_user_id NOT IN (SELECT id FROM users)"
                elif source_user_id == "unassigned":
                    rec_where_sql = "(created_by_user_id IS NULL OR created_by_user_id = 0)"
                elif source_user_db_id is not None:
                    rec_where_sql = "created_by_user_id = %s"
                    rec_params = [source_user_db_id]

                if action == "assign":
                    if lead_uuids:
                        chunk_size = 1000
                        for i in range(0, len(lead_uuids), chunk_size):
                            chunk_uuids = lead_uuids[i:i + chunk_size]
                            chunk_ids = lead_ids[i:i + chunk_size]
                            res = process_assign_leads(
                                logged_user_uuid=logged_uuid,
                                target_user_uuid=target_ident,
                                lead_uuids=chunk_uuids,
                                new_source=new_source if new_source else None,
                                reset_data=reset_data,
                                ip_address=ip
                            )
                            if res.get("success"):
                                total_updated += len(chunk_uuids)

                                # Transfer linked records ownership if requested and destination user is valid
                                if dest_user_id is not None and chunk_ids:
                                    pl_ids = ", ".join(["%s"] * len(chunk_ids))

                                    if "contacts" in record_types_to_process:
                                        cursor.execute(f"""
                                            UPDATE contacts 
                                            SET created_by_user_id = %s, created_by_name = %s, updated_at = NOW() 
                                            WHERE lead_id IN ({pl_ids})
                                        """, [dest_user_id, dest_user_name] + chunk_ids)

                                    if "followups" in record_types_to_process:
                                        cursor.execute(f"""
                                            UPDATE followups 
                                            SET created_by_user_id = %s, created_by_name = %s, updated_at = NOW() 
                                            WHERE lead_id IN ({pl_ids})
                                        """, [dest_user_id, dest_user_name] + chunk_ids)

                                    if "free_trials" in record_types_to_process:
                                        cursor.execute(f"""
                                            UPDATE free_trials 
                                            SET created_by_user_id = %s, created_by_name = %s, updated_at = NOW() 
                                            WHERE lead_id IN ({pl_ids})
                                        """, [dest_user_id, dest_user_name] + chunk_ids)

                                    if "sales_orders" in record_types_to_process:
                                        cursor.execute(f"""
                                            UPDATE sales_orders 
                                            SET created_by_user_id = %s, created_by_name = %s, updated_at = NOW() 
                                            WHERE lead_id IN ({pl_ids})
                                        """, [dest_user_id, dest_user_name] + chunk_ids)

                                    if "clients" in record_types_to_process:
                                        cursor.execute(f"""
                                            UPDATE clients 
                                            SET created_by_user_id = %s, created_by_name = %s, updated_at = NOW() 
                                            WHERE lead_id IN ({pl_ids})
                                        """, [dest_user_id, dest_user_name] + chunk_ids)

                                    conn.commit()
                            else:
                                if total_updated == 0 and not record_types_to_process:
                                    return jsonify(res), 400

                        # If assigning from disposed leads, revive them by setting is_disposed = 0
                        if source_user_id == "disposed" or view_type == "disposed":
                            for i in range(0, len(lead_uuids), chunk_size):
                                chunk = lead_uuids[i:i + chunk_size]
                                pl = ", ".join(["%s"] * len(chunk))
                                cursor.execute(f"""
                                    UPDATE leads 
                                    SET is_disposed = 0, disposed_by = NULL, disposed_at = NULL 
                                    WHERE lead_uuid IN ({pl})
                                """, chunk)
                            conn.commit()

                    # Standalone / user-created records transfer across all segments
                    standalone_counts = {}
                    if rec_where_sql and dest_user_id is not None and record_types_to_process:
                        if "contacts" in record_types_to_process:
                            cursor.execute(f"""
                                UPDATE contacts 
                                SET created_by_user_id = %s, created_by_name = %s, updated_at = NOW() 
                                WHERE {rec_where_sql}
                            """, [dest_user_id, dest_user_name] + rec_params)
                            cnt = cursor.rowcount
                            if cnt > 0: standalone_counts["Contacts"] = cnt

                        if "sales_orders" in record_types_to_process:
                            cursor.execute(f"""
                                UPDATE sales_orders 
                                SET created_by_user_id = %s, created_by_name = %s, updated_at = NOW() 
                                WHERE {rec_where_sql}
                            """, [dest_user_id, dest_user_name] + rec_params)
                            cnt = cursor.rowcount
                            if cnt > 0: standalone_counts["Sales Orders"] = cnt

                        if "clients" in record_types_to_process:
                            cursor.execute(f"""
                                UPDATE clients 
                                SET created_by_user_id = %s, created_by_name = %s, updated_at = NOW() 
                                WHERE {rec_where_sql}
                            """, [dest_user_id, dest_user_name] + rec_params)
                            cnt = cursor.rowcount
                            if cnt > 0: standalone_counts["Paid Clients"] = cnt

                        if "followups" in record_types_to_process:
                            cursor.execute(f"""
                                UPDATE followups 
                                SET created_by_user_id = %s, created_by_name = %s, updated_at = NOW() 
                                WHERE {rec_where_sql}
                            """, [dest_user_id, dest_user_name] + rec_params)
                            cnt = cursor.rowcount
                            if cnt > 0: standalone_counts["Follow-ups"] = cnt

                        if "free_trials" in record_types_to_process:
                            cursor.execute(f"""
                                UPDATE free_trials 
                                SET created_by_user_id = %s, created_by_name = %s, updated_at = NOW() 
                                WHERE {rec_where_sql}
                            """, [dest_user_id, dest_user_name] + rec_params)
                            cnt = cursor.rowcount
                            if cnt > 0: standalone_counts["Free Trials"] = cnt

                        conn.commit()

                    if total_updated == 0 and not standalone_counts:
                        if pure_lead_statuses and not lead_uuids:
                            return jsonify({"success": False, "message": "No leads found for the selected status(es)."}), 400
                        return jsonify({"success": False, "message": "No leads or records found to transfer."}), 400

                    msg_parts = []
                    if total_updated > 0:
                        msg_parts.append(f"{total_updated} lead(s)")
                    for k, v in standalone_counts.items():
                        msg_parts.append(f"{v} {k}")

                    return jsonify({
                        "success": True,
                        "message": f"Successfully transferred {', '.join(msg_parts)} to {dest_user_name}.",
                        "count": total_updated + sum(standalone_counts.values())
                    })

                elif action == "delete":
                    if lead_uuids:
                        chunk_size = 1000
                        for i in range(0, len(lead_uuids), chunk_size):
                            chunk = lead_uuids[i:i + chunk_size]
                            res = process_delete_lead(
                                logged_user_uuid=logged_uuid,
                                lead_uuids=chunk,
                                ip_address=ip
                            )
                            if res.get("success"):
                                total_deleted += len(chunk)
                            else:
                                if total_deleted == 0 and not record_types_to_process:
                                    return jsonify(res), 400

                    # Standalone / user-created records deletion if requested
                    standalone_counts = {}
                    if rec_where_sql and record_types_to_process:
                        if "contacts" in record_types_to_process:
                            cursor.execute(f"DELETE FROM contacts WHERE {rec_where_sql}", rec_params)
                            cnt = cursor.rowcount
                            if cnt > 0: standalone_counts["Contacts"] = cnt

                        if "sales_orders" in record_types_to_process:
                            cursor.execute(f"DELETE FROM sales_orders WHERE {rec_where_sql}", rec_params)
                            cnt = cursor.rowcount
                            if cnt > 0: standalone_counts["Sales Orders"] = cnt

                        if "clients" in record_types_to_process:
                            cursor.execute(f"DELETE FROM clients WHERE {rec_where_sql}", rec_params)
                            cnt = cursor.rowcount
                            if cnt > 0: standalone_counts["Paid Clients"] = cnt

                        if "followups" in record_types_to_process:
                            cursor.execute(f"DELETE FROM followups WHERE {rec_where_sql}", rec_params)
                            cnt = cursor.rowcount
                            if cnt > 0: standalone_counts["Follow-ups"] = cnt

                        if "free_trials" in record_types_to_process:
                            cursor.execute(f"DELETE FROM free_trials WHERE {rec_where_sql}", rec_params)
                            cnt = cursor.rowcount
                            if cnt > 0: standalone_counts["Free Trials"] = cnt

                        conn.commit()

                    if total_deleted == 0 and not standalone_counts:
                        if pure_lead_statuses and not lead_uuids:
                            return jsonify({"success": False, "message": "No leads found for the selected status(es)."}), 400
                        return jsonify({"success": False, "message": "No leads or records found to delete."}), 400

                    msg_parts = []
                    if total_deleted > 0:
                        msg_parts.append(f"{total_deleted} lead(s)")
                    for k, v in standalone_counts.items():
                        msg_parts.append(f"{v} {k}")

                    return jsonify({
                        "success": True,
                        "message": f"Successfully deleted {', '.join(msg_parts)}.",
                        "count": total_deleted + sum(standalone_counts.values())
                    })

                else:
                    return jsonify({"success": False, "message": f"Invalid action: {action}"}), 400

        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

    @app.route("/reports/user-report/export", endpoint="export_user_report_leads")
    @app.route("/api/user-report/export", endpoint="api_export_user_report_leads")
    @require_user_report_permission
    def export_user_report_leads():
        """
        Exports leads from the user report modal.
        Can filter by:
        - user_id: source user ID or 'unassigned', 'disposed', 'disabled_data', 'deleted_data'
        - batch_id: (optional or 'all')
        - source_id: (optional or 'all')
        - statuses: (optional comma-separated status names)
        """
        user_info = session.get("user", {})
        user_role = str(user_info.get("role_name") or "").lower()
        is_admin = user_info.get("is_admin") == 1 or user_role in ["admin", "super admin", "superadmin"] or user_info.get("id") in [1, 20]

        if not (is_admin or has_permission("global_access_scope", "global_data_export") or has_permission("reports", "user_report")):
            flash("Access Denied: You do not have permission to export leads.", "danger")
            return redirect(url_for("user_report"))

        user_id_raw = (request.args.get("user_id") or "").strip()
        view_type = (request.args.get("view_type") or request.args.get("type") or "").strip().lower()
        batch_id = (request.args.get("batch_id") or "all").strip()
        source_id = (request.args.get("source_id") or "all").strip()
        statuses_raw = (request.args.get("statuses") or "").strip()
        selected_statuses = [s.strip() for s in statuses_raw.split(",") if s.strip()] if statuses_raw else []

        conn = get_db_connection()
        if not conn:
            flash("Database connection error.", "danger")
            return redirect(url_for("user_report"))

        try:
            with conn.cursor() as cursor:
                where_clauses = []
                params = []
                target_label = "all_leads"

                # 1. User Filter
                user_clause = None
                user_params = []
                u_row = None

                if user_id_raw == "disposed" or view_type == "disposed":
                    if user_id_raw == "disposed":
                        user_clause = "l.is_disposed = 1"
                        target_label = "disposed_leads"
                    elif user_id_raw == "unassigned":
                        user_clause = "(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND l.is_disposed = 1"
                        target_label = "unassigned_disposed_leads"
                    elif user_id_raw == "disabled_data":
                        user_clause = """
                            (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                                l.current_owner_user_id IN (SELECT id FROM users WHERE status = 0)
                            )) AND l.is_disposed = 1
                        """
                        target_label = "disabled_user_disposed_leads"
                    elif user_id_raw in ("deleted_data", "old_disabled"):
                        user_clause = """
                            (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                                l.current_owner_user_id NOT IN (SELECT id FROM users)
                            )) AND l.is_disposed = 1
                        """
                        target_label = "deleted_user_disposed_leads"
                    elif user_id_raw:
                        cursor.execute("""
                            SELECT id, user_uuid, full_name, username 
                            FROM users 
                            WHERE id = %s OR user_uuid = %s 
                            LIMIT 1
                        """, (user_id_raw if user_id_raw.isdigit() else -1, user_id_raw))
                        u_row = cursor.fetchone()
                        if u_row:
                            user_clause = "l.current_owner_user_id = %s AND l.is_disposed = 1"
                            user_params = [u_row["id"]]
                            raw_name = u_row.get("full_name") or u_row.get("username") or f"user_{u_row['id']}"
                            target_label = f"{re.sub(r'[^a-zA-Z0-9_-]', '_', raw_name.strip().lower())}_disposed"
                        else:
                            user_clause = "(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND l.is_disposed = 1"
                            target_label = "unassigned_disposed_leads"
                elif user_id_raw == "unassigned":
                    user_clause = "(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)"
                    target_label = "unassigned_leads"
                elif user_id_raw == "disabled_data":
                    user_clause = """
                        (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                            l.current_owner_user_id IN (SELECT id FROM users WHERE status = 0)
                        ))
                    """
                    target_label = "disabled_user_data"
                elif user_id_raw in ("deleted_data", "old_disabled"):
                    user_clause = """
                        (l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id != 0 AND (
                            l.current_owner_user_id NOT IN (SELECT id FROM users)
                        ))
                    """
                    target_label = "deleted_user_data"
                elif user_id_raw:
                    cursor.execute("""
                        SELECT id, user_uuid, full_name, username, status 
                        FROM users 
                        WHERE id = %s OR user_uuid = %s 
                        LIMIT 1
                    """, (user_id_raw if user_id_raw.isdigit() else -1, user_id_raw))
                    u_row = cursor.fetchone()
                    if u_row:
                        if int(u_row.get("status") if u_row.get("status") is not None else 1) == 0:
                            user_clause = "l.current_owner_user_id = %s"
                        else:
                            user_clause = "l.current_owner_user_id = %s AND (l.is_disposed = 0 OR l.is_disposed IS NULL)"
                        user_params = [u_row["id"]]
                        raw_name = u_row.get("full_name") or u_row.get("username") or f"user_{u_row['id']}"
                        target_label = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name.strip().lower())
                    else:
                        user_clause = "(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0) AND (l.is_disposed = 0 OR l.is_disposed IS NULL)"
                        target_label = "unassigned_leads"

                # 2. Batch filter
                if batch_id and batch_id != "all":
                    where_clauses.append("(l.lead_batch_id = %s OR CAST(l.lead_batch_id AS CHAR) = %s)")
                    params.extend([batch_id, batch_id])

                # 3. Source filter
                if source_id and source_id != "all":
                    where_clauses.append("(l.lead_source = %s OR ls_exp.id = %s OR ls_exp.source_name = %s)")
                    params.extend([source_id, source_id, source_id])

                # 4. Status filter (if specific statuses or record categories were passed)
                RECORD_CAT_MAP = {
                    "contacts": "contacts",
                    "contact": "contacts",
                    "sales orders": "so",
                    "sales order": "so",
                    "paid clients": "clients",
                    "paid client": "clients",
                    "follow-ups": "followups",
                    "followups": "followups",
                    "follow-up": "followups",
                    "free trials": "trials",
                    "free trial": "trials"
                }

                # Determine creator filter for record categories (Sales Orders, Clients, etc.)
                if user_id_raw == "disabled_data":
                    rec_creator_sql = "created_by_user_id IN (SELECT id FROM users WHERE status = 0)"
                elif user_id_raw in ("deleted_data", "old_disabled"):
                    rec_creator_sql = "created_by_user_id IS NOT NULL AND created_by_user_id != 0 AND created_by_user_id NOT IN (SELECT id FROM users)"
                elif user_id_raw == "unassigned":
                    rec_creator_sql = "(created_by_user_id IS NULL OR created_by_user_id = 0)"
                elif u_row:
                    rec_creator_sql = f"created_by_user_id = {u_row['id']}"
                elif user_id_raw and user_id_raw.isdigit():
                    rec_creator_sql = f"created_by_user_id = {int(user_id_raw)}"
                else:
                    rec_creator_sql = "1=1"

                pure_lead_statuses = []
                record_categories_selected = []

                if selected_statuses:
                    status_or_parts = []
                    record_cat_parts = []

                    for s in selected_statuses:
                        s_clean = str(s).strip()
                        s_lower = s_clean.lower()
                        if s_lower in RECORD_CAT_MAP:
                            cat = RECORD_CAT_MAP[s_lower]
                            record_categories_selected.append(cat)
                            if cat == "contacts":
                                record_cat_parts.append(f"EXISTS (SELECT 1 FROM contacts cnt_exp WHERE cnt_exp.lead_id = l.id AND cnt_exp.{rec_creator_sql})")
                            elif cat == "so":
                                record_cat_parts.append(f"EXISTS (SELECT 1 FROM sales_orders so_exp WHERE so_exp.lead_id = l.id AND so_exp.{rec_creator_sql})")
                            elif cat == "clients":
                                record_cat_parts.append(f"EXISTS (SELECT 1 FROM clients cl_exp WHERE cl_exp.lead_id = l.id AND cl_exp.{rec_creator_sql})")
                            elif cat == "followups":
                                record_cat_parts.append(f"EXISTS (SELECT 1 FROM followups f_exp WHERE f_exp.lead_id = l.id AND f_exp.{rec_creator_sql})")
                            elif cat == "trials":
                                record_cat_parts.append(f"EXISTS (SELECT 1 FROM free_trials ft_exp WHERE ft_exp.lead_id = l.id AND ft_exp.{rec_creator_sql})")
                        elif s_clean.lower() in ("fresh", "no status", "no_status", ""):
                            pure_lead_statuses.append(s_clean)
                            status_or_parts.append("(l.lead_status IS NULL OR l.lead_status = '' OR l.lead_status = '0' OR l.lead_status = 'No Status' OR st_exp.status_name = 'Fresh')")
                        elif s_clean.startswith("Status id ") and s_clean.endswith(" Deleted"):
                            pure_lead_statuses.append(s_clean)
                            stat_id = s_clean.replace("Status id ", "").replace(" Deleted", "").strip()
                            status_or_parts.append("l.lead_status = %s")
                            params.append(stat_id)
                        elif s_clean.startswith("Status ") and s_clean.endswith(" Deleted"):
                            pure_lead_statuses.append(s_clean)
                            stat_id = s_clean.replace("Status ", "").replace(" Deleted", "").strip()
                            status_or_parts.append("l.lead_status = %s")
                            params.append(stat_id)
                        else:
                            pure_lead_statuses.append(s_clean)
                            status_or_parts.append("(st_exp.status_name = %s OR l.lead_status = %s)")
                            params.extend([s_clean, s_clean])

                    # If ONLY record categories were selected, match by those records directly (do not restrict to owner)
                    if not (record_categories_selected and not pure_lead_statuses):
                        if user_clause:
                            where_clauses.append(user_clause)
                            params.extend(user_params)

                    all_export_parts = status_or_parts + record_cat_parts
                    if all_export_parts:
                        where_clauses.append(f"({' OR '.join(all_export_parts)})")
                else:
                    # Download All
                    rec_or_parts = [
                        f"EXISTS (SELECT 1 FROM contacts cnt_exp WHERE cnt_exp.lead_id = l.id AND cnt_exp.{rec_creator_sql})",
                        f"EXISTS (SELECT 1 FROM sales_orders so_exp WHERE so_exp.lead_id = l.id AND so_exp.{rec_creator_sql})",
                        f"EXISTS (SELECT 1 FROM clients cl_exp WHERE cl_exp.lead_id = l.id AND cl_exp.{rec_creator_sql})",
                        f"EXISTS (SELECT 1 FROM followups f_exp WHERE f_exp.lead_id = l.id AND f_exp.{rec_creator_sql})",
                        f"EXISTS (SELECT 1 FROM free_trials ft_exp WHERE ft_exp.lead_id = l.id AND ft_exp.{rec_creator_sql})"
                    ]
                    if user_clause:
                        where_clauses.append(f"({user_clause} OR {' OR '.join(rec_or_parts)})")
                        params.extend(user_params)

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                export_sql = f"""
                    SELECT 
                        l.id AS lead_id,
                        l.lead_uuid,
                        COALESCE(b.batch_name, '') AS batch_name,
                        COALESCE(l.name, '') AS name,
                        l.mobile_number,
                        COALESCE(l.email, '') AS email,
                        COALESCE(l.address, '') AS address,
                        COALESCE(ls_exp.source_name, 'No Source') AS source_name,
                        CASE 
                            WHEN (l.lead_status IS NULL OR l.lead_status = '' OR l.lead_status = '0' OR l.lead_status = 'No Status') THEN 'Fresh'
                            WHEN st_exp.status_name IS NOT NULL THEN st_exp.status_name
                            WHEN l.lead_status REGEXP '^[0-9]+$' THEN CONCAT('Status id ', l.lead_status, ' Deleted')
                            ELSE CONCAT('Status ', l.lead_status, ' Deleted')
                        END AS status_name,
                        CASE WHEN l.call_status = 1 THEN 'Called' ELSE 'Not Called' END AS call_status_label,
                        COALESCE(u.full_name, u.username, 'Unassigned') AS owner_name,
                        CASE WHEN (l.is_disposed = 1 OR l.disposed_by IS NOT NULL OR l.disposed_at IS NOT NULL) THEN 'Yes' ELSE 'No' END AS disposed_label,
                        (CASE WHEN EXISTS (SELECT 1 FROM contacts cnt WHERE cnt.lead_id = l.id) THEN 'Yes' ELSE 'No' END) AS has_contact,
                        (CASE WHEN EXISTS (SELECT 1 FROM followups f WHERE f.lead_id = l.id) THEN 'Yes' ELSE 'No' END) AS has_followup,
                        (CASE WHEN EXISTS (SELECT 1 FROM free_trials ft WHERE ft.lead_id = l.id) THEN 'Yes' ELSE 'No' END) AS has_free_trial,
                        (CASE WHEN EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id) THEN 'Yes' ELSE 'No' END) AS has_so,
                        (CASE WHEN EXISTS (SELECT 1 FROM clients cl WHERE cl.lead_id = l.id) THEN 'Yes' ELSE 'No' END) AS is_paid_client,
                        COALESCE(l.comment, '') AS comment,
                        l.assigned_at,
                        l.created_at,
                        l.updated_at,
                        l.disposed_at
                    FROM leads l
                    LEFT JOIN lead_batches b ON b.id = l.lead_batch_id
                    LEFT JOIN lead_sources ls_exp ON (ls_exp.id = l.lead_source OR ls_exp.source_uuid = l.lead_source OR ls_exp.source_name = l.lead_source)
                    LEFT JOIN lead_statuses st_exp ON (st_exp.id = l.lead_status OR st_exp.status_name = l.lead_status)
                    LEFT JOIN users u ON u.id = l.current_owner_user_id
                    WHERE {where_sql}
                    ORDER BY l.id DESC
                """
                cursor.execute(export_sql, params)
                leads = cursor.fetchall() or []

                rows = []
                for idx, item in enumerate(leads, 1):
                    raw_mob = item.get("mobile_number") or ""
                    dec_mob = decrypt_mobile(raw_mob) if raw_mob else ""
                    
                    assigned_dt = item.get("assigned_at")
                    assigned_fmt = assigned_dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(assigned_dt, "strftime") else (str(assigned_dt) if assigned_dt else "")

                    created_dt = item.get("created_at")
                    created_fmt = created_dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(created_dt, "strftime") else (str(created_dt) if created_dt else "")

                    updated_dt = item.get("updated_at")
                    updated_fmt = updated_dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(updated_dt, "strftime") else (str(updated_dt) if updated_dt else "")

                    disposed_dt = item.get("disposed_at")
                    disposed_fmt = disposed_dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(disposed_dt, "strftime") else (str(disposed_dt) if disposed_dt else "")

                    raw_comment = str(item.get("comment") or "").strip()
                    clean_comment = " ".join(raw_comment.split())

                    rows.append({
                        "S.No": idx,
                        "Lead ID": item["lead_id"],
                        "Lead UUID": item["lead_uuid"],
                        "Name": item["name"],
                        "Mobile Number": dec_mob,
                        "Email": item["email"],
                        "Address": item["address"],
                        "Batch Name": item["batch_name"],
                        "Lead Source": item["source_name"],
                        "Lead Status": item["status_name"],
                        "Call Status": item["call_status_label"],
                        "Assigned Owner": item["owner_name"],
                        "Disposed": item["disposed_label"],
                        "Contact": item["has_contact"],
                        "Follow-up": item["has_followup"],
                        "Free Trial": item["has_free_trial"],
                        "Sales Order": item["has_so"],
                        "Paid Client": item["is_paid_client"],
                        "Comment": clean_comment,
                        "Assigned At": assigned_fmt,
                        "Created At": created_fmt,
                        "Updated At": updated_fmt,
                        "Disposed At": disposed_fmt,
                    })

                safe_user = re.sub(r"[^a-zA-Z0-9_-]", "_", target_label.strip().lower())
                filename = f"user_report_{safe_user}_leads.csv"
                fieldnames = [
                    "S.No", "Lead ID", "Lead UUID", "Name", "Mobile Number", "Email", "Address",
                    "Batch Name", "Lead Source", "Lead Status", "Call Status", "Assigned Owner",
                    "Disposed", "Contact", "Follow-up", "Free Trial", "Sales Order", "Paid Client",
                    "Comment", "Assigned At", "Created At", "Updated At", "Disposed At"
                ]
                return csv_response(filename, fieldnames, rows)
        finally:
            conn.close()


# Aliases for backwards compatibility
lead_monitor_routes = user_report_routes
