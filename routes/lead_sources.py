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


def fetch_lead_source_rows(cursor):
    cursor.execute("""
        SELECT source_uuid, source_name, status, created_at
        FROM lead_sources
        ORDER BY source_name ASC
    """)
    return serialize_rows(cursor.fetchall())


def lead_source_columns():
    return [
        {"headerName": "Lead Source", "field": "source_name", "minWidth": 220, "flex": 1.4},
        {"headerName": "Status", "field": "status", "minWidth": 120, "flex": 0.4, "renderer": "statusBadge"},
        {"headerName": "Action", "field": "action", "minWidth": 110, "sortable": False, "filter": False, "renderer": "settingsMasterAction"},
    ]


def lead_source_routes(app):
    @require_permission('settings', 'lead_management')
    @app.route("/settings/lead/sources")
    def setting_lead_sources():
        conn = get_db_connection()
        with conn.cursor() as cursor:
            rows = fetch_lead_source_rows(cursor)
        conn.close()

        return render_template(
            "settings/master_page.html",
            grid_id="leadSourcesGrid",
            data=rows,
            columns=lead_source_columns(),
            filters=get_status_filter(),
            toolbar_buttons=[{
                "type": "button",
                "label": "Add Lead Source",
                "icon": "mdi mdi-plus",
                "class": "btn btn-outline-primary",
                "attrs": {"data-master-add": ""},
            }],
            grid_wrapper_class="settings-master-wrap",
            grid_wrapper_attrs={
                "data-master-type": "lead_sources",
                "data-save-url": url_for("save_lead_source"),
            },
            row_id_field="source_uuid",
            action_id_field="source_uuid",
            bulk_delete_url=url_for("delete_selected_lead_sources"),
            page_size=10,
            page_size_options=get_page_size_options(),
            status_field="status",
            active_values=[1, "1", True],
            active_group="settings",
            active_page="setting_lead_sources",
            page_title="Lead Sources",
            page_heading="Lead Sources",
            modal_id="leadSourceModal",
            modal_title="Lead Source",
            add_title="Add Lead Source",
            form_type="lead_source",
        )

    @require_permission('settings', 'lead_management')
    @app.route("/settings/api/lead-sources/save", methods=["POST"])
    def save_lead_source():
        payload = request.get_json(silent=True) or {}
        source_uuid = payload.get("record_uuid")
        source_name = (payload.get("source_name") or "").strip()
        if not source_name:
            return json_error("Lead source name is required.")

        try:
            status = parse_int(payload.get("status", 1), "Status", 0, 1)
        except ValueError as error:
            return json_error(str(error))

        conn = get_db_connection()
        with conn.cursor() as cursor:
            if source_uuid:
                cursor.execute("SELECT source_name FROM lead_sources WHERE source_uuid = %s LIMIT 1", (source_uuid,))
                existing = cursor.fetchone()
                if not existing:
                    conn.close()
                    return json_error("Lead source not found.", 404)

                cursor.execute("""
                    SELECT 1 FROM lead_sources
                    WHERE source_name = %s AND source_uuid <> %s
                    LIMIT 1
                """, (source_name, source_uuid))
                if cursor.fetchone():
                    conn.close()
                    return json_error("This lead source already exists.")

                cursor.execute("UPDATE leads SET lead_source = %s WHERE lead_source = %s", (source_name, existing["source_name"]))
                cursor.execute("""
                    UPDATE lead_sources
                    SET source_name = %s, status = %s
                    WHERE source_uuid = %s
                """, (source_name, status, source_uuid))
                message = "Lead source updated successfully."
            else:
                cursor.execute("SELECT 1 FROM lead_sources WHERE source_name = %s LIMIT 1", (source_name,))
                if cursor.fetchone():
                    conn.close()
                    return json_error("This lead source already exists.")
                cursor.execute("""
                    INSERT INTO lead_sources (source_uuid, source_name, status)
                    VALUES (%s, %s, %s)
                """, (make_unique_code(cursor, "lead_sources", "source_uuid", "LSRC"), source_name, status))
                message = "Lead source added successfully."

        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": message})

    @app.route("/settings/api/lead-sources/delete-selected", methods=["POST"])
    def delete_selected_lead_sources():
        payload = request.get_json(silent=True) or {}
        source_uuids = [str(value or "").strip() for value in payload.get("ids", []) if str(value or "").strip()]
        if not source_uuids:
            return json_error("No lead sources selected.")

        placeholders = ", ".join(["%s"] * len(source_uuids))
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(f"""
                DELETE s
                FROM lead_sources s
                LEFT JOIN leads l ON l.lead_source = s.source_name
                WHERE s.source_uuid IN ({placeholders})
                  AND l.id IS NULL
            """, source_uuids)
            deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        skipped_count = len(source_uuids) - deleted_count
        message = f"{deleted_count} lead source(s) deleted."
        if skipped_count:
            message += f" {skipped_count} skipped because leads are using them."
        return jsonify({"success": True, "message": message})
