from datetime import datetime

from flask import Response, flash, redirect, render_template, url_for, request, jsonify

from config import get_db_connection
from routes.settings_helpers import decrypt_mobile
from routes.lead_upload_common import (
    cleanup_expired_lead_batch_raw_data,
    csv_response,
    get_batch,
    get_batch_list_rows,
    get_batch_performance,
    get_duplicate_rows,
    get_invalid_rows,
    get_metric_rows,
    get_performance_metrics,
    raw_data_available,
    serialize_grid_rows,
)
from utils.permissions import has_permission
import re


def check_export_permission():
    return has_permission("global_access_scope", "global_data_export")


def fetch_upload_options(cursor):
    cursor.execute("""
        SELECT id, source_name
        FROM lead_sources
        WHERE status = 1
        ORDER BY source_name ASC
    """)
    sources = cursor.fetchall()

    cursor.execute("""
        SELECT user_uuid, full_name
        FROM users
        WHERE status = 1
        ORDER BY full_name ASC
    """)
    users = cursor.fetchall()

    cursor.execute("""
        SELECT id, status_name
        FROM lead_statuses
        WHERE status = 1
        ORDER BY status_name ASC
    """)
    statuses = cursor.fetchall()

    return {
        "sources": sources,
        "users": users,
        "statuses": statuses,
    }


def default_batch_name():
    return datetime.now().strftime("Lead Batch - %d %b %Y %I:%M %p")


def build_batch_grid_rows(batches):
    rows = []
    for batch in batches:
        row = dict(batch)
        row["upload_type_label"] = "File Upload" if row.get("upload_type") == "file" else "Quick Paste"
        row["raw_data_status"] = "Available" if raw_data_available(row) else "Expired"
        rows.append(row)
    return serialize_grid_rows(rows)


def metric_label(metric, performance_metrics=None):
    metric_labels = {
        "total_uploaded": "Total Uploaded",
        "fresh_imported": "Fresh Imported",
        "duplicate": "Duplicate",
        "invalid": "Invalid",
    }
    for key, label, _field, _value in performance_metrics or []:
        metric_labels[key] = label
    return metric_labels.get(metric, "Batch List")


def metric_csv_columns(metric):
    if metric == "duplicate":
        return [
            "uploaded_number",
            "existing_lead_id",
            "existing_lead_status",
            "current_owner",
            "lead_source",
            "created_at",
            "updated_at",
        ]
    if metric == "invalid":
        return ["row_number", "uploaded_number", "validation_message", "created_at"]
    if metric == "total_uploaded":
        return [
            "row_number",
            "uploaded_number",
            "item_status",
            "validation_message",
            "created_at",
        ]
    return [
        "lead_uuid",
        "name",
        "mobile_number",
        "email",
        "lead_source",
        "lead_status",
        "call_state",
        "current_owner",
        "created_at",
        "updated_at",
    ]


def register_lead_upload_routes(app):

    @app.route("/leads/sample-csv", endpoint="sample_csv_download")
    def sample_csv_download():
        sample_data = (
            "mobile_number,name,email,address\r\n"
            "9876543210,Ramesh Kumar,ramesh@example.com,Delhi\r\n"
            "8123456789,Priya Sharma,priya@example.com,Mumbai\r\n"
            "7012345678,Amit Singh,,Jaipur\r\n"
            "6123456789,Sunita Yadav,,\r\n"
            "9988776655,Deepak Verma,deepak@example.com,Pune\r\n"
        )
        return Response(
            sample_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=lead_upload_sample.csv"},
        )


    @app.route("/leads/bulk-upload", endpoint="bulk_upload_leads")
    def bulk_upload_leads():
        conn = get_db_connection()
        with conn.cursor() as cursor:
            options = fetch_upload_options(cursor)
        conn.close()

        return render_template(
            "leads/bulk_upload_leads.html",
            options=options,
            default_batch_name=default_batch_name(),
            active_group="operations",
            active_page="bulk_upload_leads",
            page_title="Upload Leads",
        )

    @app.route("/leads/paste-leads", endpoint="paste_leads")
    def paste_leads():
        conn = get_db_connection()
        with conn.cursor() as cursor:
            options = fetch_upload_options(cursor)
        conn.close()

        return render_template(
            "leads/paste_leads.html",
            options=options,
            default_batch_name=default_batch_name(),
            active_group="operations",
            active_page="paste_leads",
            page_title="Paste Leads",
        )

    @app.route("/api/leads/recent-batches", endpoint="api_leads_recent_batches")
    def api_leads_recent_batches():
        try:
            conn = get_db_connection()
            if not conn:
                return jsonify({"success": False, "batches": [], "message": "Database connection error."}), 500
            try:
                with conn.cursor() as cursor:
                    limit = min(20, max(1, int(request.args.get("limit", 5))))
                    batches = build_batch_grid_rows(get_batch_list_rows(cursor, limit=limit))
                return jsonify({
                    "success": True,
                    "batches": batches,
                    "can_export": has_permission("global_access_scope", "global_data_export"),
                })
            finally:
                conn.close()
        except Exception as e:
            return jsonify({"success": False, "batches": [], "message": str(e)}), 500

    @app.route("/leads/batches")
    def lead_batches():
        conn = get_db_connection()
        with conn.cursor() as cursor:
            batches = get_batch_list_rows(cursor)
        conn.close()

        return render_template(
            "leads/batches/list.html",
            batches=build_batch_grid_rows(batches),
            active_group="operations",
            active_page="lead_batches",
            page_title="Lead Batches",
        )

    @app.route("/leads/batches/<batch_uuid>/result")
    def lead_batch_result(batch_uuid):
        return redirect(url_for("lead_batch_detail", batch_uuid=batch_uuid))

    @app.route("/leads/batches/<batch_uuid>")
    def lead_batch_detail(batch_uuid):
        conn = get_db_connection()
        with conn.cursor() as cursor:
            batch = get_batch(cursor, batch_uuid)
            if not batch:
                conn.close()
                flash("Lead batch not found.", "danger")
                return redirect(url_for("lead_batches"))
            performance = get_batch_performance(cursor, batch)
            performance_metrics = get_performance_metrics(cursor)
        conn.close()

        return render_template(
            "leads/batches/detail.html",
            batch=batch,
            performance=performance,
            performance_metrics=performance_metrics,
            raw_available=raw_data_available(batch),
            active_group="operations",
            active_page="lead_batches",
            page_title=batch["batch_name"],
        )

    @app.route("/leads/batches/<batch_uuid>/export", defaults={"metric": "total"}, endpoint="export_batch_leads")
    @app.route("/leads/batches/<batch_uuid>/export/<metric>", endpoint="export_batch_leads_metric")
    def export_batch_leads(batch_uuid, metric="total"):
        if not check_export_permission():
            flash("Access Denied: You do not have 'Global Data Export' permission to download lead CSV files.", "danger")
            return redirect(url_for("paste_leads"))

        conn = get_db_connection()
        if not conn:
            flash("Database connection error.", "danger")
            return redirect(url_for("paste_leads"))
        try:
            with conn.cursor() as cursor:
                batch = get_batch(cursor, batch_uuid)
                if not batch:
                    flash("Lead batch not found.", "danger")
                    return redirect(url_for("paste_leads"))

                sql = """
                    SELECT
                        i.`row_number`,
                        i.item_uuid,
                        i.item_status,
                        i.validation_message,
                        i.created_at AS batch_item_created_at,
                        l.id          AS lead_id,
                        l.lead_uuid,
                        COALESCE(l.name, i.name)                   AS name,
                        COALESCE(l.mobile_number, i.mobile_number) AS mobile_number,
                        COALESCE(l.email, i.email)                 AS email,
                        COALESCE(l.address, i.address)             AS address,
                        l.lead_source,
                        l.lead_status,
                        l.call_status,
                        (CASE WHEN EXISTS (SELECT 1 FROM contacts c WHERE c.lead_id = l.id) THEN 1 ELSE 0 END) AS has_contact,
                        (CASE WHEN EXISTS (SELECT 1 FROM followups f WHERE f.lead_id = l.id) THEN 1 ELSE 0 END) AS has_followup,
                        (CASE WHEN EXISTS (SELECT 1 FROM free_trials ft WHERE ft.lead_id = l.id) THEN 1 ELSE 0 END) AS has_free_trial,
                        (CASE WHEN EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id) THEN 1 ELSE 0 END) AS has_so,
                        (CASE WHEN EXISTS (SELECT 1 FROM clients cl WHERE cl.lead_id = l.id) THEN 1 ELSE 0 END) AS is_paid_client,
                        (CASE WHEN l.is_disposed = 1 OR l.disposed_by IS NOT NULL OR l.disposed_at IS NOT NULL THEN 1 ELSE 0 END) AS is_disposed,
                        l.comment,
                        l.assigned_at,
                        l.created_at  AS lead_created_at,
                        l.updated_at  AS lead_updated_at,
                        l.disposed_at,
                        u_owner.full_name   AS owner_name,
                        u_creator.full_name AS creator_name,
                        u_disposed.full_name AS disposed_by_name
                    FROM lead_batch_items i
                    LEFT JOIN leads l
                           ON l.lead_batch_id = i.batch_id
                          AND l.mobile_number  = i.mobile_number
                    LEFT JOIN users u_owner    ON u_owner.id   = l.current_owner_user_id
                    LEFT JOIN users u_creator  ON u_creator.id = l.created_by
                    LEFT JOIN users u_disposed ON u_disposed.id = CAST(l.disposed_by AS UNSIGNED)
                    WHERE i.batch_id = %s
                """
                params = [batch["id"]]

                if metric in ["uploaded", "imported", "fresh"]:
                    sql += " AND i.item_status IN ('imported', 'fresh')"
                elif metric == "duplicate":
                    sql += " AND i.item_status = 'duplicate'"
                elif metric == "invalid":
                    sql += " AND i.item_status = 'invalid'"

                sql += " ORDER BY i.`row_number` ASC"
                cursor.execute(sql, params)
                raw_items = cursor.fetchall()

                cursor.execute("SELECT id, source_name FROM lead_sources")
                source_map = {str(r["id"]): r["source_name"] for r in cursor.fetchall()}

                cursor.execute("SELECT id, status_name FROM lead_statuses")
                status_map = {str(r["id"]): r["status_name"] for r in cursor.fetchall()}

                rows = []
                for item in raw_items:
                    dec_mob = decrypt_mobile(item["mobile_number"]) if item.get("mobile_number") else ""
                    src_id  = str(item.get("lead_source") or "")
                    st_id   = str(item.get("lead_status") or "")

                    rows.append({
                        "Row Number":      item["row_number"],
                        "Lead DB ID":      item.get("lead_id") or "",
                        "Lead UUID":       item.get("lead_uuid") or item["item_uuid"],
                        "Batch Name":      batch["batch_name"],
                        "Name":            item.get("name") or "",
                        "Mobile Number":   dec_mob,
                        "Email":           item.get("email") or "",
                        "Address":         item.get("address") or "",
                        "Lead Source":     source_map.get(src_id, "") if src_id else "",
                        "Lead Status":     status_map.get(st_id, "") if st_id else "",
                        "Call Status":     item.get("call_status") if item.get("call_status") is not None else "",
                        "Has Contact":     "Yes" if item.get("has_contact") else "No",
                        "Has Followup":    "Yes" if item.get("has_followup") else "No",
                        "Has Free Trial":  "Yes" if item.get("has_free_trial") else "No",
                        "Has SO":          "Yes" if item.get("has_so") else "No",
                        "Is Paid Client":  "Yes" if item.get("is_paid_client") else "No",
                        "Is Disposed":     "Yes" if item.get("is_disposed") else "No",
                        "Disposed By":     item.get("disposed_by_name") or "",
                        "Disposed At":     str(item["disposed_at"]) if item.get("disposed_at") else "",
                        "Comment":         item.get("comment") or "",
                        "Assigned Owner":  item.get("owner_name") or "",
                        "Assigned At":     str(item["assigned_at"]) if item.get("assigned_at") else "",
                        "Created By":      item.get("creator_name") or "",
                        "Created At":      str(item["lead_created_at"]) if item.get("lead_created_at") else str(item.get("batch_item_created_at", "")),
                        "Updated At":      str(item["lead_updated_at"]) if item.get("lead_updated_at") else "",
                        "Item Status":     item["item_status"],
                        "Validation Message": item["validation_message"] or "",
                    })

                safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", batch["batch_name"].lower())
                filename  = f"{safe_name}_{metric}_{batch_uuid}.csv"
                fieldnames = [
                    "Row Number", "Lead DB ID", "Lead UUID", "Batch Name",
                    "Name", "Mobile Number", "Email", "Address",
                    "Lead Source", "Lead Status",
                    "Call Status", "Has Contact", "Has Followup", "Has Free Trial",
                    "Has SO", "Is Paid Client", "Is Disposed", "Disposed By", "Disposed At",
                    "Comment",
                    "Assigned Owner", "Assigned At",
                    "Created By", "Created At", "Updated At",
                    "Item Status", "Validation Message",
                ]
                return csv_response(filename, fieldnames, rows)
        finally:
            conn.close()

    @app.route("/leads/batches/<batch_uuid>/list/<metric>")
    def lead_batch_metric_list(batch_uuid, metric):
        conn = get_db_connection()
        with conn.cursor() as cursor:
            batch = get_batch(cursor, batch_uuid)
            if not batch:
                conn.close()
                flash("Lead batch not found.", "danger")
                return redirect(url_for("lead_batches"))
            try:
                if metric in {"total_uploaded", "duplicate", "invalid"} and not raw_data_available(batch):
                    rows = []
                else:
                    rows = get_metric_rows(cursor, batch, metric)
                performance_metrics = get_performance_metrics(cursor)
            except ValueError:
                conn.close()
                flash("Unknown batch metric.", "danger")
                return redirect(url_for("lead_batch_detail", batch_uuid=batch_uuid))
        conn.close()

        return render_template(
            "leads/batches/metric_list.html",
            batch=batch,
            metric=metric,
            metric_label=metric_label(metric, performance_metrics),
            rows=serialize_grid_rows(rows),
            download_url=url_for("download_batch_metric", batch_uuid=batch_uuid, metric=metric),
            active_group="operations",
            active_page="lead_batches",
            page_title="Batch List",
        )

    @app.route("/leads/batches/<batch_uuid>/download/<metric>")
    def download_batch_metric(batch_uuid, metric):
        if not check_export_permission():
            flash("Access Denied: You do not have 'Global Data Export' permission.", "danger")
            return redirect(url_for("paste_leads"))
        conn = get_db_connection()
        with conn.cursor() as cursor:
            batch = get_batch(cursor, batch_uuid)
            if not batch:
                conn.close()
                flash("Lead batch not found.", "danger")
                return redirect(url_for("lead_batches"))
            try:
                if metric in {"total_uploaded", "duplicate", "invalid"} and not raw_data_available(batch):
                    rows = []
                else:
                    rows = get_metric_rows(cursor, batch, metric)
            except ValueError:
                conn.close()
                flash("Unknown batch metric.", "danger")
                return redirect(url_for("lead_batch_detail", batch_uuid=batch_uuid))
        conn.close()

        columns = metric_csv_columns(metric)
        csv_body = csv_response(rows, columns)
        safe_name = batch["batch_name"].replace(" ", "_")
        filename = f"{safe_name}_{metric}.csv"
        return Response(
            csv_body,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.route("/leads/batches/<batch_uuid>/download/duplicates")
    def download_batch_duplicates(batch_uuid):
        if not check_export_permission():
            flash("Access Denied: You do not have 'Global Data Export' permission.", "danger")
            return redirect(url_for("paste_leads"))
        conn = get_db_connection()
        with conn.cursor() as cursor:
            batch = get_batch(cursor, batch_uuid)
            if not batch:
                conn.close()
                flash("Lead batch not found.", "danger")
                return redirect(url_for("lead_batches"))
            rows = get_duplicate_rows(cursor, batch["batch_uuid"]) if raw_data_available(batch) else []
        conn.close()

        columns = [
            "uploaded_number",
            "existing_lead_id",
            "existing_lead_status",
            "current_owner",
            "lead_source",
            "created_at",
            "updated_at",
        ]
        csv_body = csv_response(rows, columns)
        filename = f"{batch['batch_name'].replace(' ', '_')}_duplicates.csv"
        return Response(
            csv_body,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.route("/leads/batches/<batch_uuid>/download/invalid")
    def download_batch_invalid(batch_uuid):
        if not check_export_permission():
            flash("Access Denied: You do not have 'Global Data Export' permission.", "danger")
            return redirect(url_for("paste_leads"))
        conn = get_db_connection()
        with conn.cursor() as cursor:
            batch = get_batch(cursor, batch_uuid)
            if not batch:
                conn.close()
                flash("Lead batch not found.", "danger")
                return redirect(url_for("lead_batches"))
            rows = get_invalid_rows(cursor, batch["batch_uuid"]) if raw_data_available(batch) else []
        conn.close()

        columns = ["row_number", "uploaded_number", "validation_message", "created_at"]
        csv_body = csv_response(rows, columns)
        filename = f"{batch['batch_name'].replace(' ', '_')}_invalid_numbers.csv"
        return Response(
            csv_body,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.route("/leads/batches/cleanup-raw", methods=["POST"])
    def cleanup_lead_batch_raw():
        conn = get_db_connection()
        deleted_count = cleanup_expired_lead_batch_raw_data(conn)
        conn.close()
        flash(f"{deleted_count} expired raw lead upload item(s) cleaned.", "success")
        return redirect(url_for("lead_batches"))
