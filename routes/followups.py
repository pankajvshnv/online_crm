from datetime import datetime
from flask import flash, jsonify, redirect, render_template, request, session, url_for

from config import get_db_connection
from routes.lead_upload_common import serialize_grid_rows
from utils.permissions import require_permission
from routes.settings_helpers import (
    apply_mobile_and_last_dialed_context,
    fetch_last_dialed_lead_uuid,
    fetch_logged_user_settings,
    fetch_owner_filter_options,
    resolve_selected_owner,
)


def get_followups_data(cursor, logged_user_uuid, mode="today", date_preset=None, start_date="", end_date="", status_filter="all", lead_status_filter="all", source_filter="all", owner_filter="all", search_query="", target_lead_uuid="", page=1, page_size=10):
    user_info = session.get("user") or {}
    is_admin = bool(user_info.get("is_admin")) or str(user_info.get("role_name", "")).lower() == "admin"
    from utils.permissions import has_permission
    has_global_permission = has_permission('global_access_scope', 'global_data_access')
    is_global = is_admin or has_global_permission

    owner_context = fetch_owner_filter_options(cursor, logged_user_uuid)
    owners = owner_context["owners"]
    
    allowed_user_ids = None
    if not is_global:
        allowed_user_ids = owner_context["allowed_user_ids"]

    # Fetch active lead statuses & sources
    cursor.execute("SELECT id, status_name FROM lead_statuses ORDER BY id ASC")
    lead_statuses = cursor.fetchall() or []

    cursor.execute("SELECT id, source_name FROM lead_sources ORDER BY id ASC")
    lead_sources = cursor.fetchall() or []

    where_sql = " WHERE 1=1"
    params = []

    # Date filter mode (Pushed directly to SQL query)
    effective_preset = date_preset if date_preset else (mode if mode in ['today', 'upcoming', 'missed'] else 'today')

    if mode == "upcoming":
        where_sql += " AND DATE(f.followup_date) > CURRENT_DATE() AND f.followup_status != 'completed'"
    elif mode == "missed":
        where_sql += " AND DATE(f.followup_date) < CURRENT_DATE() AND f.followup_status != 'completed'"
    elif effective_preset == "today":
        where_sql += " AND DATE(f.followup_date) = CURRENT_DATE()"
    elif effective_preset == "yesterday":
        where_sql += " AND DATE(f.followup_date) = CURRENT_DATE() - INTERVAL 1 DAY"
    elif effective_preset == "this_week":
        where_sql += " AND DATE(f.followup_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL WEEKDAY(CURRENT_DATE()) DAY)"
    elif effective_preset == "this_month":
        where_sql += " AND DATE(f.followup_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL DAYOFMONTH(CURRENT_DATE()) - 1 DAY)"
    elif effective_preset == "custom" and start_date and end_date:
        where_sql += " AND DATE(f.followup_date) >= %s AND DATE(f.followup_date) <= %s"
        params.extend([start_date, end_date])

    if status_filter and status_filter.lower() != "all":
        where_sql += " AND LOWER(f.followup_status) = %s"
        params.append(status_filter.lower())

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
        where_sql += " AND (LOWER(l.name) LIKE %s OR LOWER(l.mobile_number) LIKE %s OR LOWER(l.email) LIKE %s OR LOWER(COALESCE(f.notes, '')) LIKE %s OR LOWER(COALESCE(ls.source_name, '')) LIKE %s)"
        params.extend([term, term, term, term, term])

    if allowed_user_ids:
        placeholders = ", ".join(["%s"] * len(allowed_user_ids))
        where_sql += f" AND (l.current_owner_user_id IN ({placeholders}) OR l.created_by IN ({placeholders}))"
        params.extend(allowed_user_ids)
        params.extend(allowed_user_ids)

    if target_lead_uuid:
        where_sql += " AND (l.lead_uuid = %s OR l.id = %s)"
        params.extend([target_lead_uuid, int(target_lead_uuid) if str(target_lead_uuid).isdigit() else -1])

    # 1. Total Count Query (Filtered matching followups grouped by lead_id)
    count_sql = f"""
        SELECT COUNT(*) AS total_count
        FROM (
            SELECT f.lead_id, MAX(f.id) AS max_followup_id
            FROM followups f
            JOIN leads l ON l.id = f.lead_id
            LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)
            LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_name = l.lead_status)
            LEFT JOIN users u_owner ON u_owner.id = l.current_owner_user_id
            LEFT JOIN users u_creator ON u_creator.id = f.created_by_user_id
            {where_sql}
            GROUP BY f.lead_id
        ) latest_f
    """

    cursor.execute(count_sql, params)
    count_row = cursor.fetchone()
    total_count = count_row["total_count"] if count_row else 0

    # 2. Main Data Query (Filtered matching followups grouped by lead_id)
    select_sql = f"""
        SELECT 
            f.id AS followup_id,
            f.followup_uuid,
            f.followup_date,
            f.followup_type,
            f.followup_status,
            COALESCE(f.notes, '') AS notes,
            f.completed_at,
            f.created_at,
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
            COALESCE(u_owner.full_name, 'Unassigned') AS owner_name,
            u_owner.user_uuid AS owner_uuid,
            COALESCE(u_creator.full_name, f.created_by_name, 'System') AS creator_name
        FROM (
            SELECT f.lead_id, MAX(f.id) AS max_followup_id
            FROM followups f
            JOIN leads l ON l.id = f.lead_id
            LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)
            LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_name = l.lead_status)
            LEFT JOIN users u_owner ON u_owner.id = l.current_owner_user_id
            LEFT JOIN users u_creator ON u_creator.id = f.created_by_user_id
            {where_sql}
            GROUP BY f.lead_id
        ) latest_f
        JOIN followups f ON f.id = latest_f.max_followup_id
        JOIN leads l ON l.id = f.lead_id
        LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)
        LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_name = l.lead_status)
        LEFT JOIN users u_owner ON u_owner.id = l.current_owner_user_id
        LEFT JOIN users u_creator ON u_creator.id = f.created_by_user_id
        ORDER BY f.followup_date DESC, f.id DESC
    """

    data_params = list(params)
    page_size_val = int(page_size) if str(page_size).isdigit() else 10
    page_val = int(page) if str(page).isdigit() else 1

    if page_size_val > 0:
        offset_val = max(0, (page_val - 1) * page_size_val)
        select_sql += " LIMIT %s OFFSET %s"
        data_params.extend([page_size_val, offset_val])

    cursor.execute(select_sql, data_params)
    followups = cursor.fetchall() or []

    user_settings = fetch_logged_user_settings(cursor, logged_user_uuid)
    last_dialed_lead_uuid = fetch_last_dialed_lead_uuid(cursor, logged_user_uuid)

    for f in followups:
        apply_mobile_and_last_dialed_context(f, user_settings, last_dialed_lead_uuid)
        f["client_code"] = f"{f['lead_id']}"
        if f.get("followup_date"):
            f["followup_date_fmt"] = f["followup_date"].strftime("%d %b %Y, %I:%M %p")
            f["followup_time_fmt"] = f["followup_date"].strftime("%I:%M %p")
        else:
            f["followup_date_fmt"] = "N/A"
            f["followup_time_fmt"] = "N/A"

        if f.get("created_at"):
            f["created_at_fmt"] = f["created_at"].strftime("%d %b %Y, %I:%M %p")
        else:
            f["created_at_fmt"] = "N/A"

    return {
        "followups": followups,
        "owners": owners,
        "lead_statuses": lead_statuses,
        "lead_sources": lead_sources,
        "total_count": total_count,
        "page": page_val,
        "page_size": page_size_val,
    }


def followup_routes(app):
    @app.route("/followups/today", endpoint="today_followups")
    def today_followups():
        return redirect(url_for("all_followups"))

    @app.route("/followups/upcoming", endpoint="upcoming_followups")
    def upcoming_followups():
        return redirect(url_for("all_followups"))

    @app.route("/followups/missed", endpoint="missed_followups")
    def missed_followups():
        return redirect(url_for("all_followups"))

    @app.route("/followups", endpoint="all_followups")
    def all_followups():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                data = get_followups_data(cursor, logged_user_uuid, mode="today")
        finally:
            conn.close()

        return render_template(
            "followups/all_followups.html",
            followups=data["followups"],
            owners=data["owners"],
            lead_statuses=data["lead_statuses"],
            lead_sources=data["lead_sources"],
            logged_user_uuid=logged_user_uuid,
            selected_owner=resolve_selected_owner(logged_user_uuid),
            active_group="followups",
            active_page="all_followups",
            page_title="Follow-ups",
            page_heading="Follow-ups",
            mode="today",
        )

    @app.route("/api/followups/list", methods=["GET", "POST"], endpoint="api_followups_list")
    def api_followups_list():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        payload = request.get_json(silent=True) or request.form or request.args or {}
        mode = payload.get("mode", "today")
        date_preset = payload.get("date_preset", "today")
        start_date = payload.get("start_date", "")
        end_date = payload.get("end_date", "")
        status = payload.get("status", "all")
        lead_status = payload.get("lead_status", "all")
        source = payload.get("source", "all")
        owner = payload.get("owner", "all")
        search = payload.get("search", "")
        page = int(payload.get("page", 1)) if str(payload.get("page", 1)).isdigit() else 1
        page_size = int(payload.get("page_size", 10)) if str(payload.get("page_size", 10)).isdigit() else 10

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                data = get_followups_data(
                    cursor,
                    logged_user_uuid,
                    mode=mode,
                    date_preset=date_preset,
                    start_date=start_date,
                    end_date=end_date,
                    status_filter=status,
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
            "followups": serialize_grid_rows(data["followups"]),
            "count": len(data["followups"]),
            "total_count": data["total_count"],
            "page": data["page"],
            "page_size": data["page_size"]
        })


    @app.route("/api/followups/complete", methods=["POST"], endpoint="api_complete_followup")
    def api_complete_followup():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Authentication required."}), 401

        payload = request.get_json(silent=True) or {}
        followup_uuid = payload.get("followup_uuid")
        if not followup_uuid:
            return jsonify({"success": False, "message": "Follow-up ID missing."}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE followups 
                    SET followup_status = 'completed', completed_at = NOW(), updated_at = NOW() 
                    WHERE followup_uuid = %s OR id = %s
                """, (followup_uuid, int(followup_uuid) if str(followup_uuid).isdigit() else -1))
                conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "message": "Follow-up marked as completed!"})

    @app.route("/api/followups/delete", methods=["POST"], endpoint="api_delete_followup")
    @require_permission("followups", "delete")
    def api_delete_followup():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Authentication required."}), 401

        payload = request.get_json(silent=True) or {}
        followup_uuids = [u for u in payload.get("followup_uuids", []) if u]
        lead_uuids = [u for u in payload.get("lead_uuids", []) if u]
        
        if not followup_uuids and not lead_uuids:
            return jsonify({"success": False, "message": "Please select at least one follow-up to delete."}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                deleted_count = 0
                if followup_uuids:
                    placeholders = ", ".join(["%s"] * len(followup_uuids))
                    cursor.execute(f"DELETE FROM followups WHERE followup_uuid IN ({placeholders})", tuple(followup_uuids))
                    deleted_count += cursor.rowcount
                elif lead_uuids:
                    placeholders = ", ".join(["%s"] * len(lead_uuids))
                    cursor.execute(f"DELETE FROM followups WHERE lead_id IN (SELECT id FROM leads WHERE lead_uuid IN ({placeholders}))", tuple(lead_uuids))
                    deleted_count += cursor.rowcount

                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({"success": False, "message": f"Error deleting followups: {str(e)}"}), 500
        finally:
            if conn:
                conn.close()

        return jsonify({"success": True, "message": f"Successfully deleted {deleted_count} follow-up(s)."})


    @app.route("/api/followups/update", methods=["POST"], endpoint="api_update_followup")
    def api_update_followup():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Authentication required."}), 401

        payload = request.get_json(silent=True) or {}
        followup_uuid = payload.get("followup_uuid")
        lead_uuid = payload.get("lead_uuid")
        status = payload.get("status", "completed")
        remarks = payload.get("remarks", "").strip()
        next_followup_date = payload.get("next_followup_date", "").strip()
        lead_status = payload.get("lead_status", "")

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 1. Update current followup status & notes
                if followup_uuid:
                    cursor.execute("""
                        UPDATE followups 
                        SET followup_status = %s, 
                            notes = CASE WHEN %s != '' THEN %s ELSE notes END,
                            completed_at = CASE WHEN %s = 'completed' THEN NOW() ELSE completed_at END,
                            updated_at = NOW() 
                        WHERE followup_uuid = %s OR id = %s
                    """, (status, remarks, remarks, status, followup_uuid, int(followup_uuid) if str(followup_uuid).isdigit() else -1))

                # 2. Get lead_id from lead_uuid or followup
                lead_id = None
                if lead_uuid:
                    cursor.execute("SELECT id FROM leads WHERE lead_uuid = %s OR id = %s", (lead_uuid, int(lead_uuid) if str(lead_uuid).isdigit() else -1))
                    row = cursor.fetchone()
                    if row:
                        lead_id = row["id"]

                if not lead_id and followup_uuid:
                    cursor.execute("SELECT lead_id FROM followups WHERE followup_uuid = %s OR id = %s", (followup_uuid, int(followup_uuid) if str(followup_uuid).isdigit() else -1))
                    row = cursor.fetchone()
                    if row:
                        lead_id = row["lead_id"]

                # 3. Update lead status if provided
                if lead_id and lead_status:
                    cursor.execute("UPDATE leads SET lead_status = %s, updated_at = NOW() WHERE id = %s", (lead_status, lead_id))

                # 4. If status is 'rescheduled' and next_followup_date provided, create new followup record!
                if status == "rescheduled" and lead_id and next_followup_date:
                    import uuid
                    new_uuid = f"FOL{uuid.uuid4().hex[:12].upper()}"
                    cursor.execute("SELECT id, full_name FROM users WHERE user_uuid = %s LIMIT 1", (logged_user_uuid,))
                    resched_user = cursor.fetchone()
                    resched_user_id = resched_user["id"] if resched_user else None
                    resched_user_name = resched_user["full_name"] if resched_user else "System"
                    cursor.execute("""
                        INSERT INTO followups (followup_uuid, lead_id, created_by_user_id, created_by_name, followup_date, followup_type, followup_status, notes)
                        VALUES (%s, %s, %s, %s, %s, 'Call', 'pending', %s)
                    """, (new_uuid, lead_id, resched_user_id, resched_user_name, next_followup_date, remarks or 'Rescheduled follow-up'))

                conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

        return jsonify({"success": True, "message": "Follow-up updated successfully!"})

    @app.route("/api/followups/history/<lead_uuid>", methods=["GET"], endpoint="api_followup_history")
    def api_followup_history(lead_uuid):
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Authentication required."}), 401

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, lead_uuid, name, mobile_number, email
                    FROM leads
                    WHERE lead_uuid = %s OR id = %s
                    LIMIT 1
                """, (lead_uuid, int(lead_uuid) if str(lead_uuid).isdigit() else -1))
                lead = cursor.fetchone()

                if not lead:
                    return jsonify({"success": False, "message": "Lead record not found."}), 404

                cursor.execute("""
                    SELECT 
                        f.id AS followup_id,
                        f.followup_uuid,
                        f.followup_date,
                        f.followup_type,
                        f.followup_status,
                        COALESCE(f.notes, '') AS notes,
                        f.completed_at,
                        f.created_at,
                        COALESCE(u.full_name, 'System') AS created_by_name
                    FROM followups f
                    LEFT JOIN users u ON u.id = f.created_by_user_id
                    WHERE f.lead_id = %s
                    ORDER BY f.followup_date DESC, f.id DESC
                """, (lead["id"],))
                history = cursor.fetchall() or []

                for h in history:
                    if h.get("followup_date"):
                        h["followup_date_fmt"] = h["followup_date"].strftime("%d %b %Y, %I:%M %p")
                    else:
                        h["followup_date_fmt"] = "N/A"
                    if h.get("completed_at"):
                        h["completed_at_fmt"] = h["completed_at"].strftime("%d %b %Y, %I:%M %p")
                    else:
                        h["completed_at_fmt"] = None
                    if h.get("created_at"):
                        h["created_at_fmt"] = h["created_at"].strftime("%d %b %Y, %I:%M %p")
                    else:
                        h["created_at_fmt"] = None

                return jsonify({
                    "success": True,
                    "lead": {
                        "lead_id": lead["id"],
                        "lead_uuid": lead["lead_uuid"],
                        "name": lead["name"] or "No Name",
                        "mobile": lead["mobile_number"] or "N/A",
                        "email": lead["email"] or "N/A"
                    },
                    "history": serialize_grid_rows(history)
                })
        finally:
            conn.close()

