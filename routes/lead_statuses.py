from utils.permissions import require_permission
from flask import jsonify, render_template, request, url_for

from config import get_db_connection
from routes.settings_helpers import (
    get_page_size_options,
    get_status_filter,
    json_error,
    make_unique_code,
    parse_int,
    serialize_rows,
)
from routes.settings_helpers import (
    LEAD_STATUS_TONES,
    LEAD_STATUS_TONE_VALUES,
)


def fetch_lead_status_rows(cursor):
    cursor.execute("""
        SELECT status_uuid, status_name, status_tone, status, created_at
        FROM lead_statuses
        ORDER BY status_name ASC
    """)
    return serialize_rows(cursor.fetchall())


def lead_status_columns():
    return [
        {"headerName": "Lead Status", "field": "status_name", "minWidth": 220, "flex": 1.2, "renderer": "leadStatusBadge"},
        {"headerName": "Color Tone", "field": "status_tone", "minWidth": 140, "flex": 0.4, "renderer": "leadToneBadge"},
        {"headerName": "Status", "field": "status", "minWidth": 120, "flex": 0.4, "renderer": "statusBadge"},
        {"headerName": "Action", "field": "action", "minWidth": 110, "sortable": False, "filter": False, "renderer": "settingsMasterAction"},
    ]


def lead_status_routes(app):
    @require_permission('settings', 'lead_management')
    @app.route("/settings/lead/statuses")
    def setting_lead_statuses():
        conn = get_db_connection()
        with conn.cursor() as cursor:
            rows = fetch_lead_status_rows(cursor)
        conn.close()

        return render_template(
            "settings/master_page.html",
            grid_id="leadStatusesGrid",
            data=rows,
            columns=lead_status_columns(),
            filters=get_status_filter(),
            toolbar_buttons=[{
                "type": "button",
                "label": "Add Lead Status",
                "icon": "mdi mdi-plus",
                "class": "btn btn-outline-primary",
                "attrs": {"data-master-add": ""},
            }],
            grid_wrapper_class="settings-master-wrap",
            grid_wrapper_attrs={
                "data-master-type": "lead_statuses",
                "data-save-url": url_for("save_lead_status"),
            },
            row_id_field="status_uuid",
            action_id_field="status_uuid",
            bulk_delete_url=url_for("delete_selected_lead_statuses"),
            page_size=10,
            page_size_options=get_page_size_options(),
            status_field="status",
            active_values=[1, "1", True],
            active_group="settings",
            active_page="setting_lead_statuses",
            page_title="Lead Status",
            page_heading="Lead Status",
            modal_id="leadStatusModal",
            modal_title="Lead Status",
            add_title="Add Lead Status",
            form_type="lead_status",
            lead_status_tones=LEAD_STATUS_TONES,
        )

    @require_permission('settings', 'lead_management')
    @app.route("/settings/api/lead-statuses/save", methods=["POST"])
    def save_lead_status():
        payload = request.get_json(silent=True) or {}
        status_uuid = payload.get("record_uuid")
        status_name = (payload.get("status_name") or "").strip()
        status_tone = (payload.get("status_tone") or "slate").strip()
        if status_tone not in LEAD_STATUS_TONE_VALUES:
            status_tone = "slate"
        if not status_name:
            return json_error("Lead status name is required.")

        try:
            status = parse_int(payload.get("status", 1), "Status", 0, 1)
        except ValueError as error:
            return json_error(str(error))

        conn = get_db_connection()
        with conn.cursor() as cursor:
            if status_uuid:
                cursor.execute("SELECT status_name FROM lead_statuses WHERE status_uuid = %s LIMIT 1", (status_uuid,))
                existing = cursor.fetchone()
                if not existing:
                    conn.close()
                    return json_error("Lead status not found.", 404)
                cursor.execute("""
                    SELECT 1 FROM lead_statuses
                    WHERE status_name = %s AND status_uuid <> %s
                    LIMIT 1
                """, (status_name, status_uuid))
                if cursor.fetchone():
                    conn.close()
                    return json_error("This lead status already exists.")
                cursor.execute("UPDATE leads SET lead_status = %s WHERE lead_status = %s", (status_name, existing["status_name"]))
                cursor.execute("""
                    UPDATE lead_statuses
                    SET status_name = %s, status_tone = %s, status = %s
                    WHERE status_uuid = %s
                """, (status_name, status_tone, status, status_uuid))
                message = "Lead status updated successfully."
            else:
                cursor.execute("SELECT 1 FROM lead_statuses WHERE status_name = %s LIMIT 1", (status_name,))
                if cursor.fetchone():
                    conn.close()
                    return json_error("This lead status already exists.")
                cursor.execute("""
                    INSERT INTO lead_statuses (status_uuid, status_name, status_tone, status)
                    VALUES (%s, %s, %s, %s)
                """, (
                    make_unique_code(cursor, "lead_statuses", "status_uuid", "LSTS"),
                    status_name,
                    status_tone,
                    status,
                ))
                message = "Lead status added successfully."

        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": message})

    @app.route("/settings/api/lead-statuses/delete-selected", methods=["POST"])
    def delete_selected_lead_statuses():
        payload = request.get_json(silent=True) or {}
        status_uuids = [str(value or "").strip() for value in payload.get("ids", []) if str(value or "").strip()]
        if not status_uuids:
            return json_error("No lead statuses selected.")

        placeholders = ", ".join(["%s"] * len(status_uuids))
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(f"""
                DELETE s
                FROM lead_statuses s
                LEFT JOIN leads l ON l.lead_status = s.status_name
                WHERE s.status_uuid IN ({placeholders})
                  AND l.id IS NULL
            """, status_uuids)
            deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        skipped_count = len(status_uuids) - deleted_count
        message = f"{deleted_count} lead status(es) deleted."
        if skipped_count:
            message += f" {skipped_count} skipped because leads are using them."
        return jsonify({"success": True, "message": message})
