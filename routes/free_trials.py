from datetime import datetime
from flask import render_template, session, jsonify, request, url_for

from config import get_db_connection
from utils.permissions import require_permission
from routes.lead_action import get_action_permissions, get_current_user
from routes.lead_upload_common import serialize_grid_rows
from routes.settings_helpers import (
    decrypt_mobile, 
    fetch_owner_filter_options,
    fetch_logged_user_settings,
    fetch_last_dialed_lead_uuid,
    apply_mobile_and_last_dialed_context,
    resolve_selected_owner
)


def fetch_free_trials_data(cursor, user_uuid, status_filter="today", date_preset=None, start_date="", end_date="", trial_status_filter="all", lead_status_filter="all", source_filter="all", owner_filter="all", search_query="", target_lead_uuid="", page=1, page_size=10):
    user_info = session.get("user") or {}
    is_admin = bool(user_info.get("is_admin")) or str(user_info.get("role_name", "")).lower() == "admin"
    from utils.permissions import has_permission
    has_global_permission = has_permission('global_access_scope', 'global_data_access')
    is_global = is_admin or has_global_permission

    user = get_current_user(cursor, user_uuid)
    permissions = get_action_permissions(user)

    owner_context = fetch_owner_filter_options(cursor, user_uuid)
    owners = owner_context["owners"]
    
    allowed_user_ids = None
    if not is_global:
        allowed_user_ids = owner_context["allowed_user_ids"]

    # Fetch active lead statuses & sources for filter bar
    cursor.execute("SELECT id, status_name FROM lead_statuses ORDER BY id ASC")
    lead_statuses = cursor.fetchall() or []

    cursor.execute("SELECT id, source_name FROM lead_sources ORDER BY id ASC")
    lead_sources = cursor.fetchall() or []

    # 1. KPIs (Filtered by allowed_user_ids if restricted)
    kpi_sql = """
        SELECT 
            COUNT(*) AS total_trials,
            COALESCE(SUM(CASE WHEN (end_date IS NULL OR end_date >= NOW()) AND trial_status != 'cancelled' THEN 1 ELSE 0 END), 0) AS active_trials,
            COALESCE(SUM(CASE WHEN end_date < NOW() OR trial_status = 'expired' THEN 1 ELSE 0 END), 0) AS expired_trials,
            COALESCE(SUM(CASE WHEN ft.trial_status = 'converted' OR EXISTS(SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id) THEN 1 ELSE 0 END), 0) AS converted_trials
        FROM free_trials ft
        JOIN leads l ON l.id = ft.lead_id
        WHERE 1=1
    """
    kpi_params = []
    if allowed_user_ids:
        placeholders = ", ".join(["%s"] * len(allowed_user_ids))
        kpi_sql += f" AND (l.current_owner_user_id IN ({placeholders}) OR l.created_by IN ({placeholders}))"
        kpi_params.extend(allowed_user_ids)
        kpi_params.extend(allowed_user_ids)

    cursor.execute(kpi_sql, kpi_params)
    kpis = cursor.fetchone() or {
        "total_trials": 0, "active_trials": 0, "expired_trials": 0, "converted_trials": 0
    }

    # 2. Detailed Free Trials List - Where Clauses
    where_sql = " WHERE 1=1"
    params = []
    
    effective_preset = date_preset if date_preset else (status_filter if status_filter in ['today'] else 'today')

    if status_filter == "active":
        where_sql += " AND (ft.end_date IS NULL OR ft.end_date >= NOW()) AND ft.trial_status != 'cancelled'"
    elif status_filter == "expired":
        where_sql += " AND (ft.end_date < NOW() OR ft.trial_status = 'expired')"
    elif status_filter == "converted":
        where_sql += " AND (ft.trial_status = 'converted' OR EXISTS(SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id))"

    if effective_preset == "today":
        where_sql += " AND DATE(ft.start_date) = CURRENT_DATE()"
    elif effective_preset == "yesterday":
        where_sql += " AND DATE(ft.start_date) = CURRENT_DATE() - INTERVAL 1 DAY"
    elif effective_preset == "this_week":
        where_sql += " AND DATE(ft.start_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL WEEKDAY(CURRENT_DATE()) DAY)"
    elif effective_preset == "this_month":
        where_sql += " AND DATE(ft.start_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL DAYOFMONTH(CURRENT_DATE()) - 1 DAY)"
    elif effective_preset == "custom" and start_date and end_date:
        where_sql += " AND DATE(ft.start_date) >= %s AND DATE(ft.start_date) <= %s"
        params.extend([start_date, end_date])

    if trial_status_filter and trial_status_filter.lower() != "all":
        where_sql += " AND LOWER(ft.trial_status) = %s"
        params.append(trial_status_filter.lower())

    if lead_status_filter and lead_status_filter.lower() != "all":
        where_sql += " AND (LOWER(st.status_name) = %s OR LOWER(l.lead_status) = %s)"
        params.extend([lead_status_filter.lower(), lead_status_filter.lower()])

    if source_filter and source_filter.lower() != "all":
        if str(source_filter).isdigit():
            where_sql += " AND (ls.id = %s OR l.lead_source = %s)"
            params.extend([int(source_filter), str(source_filter)])
        else:
            where_sql += " AND (LOWER(ls.source_name) = %s OR LOWER(l.lead_source) = %s)"
            params.extend([source_filter.lower(), source_filter.lower()])

    if owner_filter and owner_filter.lower() != "all":
        if owner_filter.lower() == "unassigned":
            where_sql += " AND (l.current_owner_user_id IS NULL OR u_owner.id IS NULL)"
        else:
            where_sql += " AND u_owner.user_uuid = %s"
            params.append(owner_filter)

    if search_query:
        term = f"%{search_query.strip().lower()}%"
        where_sql += " AND (LOWER(l.name) LIKE %s OR LOWER(l.mobile_number) LIKE %s OR LOWER(l.email) LIKE %s OR LOWER(COALESCE(ft.notes, '')) LIKE %s OR LOWER(COALESCE(ft.trial_name, '')) LIKE %s)"
        params.extend([term, term, term, term, term])

    if allowed_user_ids:
        placeholders = ", ".join(["%s"] * len(allowed_user_ids))
        where_sql += f" AND (l.current_owner_user_id IN ({placeholders}) OR l.created_by IN ({placeholders}))"
        params.extend(allowed_user_ids)
        params.extend(allowed_user_ids)

    if target_lead_uuid:
        where_sql += " AND (l.lead_uuid = %s OR l.id = %s)"
        params.extend([target_lead_uuid, int(target_lead_uuid) if str(target_lead_uuid).isdigit() else -1])

    # Count Query
    count_sql = """
        SELECT COUNT(*) AS total_count
        FROM free_trials ft
        JOIN leads l ON l.id = ft.lead_id
        LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)
        LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_name = l.lead_status)
        LEFT JOIN users u_creator ON u_creator.id = ft.created_by_user_id
        LEFT JOIN users u_owner ON u_owner.id = l.current_owner_user_id
    """ + where_sql

    cursor.execute(count_sql, params)
    count_row = cursor.fetchone()
    total_count = count_row["total_count"] if count_row else 0

    # Data Select Query
    select_sql = """
        SELECT
            ft.id AS trial_id,
            ft.free_trial_uuid,
            COALESCE(ft.trial_name, 'Free Trial') AS trial_name,
            ft.start_date,
            ft.end_date,
            ft.trial_status,
            COALESCE(ft.notes, '') AS notes,
            ft.created_at,
            l.id AS lead_id,
            l.lead_uuid,
            COALESCE(l.name, 'No Name') AS lead_name,
            l.mobile_number,
            l.email,
            l.address,
            l.call_status,
            l.lead_status AS current_lead_status_id,
            COALESCE(ls.source_name, 'No Source') AS lead_source,
            COALESCE(st.status_name, 'No Status') AS lead_status,
            COALESCE(st.id, 0) AS lead_status_id,
            COALESCE(st.status_tone, 'slate') AS status_tone,
            COALESCE(st.status_tone, 'slate') AS status_color,
            (EXISTS(SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id)) AS has_so,
            (EXISTS(SELECT 1 FROM clients c WHERE c.lead_id = l.id)) AS is_paid_client,
            COALESCE(u_creator.full_name, ft.created_by_name, 'System') AS creator_name,
            COALESCE(u_owner.full_name, 'Unassigned') AS owner_name,
            u_owner.user_uuid AS owner_uuid
        FROM free_trials ft
        JOIN leads l ON l.id = ft.lead_id
        LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)
        LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_name = l.lead_status)
        LEFT JOIN users u_creator ON u_creator.id = ft.created_by_user_id
        LEFT JOIN users u_owner ON u_owner.id = l.current_owner_user_id
    """ + where_sql + " ORDER BY ft.id DESC"
    
    data_params = list(params)
    page_size_val = int(page_size) if str(page_size).isdigit() else 10
    page_val = int(page) if str(page).isdigit() else 1

    if page_size_val > 0:
        offset_val = max(0, (page_val - 1) * page_size_val)
        select_sql += " LIMIT %s OFFSET %s"
        data_params.extend([page_size_val, offset_val])

    cursor.execute(select_sql, data_params)
    rows = cursor.fetchall() or []

    user_settings = fetch_logged_user_settings(cursor, user_uuid)
    last_dialed_lead_uuid = fetch_last_dialed_lead_uuid(cursor, user_uuid)

    for row in rows:
        apply_mobile_and_last_dialed_context(row, user_settings, last_dialed_lead_uuid)
        row["client_code"] = f"{row['lead_id']}"
        
        # Keep old mobile formatting if missing from apply_mobile_and_last_dialed_context
        if "decrypted_mobile" not in row:
            row["decrypted_mobile"] = decrypt_mobile(row["mobile_number"]) if permissions["can_view_mobile"] else "Hidden"

        if row.get("start_date"):
            row["start_date"] = str(row["start_date"])
        if row.get("end_date"):
            row["end_date"] = str(row["end_date"])
        if row.get("created_at"):
            c_val = row["created_at"]
            row["created_at_fmt"] = c_val.strftime("%d %b %Y, %I:%M %p") if hasattr(c_val, "strftime") else str(c_val)
            row["created_at"] = str(c_val)
        else:
            row["created_at_fmt"] = ""

    return {
        "kpis": kpis,
        "trials": serialize_grid_rows(rows),
        "owners": owners,
        "lead_statuses": lead_statuses,
        "lead_sources": lead_sources,
        "total_count": total_count,
        "page": page_val,
        "page_size": page_size_val,
    }


def free_trial_routes(app):

    @app.route("/free-trials", endpoint="all_free_trials")
    def all_free_trials():
        from flask import flash, redirect, url_for
        flash("The Free Trials module has been removed.", "info")
        return redirect(url_for("dashboard"))

    @app.route("/api/free-trials/list", methods=["GET", "POST"], endpoint="api_free_trials_list")
    def api_free_trials_list():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        payload = request.get_json(silent=True) or request.form or request.args or {}
        status_filter = payload.get("status_filter", payload.get("mode", "today"))
        date_preset = payload.get("date_preset", "")
        start_date = payload.get("start_date", "")
        end_date = payload.get("end_date", "")
        trial_status = payload.get("trial_status", payload.get("trial_status_filter", "all"))
        lead_status = payload.get("lead_status", "all")
        source = payload.get("source", payload.get("source_filter", "all"))
        owner = payload.get("owner", payload.get("owner_filter", "all"))
        search = payload.get("search", payload.get("search_query", ""))
        page = int(payload.get("page", 1)) if str(payload.get("page", 1)).isdigit() else 1
        page_size = int(payload.get("page_size", 10)) if str(payload.get("page_size", 10)).isdigit() else 10

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                data = fetch_free_trials_data(
                    cursor,
                    logged_user_uuid,
                    status_filter=status_filter,
                    date_preset=date_preset,
                    start_date=start_date,
                    end_date=end_date,
                    trial_status_filter=trial_status,
                    lead_status_filter=lead_status,
                    source_filter=source,
                    owner_filter=owner,
                    search_query=search,
                    page=page,
                    page_size=page_size
                )
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "trials": data["trials"],
            "kpis": data["kpis"],
            "count": len(data["trials"]),
            "total_count": data["total_count"],
            "page": data["page"],
            "page_size": data["page_size"]
        })


    @app.route("/free-trials/today", endpoint="today_free_trials")
    def today_free_trials():
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                data = fetch_free_trials_data(cursor, session.get("user_uuid"), status_filter="today")
        finally:
            conn.close()

        return render_template(
            "free_trials/today_free_trials.html",
            kpis=data["kpis"],
            trials=data["trials"],
            owners=data["owners"],
            lead_statuses=data["lead_statuses"],
            lead_sources=data["lead_sources"],
            logged_user_uuid=session.get("user_uuid"),
            selected_owner=resolve_selected_owner(session.get("user_uuid")),
            active_group="free_trials",
            active_page="today_free_trials",
            page_title="Today Free Trials",
            page_heading="Today Free Trials",
            mode="today",
        )

    @app.route("/free-trials/active", endpoint="active_free_trials")
    def active_free_trials():
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                data = fetch_free_trials_data(cursor, session.get("user_uuid"), status_filter="active")
        finally:
            conn.close()

        return render_template(
            "free_trials/active_free_trials.html",
            kpis=data["kpis"],
            trials=data["trials"],
            owners=data["owners"],
            lead_statuses=data["lead_statuses"],
            lead_sources=data["lead_sources"],
            logged_user_uuid=session.get("user_uuid"),
            selected_owner=resolve_selected_owner(session.get("user_uuid")),
            active_group="free_trials",
            active_page="active_free_trials",
            page_title="Active Trials",
            page_heading="Active Trials",
            mode="active",
        )

    @app.route("/free-trials/expired", endpoint="expired_free_trials")
    def expired_free_trials():
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                data = fetch_free_trials_data(cursor, session.get("user_uuid"), status_filter="expired")
        finally:
            conn.close()

        return render_template(
            "free_trials/expired_free_trials.html",
            kpis=data["kpis"],
            trials=data["trials"],
            owners=data["owners"],
            lead_statuses=data["lead_statuses"],
            lead_sources=data["lead_sources"],
            logged_user_uuid=session.get("user_uuid"),
            selected_owner=resolve_selected_owner(session.get("user_uuid")),
            active_group="free_trials",
            active_page="expired_free_trials",
            page_title="Expired Trials",
            page_heading="Expired Trials",
            mode="expired",
        )

    @app.route("/free-trials/converted", endpoint="converted_free_trials")
    def converted_free_trials():
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                data = fetch_free_trials_data(cursor, session.get("user_uuid"), status_filter="converted")
        finally:
            conn.close()

        return render_template(
            "free_trials/converted_free_trials.html",
            kpis=data["kpis"],
            trials=data["trials"],
            owners=data["owners"],
            lead_statuses=data["lead_statuses"],
            lead_sources=data["lead_sources"],
            logged_user_uuid=session.get("user_uuid"),
            selected_owner=resolve_selected_owner(session.get("user_uuid")),
            active_group="free_trials",
            active_page="converted_free_trials",
            page_title="Converted Trials",
            page_heading="Converted Trials",
            mode="converted",
        )

    @app.route("/api/free-trials/delete", methods=["POST"], endpoint="api_delete_free_trial")
    @require_permission("free_trials", "delete")
    def api_delete_free_trial():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Authentication required."}), 401

        payload = request.get_json(silent=True) or {}
        free_trial_uuids = payload.get("free_trial_uuids", [])
        
        if not free_trial_uuids:
            return jsonify({"success": False, "message": "Please select at least one free trial to delete."}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                placeholders = ", ".join(["%s"] * len(free_trial_uuids))
                cursor.execute(f"DELETE FROM free_trials WHERE free_trial_uuid IN ({placeholders})", tuple(free_trial_uuids))
                conn.commit()
                deleted_count = cursor.rowcount
        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({"success": False, "message": f"Error deleting free trials: {str(e)}"}), 500
        finally:
            if conn:
                conn.close()

        return jsonify({"success": True, "message": f"Successfully deleted {deleted_count} free trial(s)."})
        
    # Maintain old routes for backward compatibility for a while to prevent 404s if linked elsewhere
    @app.route("/free-trials", endpoint="free_trials")
    def free_trials_legacy():
        return redirect(url_for('all_free_trials'))

