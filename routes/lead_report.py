from functools import wraps
from flask import render_template, session, jsonify, request, flash, redirect, url_for
from config import get_db_connection
from utils.permissions import require_permission, has_permission
from routes.lead_upload_common import csv_response
from routes.settings_helpers import decrypt_mobile
import math
import re


def require_lead_report_permission(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_info = session.get("user", {})
        role_name = str(user_info.get("role_name") or "").lower()
        if user_info.get("is_admin") == 1 or role_name in ["admin", "super admin", "superadmin"] or user_info.get("id") in [1, 20]:
            return f(*args, **kwargs)
        if not (has_permission("reports", "lead_report") or has_permission("reports", "view")):
            if request.path.startswith("/api/") or request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "message": "Access Denied: You do not have permission for Lead Report."}), 403
            flash("Access Denied: You do not have permission to access Lead Report.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function


def format_time_ago(dt):
    if not dt:
        return ""
    from datetime import datetime
    now = datetime.now()
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    years = days // 365
    return f"{years}y ago"


def lead_report_routes(app):
    @app.route("/reports/lead-report", endpoint="lead_report_page")
    @app.route("/reports/leads", endpoint="lead_report")
    @require_lead_report_permission
    def lead_report_view():
        """
        Renders the Lead Report page with batch history, skeleton loader, and instant UI.
        Data is dynamically loaded via /api/reports/lead-batches.
        """
        can_export = has_permission("global_access_scope", "global_data_export")
        return render_template(
            "reports/lead_report.html",
            active_group="reports",
            active_page="lead_report",
            page_title="Lead Report",
            can_export=can_export,
        )

    @app.route("/api/reports/lead-batches")
    @require_lead_report_permission
    def api_reports_lead_batches():
        """
        Fast paginated API returning uploaded lead batches with live lead counts,
        lead sources, and uploader information.
        """
        try:
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(5, int(request.args.get("per_page", 10))))
            search = (request.args.get("search") or "").strip()
            upload_type = (request.args.get("upload_type") or "all").strip().lower()
            uploaded_by_filter = (request.args.get("uploaded_by") or "all").strip()
            source_filter = (request.args.get("source_id") or "all").strip()
            offset = (page - 1) * per_page

            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    where_clauses = ["1=1"]
                    params = []

                    if upload_type in ["file", "quick_paste"]:
                        where_clauses.append("b.upload_type = %s")
                        params.append(upload_type)

                    if uploaded_by_filter and uploaded_by_filter != "all":
                        where_clauses.append("(b.uploaded_by = %s OR u.user_uuid = %s OR CAST(u.id AS CHAR) = %s)")
                        params.extend([uploaded_by_filter, uploaded_by_filter, uploaded_by_filter])

                    if source_filter and source_filter != "all":
                        where_clauses.append("(b.lead_source = %s OR ls.source_name = %s)")
                        params.extend([source_filter, source_filter])

                    if search:
                        term = f"%{search.lower()}%"
                        where_clauses.append("""
                            (LOWER(b.batch_name) LIKE %s 
                             OR LOWER(b.batch_uuid) LIKE %s 
                             OR CAST(b.id AS CHAR) LIKE %s 
                             OR LOWER(COALESCE(u.full_name, '')) LIKE %s 
                             OR LOWER(COALESCE(u.username, '')) LIKE %s)
                        """)
                        params.extend([term, term, term, term, term])

                    where_sql = " AND ".join(where_clauses)

                    # 1. Total matching records count
                    count_query = f"""
                        SELECT COUNT(*) AS total
                        FROM lead_batches b
                        LEFT JOIN users u ON (u.user_uuid = b.uploaded_by OR u.id = b.uploaded_by)
                        LEFT JOIN lead_sources ls ON ls.id = b.lead_source
                        WHERE {where_sql}
                    """
                    cursor.execute(count_query, params)
                    total_records = int((cursor.fetchone() or {}).get("total") or 0)
                    total_pages = max(1, math.ceil(total_records / per_page))

                    # 2. Paginated batches
                    data_query = f"""
                        SELECT 
                            b.id,
                            b.batch_uuid,
                            b.batch_name,
                            b.upload_type,
                            b.lead_source,
                            b.uploaded_by,
                            b.created_at,
                            b.imported_at,
                            COALESCE(ls.source_name, 'No Source') AS source_name,
                            COALESCE(u.full_name, u.username, b.uploaded_by, 'System') AS uploader_name,
                            u.user_uuid AS uploader_uuid,
                            u.username AS uploader_username
                        FROM lead_batches b
                        LEFT JOIN users u ON (u.user_uuid = b.uploaded_by OR u.id = b.uploaded_by)
                        LEFT JOIN lead_sources ls ON ls.id = b.lead_source
                        WHERE {where_sql}
                        ORDER BY b.id DESC
                        LIMIT %s OFFSET %s
                    """
                    cursor.execute(data_query, params + [per_page, offset])
                    batches = cursor.fetchall() or []
                    batch_ids = [b["id"] for b in batches]

                    item_stats_map = {}
                    lead_stats_map = {}

                    if batch_ids:
                        placeholders = ",".join(["%s"] * len(batch_ids))

                        # 1. Upload-time stats from lead_batch_items
                        cursor.execute(f"""
                            SELECT 
                                batch_id,
                                COUNT(*) AS total_uploaded,
                                SUM(CASE WHEN item_status = 'imported' THEN 1 ELSE 0 END) AS imported_leads,
                                SUM(CASE WHEN item_status = 'duplicate' THEN 1 ELSE 0 END) AS duplicate_leads,
                                SUM(CASE WHEN item_status = 'invalid' THEN 1 ELSE 0 END) AS invalid_leads
                            FROM lead_batch_items
                            WHERE batch_id IN ({placeholders})
                            GROUP BY batch_id
                        """, batch_ids)
                        for r in cursor.fetchall() or []:
                            item_stats_map[r["batch_id"]] = r

                        # 2. Live leads count from leads table
                        cursor.execute(f"""
                            SELECT 
                                l.lead_batch_id,
                                COUNT(l.id) AS live_leads
                            FROM leads l
                            WHERE l.lead_batch_id IN ({placeholders})
                            GROUP BY l.lead_batch_id
                        """, batch_ids)
                        for r in cursor.fetchall() or []:
                            lead_stats_map[r["lead_batch_id"]] = r

                    # 3. Format batches for response
                    formatted_batches = []
                    for b in batches:
                        b_id = b["id"]
                        i_stat = item_stats_map.get(b_id, {})
                        l_stat = lead_stats_map.get(b_id, {})

                        dt = b.get("created_at")
                        created_at_fmt = dt.strftime("%d %b %Y, %I:%M %p") if dt else "-"
                        time_ago = format_time_ago(dt)

                        total_uploaded = int(i_stat.get("total_uploaded") or 0)
                        imported_leads = int(i_stat.get("imported_leads") or 0)
                        duplicate_leads = int(i_stat.get("duplicate_leads") or 0)
                        invalid_leads = int(i_stat.get("invalid_leads") or 0)
                        live_leads = int(l_stat.get("live_leads") or 0)
                        source_name = b.get("source_name") or ("No Source" if total_uploaded > 0 else "-")

                        raw_name = b["batch_name"] or f"Batch {b_id}"

                        formatted_batches.append({
                            "id": b_id,
                            "batch_uuid": b["batch_uuid"],
                            "batch_name": raw_name,
                            "upload_type": b["upload_type"],
                            "source_names": source_name,
                            "uploaded_by": b["uploader_name"],
                            "uploader_uuid": b.get("uploader_uuid") or "",
                            "created_at_fmt": created_at_fmt,
                            "time_ago": time_ago,
                            "total_uploaded": total_uploaded,
                            "imported_leads": imported_leads,
                            "duplicate_leads": duplicate_leads,
                            "invalid_leads": invalid_leads,
                            "live_leads": live_leads,
                        })

                    # 4. Fetch filter options (uploaders & lead sources)
                    cursor.execute("""
                        SELECT DISTINCT b.uploaded_by, COALESCE(u.full_name, u.username, b.uploaded_by) AS name, COALESCE(u.user_uuid, b.uploaded_by) AS uuid
                        FROM lead_batches b
                        LEFT JOIN users u ON (u.user_uuid = b.uploaded_by OR u.id = b.uploaded_by)
                        WHERE b.uploaded_by IS NOT NULL AND b.uploaded_by != ''
                        ORDER BY name ASC
                    """)
                    uploaders_list = cursor.fetchall() or []

                    cursor.execute("SELECT id, source_name FROM lead_sources ORDER BY source_name ASC")
                    sources_list = cursor.fetchall() or []

                    start_index = offset + 1 if total_records > 0 else 0
                    end_index = min(offset + per_page, total_records)

                    return jsonify({
                        "success": True,
                        "batches": formatted_batches,
                        "pagination": {
                            "page": page,
                            "per_page": per_page,
                            "total_records": total_records,
                            "total_pages": total_pages,
                            "start_index": start_index,
                            "end_index": end_index,
                            "has_prev": page > 1,
                            "has_next": page < total_pages,
                        },
                        "filter_options": {
                            "uploaders": uploaders_list,
                            "lead_sources": sources_list,
                        }
                    })
            finally:
                conn.close()
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    @app.route("/api/reports/batch-breakdown/<int:batch_id>")
    @require_lead_report_permission
    def api_reports_batch_breakdown(batch_id):
        """
        Returns upload-time metrics from lead_batch_items and live status breakdown
        from the leads table for the given batch_id.
        """
        try:
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    # 1. Batch info
                    cursor.execute("""
                        SELECT 
                            b.id,
                            b.batch_uuid,
                            b.batch_name,
                            b.upload_type,
                            b.lead_source,
                            b.uploaded_by,
                            b.created_at,
                            COALESCE(ls.source_name, 'No Source') AS source_name,
                            COALESCE(u.full_name, u.username, b.uploaded_by, 'System') AS uploader_name,
                            u.user_uuid AS uploader_uuid
                        FROM lead_batches b
                        LEFT JOIN users u ON (u.user_uuid = b.uploaded_by OR u.id = b.uploaded_by)
                        LEFT JOIN lead_sources ls ON ls.id = b.lead_source
                        WHERE b.id = %s
                    """, (batch_id,))
                    batch = cursor.fetchone()
                    if not batch:
                        return jsonify({"success": False, "message": "Batch not found."}), 404

                    dt = batch.get("created_at")
                    batch_info = {
                        "id": batch["id"],
                        "batch_uuid": batch["batch_uuid"],
                        "batch_name": batch["batch_name"] or f"Batch {batch['id']}",
                        "upload_type": batch["upload_type"],
                        "source_name": batch.get("source_name") or "No Source",
                        "uploaded_by": batch["uploader_name"],
                        "uploader_uuid": batch.get("uploader_uuid") or "",
                        "created_at_fmt": dt.strftime("%d %b %Y, %I:%M %p") if dt else "-",
                        "time_ago": format_time_ago(dt),
                    }

                    # 2. Upload-time stats from lead_batch_items
                    cursor.execute("""
                        SELECT 
                            COUNT(*) AS total_items,
                            SUM(CASE WHEN item_status = 'imported' THEN 1 ELSE 0 END) AS imported_count,
                            SUM(CASE WHEN item_status = 'duplicate' THEN 1 ELSE 0 END) AS duplicate_count,
                            SUM(CASE WHEN item_status = 'invalid' THEN 1 ELSE 0 END) AS invalid_count
                        FROM lead_batch_items
                        WHERE batch_id = %s
                    """, (batch_id,))
                    item_row = cursor.fetchone() or {}
                    upload_stats = {
                        "total_items": int(item_row.get("total_items") or 0),
                        "imported_count": int(item_row.get("imported_count") or 0),
                        "duplicate_count": int(item_row.get("duplicate_count") or 0),
                        "invalid_count": int(item_row.get("invalid_count") or 0),
                    }

                    # 3. Live leads summary & pipeline counts from leads table
                    cursor.execute("""
                        SELECT 
                            COUNT(l.id) AS total_leads,
                            SUM(CASE WHEN l.call_status = 1 THEN 1 ELSE 0 END) AS called_leads,
                            SUM(CASE WHEN l.call_status = 0 OR l.call_status IS NULL THEN 1 ELSE 0 END) AS not_called_leads,
                            SUM(CASE WHEN l.current_owner_user_id IS NOT NULL AND l.current_owner_user_id > 0 THEN 1 ELSE 0 END) AS assigned_leads,
                            SUM(CASE WHEN l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0 THEN 1 ELSE 0 END) AS unassigned_leads,
                            SUM(CASE WHEN l.is_disposed = 1 THEN 1 ELSE 0 END) AS disposed_leads,
                            (SELECT COUNT(DISTINCT f.lead_id) FROM followups f JOIN leads l2 ON l2.id = f.lead_id WHERE l2.lead_batch_id = %s) AS followup_leads,
                            (SELECT COUNT(DISTINCT ft.lead_id) FROM free_trials ft JOIN leads l3 ON l3.id = ft.lead_id WHERE l3.lead_batch_id = %s) AS trial_leads,
                            (SELECT COUNT(DISTINCT so.lead_id) FROM sales_orders so JOIN leads l4 ON l4.id = so.lead_id WHERE l4.lead_batch_id = %s) AS so_leads,
                            (SELECT COUNT(DISTINCT cl.lead_id) FROM clients cl JOIN leads l5 ON l5.id = cl.lead_id WHERE l5.lead_batch_id = %s) AS client_leads
                        FROM leads l
                        WHERE l.lead_batch_id = %s
                    """, (batch_id, batch_id, batch_id, batch_id, batch_id))
                    live_row = cursor.fetchone() or {}
                    live_stats = {
                        "total_leads": int(live_row.get("total_leads") or 0),
                        "called_leads": int(live_row.get("called_leads") or 0),
                        "not_called_leads": int(live_row.get("not_called_leads") or 0),
                        "assigned_leads": int(live_row.get("assigned_leads") or 0),
                        "unassigned_leads": int(live_row.get("unassigned_leads") or 0),
                        "disposed_leads": int(live_row.get("disposed_leads") or 0),
                        "followup_leads": int(live_row.get("followup_leads") or 0),
                        "trial_leads": int(live_row.get("trial_leads") or 0),
                        "so_leads": int(live_row.get("so_leads") or 0),
                        "client_leads": int(live_row.get("client_leads") or 0),
                    }

                    # 4. Status breakdown with pipeline activity from leads table
                    # Keep "No Status" at the top (is_no_status = 1), handle deleted statuses, and order by total_leads DESC
                    cursor.execute("""
                        SELECT 
                            CASE 
                                WHEN (l.lead_status IS NULL OR l.lead_status = '' OR l.lead_status = '0' OR l.lead_status = 0) THEN 'No Status'
                                WHEN st.id IS NOT NULL THEN st.status_name
                                ELSE CONCAT(l.lead_status, ' (Deleted)')
                            END AS display_status,
                            CASE 
                                WHEN (l.lead_status IS NULL OR l.lead_status = '' OR l.lead_status = '0' OR l.lead_status = 0) THEN 'slate'
                                WHEN st.id IS NOT NULL THEN COALESCE(st.status_tone, 'blue')
                                ELSE 'rose'
                            END AS status_tone,
                            CASE 
                                WHEN (l.lead_status IS NULL OR l.lead_status = '' OR l.lead_status = '0' OR l.lead_status = 0) THEN 1
                                ELSE 0
                            END AS is_no_status,
                            COUNT(DISTINCT l.id) AS total_leads,
                            COUNT(DISTINCT f.id) AS followup_count,
                            COUNT(DISTINCT ft.id) AS trial_count,
                            COUNT(DISTINCT so.id) AS so_count,
                            COUNT(DISTINCT cl.id) AS client_count
                        FROM leads l
                        LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_uuid = l.lead_status OR st.status_name = l.lead_status)
                        LEFT JOIN followups f ON f.lead_id = l.id
                        LEFT JOIN free_trials ft ON ft.lead_id = l.id
                        LEFT JOIN sales_orders so ON so.lead_id = l.id
                        LEFT JOIN clients cl ON cl.lead_id = l.id
                        WHERE l.lead_batch_id = %s
                        GROUP BY display_status, status_tone, is_no_status
                        ORDER BY is_no_status DESC, total_leads DESC
                    """, (batch_id,))
                    status_rows = cursor.fetchall() or []

                    total_live = live_stats["total_leads"]
                    formatted_statuses = []
                    for st in status_rows:
                        cnt = int(st["total_leads"])
                        pct = round((cnt / total_live * 100), 1) if total_live > 0 else 0
                        formatted_statuses.append({
                            "status_name": st["display_status"],
                            "status_tone": st["status_tone"],
                            "total_leads": cnt,
                            "percentage": pct,
                            "followup_count": int(st.get("followup_count") or 0),
                            "trial_count": int(st.get("trial_count") or 0),
                            "so_count": int(st.get("so_count") or 0),
                            "client_count": int(st.get("client_count") or 0),
                        })

                    # 5. Live source breakdown from leads table (in case leads were reassigned or had multiple sources)
                    cursor.execute("""
                        SELECT 
                            CASE 
                                WHEN (l.lead_source IS NULL OR l.lead_source = '' OR l.lead_source = '0' OR l.lead_source = 0) THEN 'No Source'
                                WHEN ls.id IS NOT NULL THEN ls.source_name
                                ELSE COALESCE(l.lead_source, 'Unknown Source')
                            END AS source_name,
                            COUNT(l.id) AS total_leads
                        FROM leads l
                        LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_uuid = l.lead_source OR ls.source_name = l.lead_source)
                        WHERE l.lead_batch_id = %s
                        GROUP BY source_name
                        ORDER BY total_leads DESC
                    """, (batch_id,))
                    source_rows = cursor.fetchall() or []
                    formatted_sources = []
                    for src in source_rows:
                        cnt = int(src["total_leads"])
                        pct = round((cnt / total_live * 100), 1) if total_live > 0 else 0
                        formatted_sources.append({
                            "source_name": src["source_name"],
                            "total_leads": cnt,
                            "percentage": pct,
                        })

                    return jsonify({
                        "success": True,
                        "batch": batch_info,
                        "upload_stats": upload_stats,
                        "live_stats": live_stats,
                        "statuses": formatted_statuses,
                        "sources": formatted_sources,
                        "source_name": batch_info.get("source_name") or "No Source",
                        "can_export": has_permission("global_access_scope", "global_data_export"),
                    })
            finally:
                conn.close()
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    @app.route("/reports/batch-leads/export", endpoint="export_lead_report_batch_leads")
    @require_lead_report_permission
    def export_lead_report_batch_leads():
        """
        Exports leads from a batch filtered by 'all', 'status', or 'source'.
        Strictly guarded by 'Global Data Export' permission (has_permission('global_access_scope', 'global_data_export')).
        """
        if not has_permission("global_access_scope", "global_data_export"):
            flash("Access Denied: You do not have 'Global Data Export' permission to download lead CSV files.", "danger")
            return redirect(url_for("lead_report_page"))

        batch_id = request.args.get("batch_id")
        export_type = (request.args.get("type") or "all").strip().lower()
        value = (request.args.get("value") or "").strip()

        if not batch_id:
            flash("Invalid batch specified.", "danger")
            return redirect(url_for("lead_report_page"))

        conn = get_db_connection()
        if not conn:
            flash("Database connection error.", "danger")
            return redirect(url_for("lead_report_page"))

        try:
            with conn.cursor() as cursor:
                # 1. Fetch batch info
                cursor.execute("SELECT id, batch_uuid, batch_name FROM lead_batches WHERE id = %s", (batch_id,))
                batch = cursor.fetchone()
                if not batch:
                    flash("Lead batch not found.", "danger")
                    return redirect(url_for("lead_report_page"))

                where_clauses = ["l.lead_batch_id = %s"]
                params = [batch_id]

                if export_type == "status" and value:
                    if value.lower() in ["no status", "no_status"]:
                        where_clauses.append("(l.lead_status IS NULL OR l.lead_status = '' OR l.lead_status = '0' OR l.lead_status = 0)")
                    elif value.endswith(" (Deleted)"):
                        orig_val = value.replace(" (Deleted)", "").strip()
                        where_clauses.append("l.lead_status = %s")
                        params.append(orig_val)
                    else:
                        where_clauses.append("(st.status_name = %s OR l.lead_status = %s)")
                        params.extend([value, value])

                elif export_type == "source" and value:
                    if value.lower() in ["no source", "no_source"]:
                        where_clauses.append("(l.lead_source IS NULL OR l.lead_source = '' OR l.lead_source = '0' OR l.lead_source = 0)")
                    else:
                        where_clauses.append("(ls.source_name = %s OR l.lead_source = %s)")
                        params.extend([value, value])

                where_sql = " AND ".join(where_clauses)

                query = f"""
                    SELECT 
                        l.id AS lead_id,
                        l.lead_uuid,
                        COALESCE(b.batch_name, '') AS batch_name,
                        COALESCE(l.name, '') AS name,
                        l.mobile_number,
                        COALESCE(l.email, '') AS email,
                        COALESCE(l.address, '') AS address,
                        COALESCE(ls.source_name, 'No Source') AS source_name,
                        CASE 
                            WHEN (l.lead_status IS NULL OR l.lead_status = '' OR l.lead_status = '0' OR l.lead_status = 0) THEN 'No Status'
                            WHEN st.id IS NOT NULL THEN st.status_name
                            ELSE CONCAT(l.lead_status, ' (Deleted)')
                        END AS status_name,
                        CASE WHEN l.call_status = 1 THEN 'Called' ELSE 'Not Called' END AS call_status_label,
                        COALESCE(u.full_name, u.username, 'Unassigned') AS owner_name,
                        CASE WHEN (l.is_disposed = 1 OR l.disposed_by IS NOT NULL OR l.disposed_at IS NOT NULL) THEN 'Yes' ELSE 'No' END AS disposed_label,
                        (CASE WHEN EXISTS (SELECT 1 FROM followups f WHERE f.lead_id = l.id) THEN 'Yes' ELSE 'No' END) AS has_followup,
                        (CASE WHEN EXISTS (SELECT 1 FROM free_trials ft WHERE ft.lead_id = l.id) THEN 'Yes' ELSE 'No' END) AS has_free_trial,
                        (CASE WHEN EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id) THEN 'Yes' ELSE 'No' END) AS has_so,
                        (CASE WHEN EXISTS (SELECT 1 FROM clients cl WHERE cl.lead_id = l.id) THEN 'Yes' ELSE 'No' END) AS is_paid_client,
                        COALESCE(l.comment, '') AS comment,
                        l.created_at
                    FROM leads l
                    LEFT JOIN lead_batches b ON b.id = l.lead_batch_id
                    LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_uuid = l.lead_source OR ls.source_name = l.lead_source)
                    LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_uuid = l.lead_status OR st.status_name = l.lead_status)
                    LEFT JOIN users u ON u.id = l.current_owner_user_id
                    WHERE {where_sql}
                    ORDER BY l.id ASC
                """
                cursor.execute(query, params)
                leads = cursor.fetchall() or []

                rows = []
                for idx, item in enumerate(leads, 1):
                    raw_mob = item.get("mobile_number") or ""
                    dec_mob = decrypt_mobile(raw_mob) if raw_mob else ""
                    created_dt = item.get("created_at")
                    created_fmt = created_dt.strftime("%Y-%m-%d %H:%M:%S") if created_dt else ""

                    rows.append({
                        "S.No": idx,
                        "Lead ID": item["lead_id"],
                        "Lead UUID": item["lead_uuid"],
                        "Batch Name": item["batch_name"],
                        "Name": item["name"],
                        "Mobile Number": dec_mob,
                        "Email": item["email"],
                        "Address": item["address"],
                        "Lead Source": item["source_name"],
                        "Lead Status": item["status_name"],
                        "Call Status": item["call_status_label"],
                        "Assigned Owner": item["owner_name"],
                        "Disposed": item["disposed_label"],
                        "Follow-up": item["has_followup"],
                        "Free Trial": item["has_free_trial"],
                        "SO": item["has_so"],
                        "Paid Client": item["is_paid_client"],
                        "Comment": item["comment"],
                        "Created At": created_fmt,
                    })

                safe_batch = re.sub(r"[^a-zA-Z0-9_-]", "_", (batch.get("batch_name") or f"batch_{batch_id}").strip().lower())
                if export_type == "status" and value:
                    safe_val = re.sub(r"[^a-zA-Z0-9_-]", "_", value.strip().lower())
                    filename = f"{safe_batch}_status_{safe_val}.csv"
                elif export_type == "source" and value:
                    safe_val = re.sub(r"[^a-zA-Z0-9_-]", "_", value.strip().lower())
                    filename = f"{safe_batch}_source_{safe_val}.csv"
                else:
                    filename = f"{safe_batch}_all_leads.csv"

                fieldnames = [
                    "S.No", "Lead ID", "Lead UUID", "Batch Name",
                    "Name", "Mobile Number", "Email", "Address",
                    "Lead Source", "Lead Status", "Call Status",
                    "Assigned Owner", "Disposed", "Follow-up", "Free Trial",
                    "SO", "Paid Client", "Comment", "Created At"
                ]
                return csv_response(filename, fieldnames, rows)
        finally:
            conn.close()
