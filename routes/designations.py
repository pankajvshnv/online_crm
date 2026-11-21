from utils.permissions import require_permission
from flask import jsonify, render_template, request, url_for

from config import get_db_connection
from routes.settings_helpers import (
    fetch_assigned_users,
    get_page_size_options,
    get_status_filter,
    json_error,
    make_unique_code,
    parse_int,
    resolve_uuid_to_id,
    serialize_rows,
)


def fetch_designation_rows(cursor):
    cursor.execute("""
        SELECT
            d.designation_uuid,
            d.designation_name,
            d.status,
            d.created_at,
            d.updated_at,
            COUNT(u.id) AS user_count
        FROM designations d
        LEFT JOIN users u ON u.designation_id = d.id
        GROUP BY d.id, d.designation_uuid, d.designation_name, d.status, d.created_at, d.updated_at
        ORDER BY d.id DESC
    """)
    return serialize_rows(cursor.fetchall())


def get_designation_columns():
    return [
        {"headerName": "Designation Name", "field": "designation_name", "minWidth": 220, "flex": 1.3},
        {
            "headerName": "Assigned Users",
            "field": "user_count",
            "minWidth": 150,
            "flex": 0.7,
            "renderer": "settingsUserCount",
        },
        {
            "headerName": "Status",
            "field": "status",
            "minWidth": 120,
            "flex": 0.5,
            "renderer": "statusBadge",
        },
        {
            "headerName": "Action",
            "field": "action",
            "minWidth": 110,
            "sortable": False,
            "filter": False,
            "renderer": "settingsMasterAction",
        },
    ]


def get_designation_grid_context(rows):
    return {
        "grid_id": "designationsGrid",
        "data": rows,
        "columns": get_designation_columns(),
        "filters": get_status_filter(),
        "toolbar_buttons": [
            {
                "type": "button",
                "label": "Add Designation",
                "icon": "mdi mdi-plus",
                "class": "btn btn-outline-primary",
                "attrs": {"data-master-add": ""},
            }
        ],
        "grid_wrapper_class": "settings-master-wrap",
        "grid_wrapper_attrs": {
            "data-master-type": "designations",
            "data-save-url": url_for("save_designation"),
            "data-users-url-template": "/settings/api/designations/__id__/users",
            "data-edit-url-template": url_for("edit_user", user_key="__key__"),
        },
        "row_id_field": "designation_uuid",
        "action_id_field": "designation_uuid",
        "bulk_delete_url": url_for("delete_selected_designations"),
        "page_size": 10,
        "page_size_options": get_page_size_options(),
        "status_field": "status",
        "active_values": [1, "1", True],
    }


def designation_routes(app):
    @require_permission('settings', 'user_management')
    @app.route("/settings/user/designations")
    def setting_designations():
        conn = get_db_connection()
        with conn.cursor() as cursor:
            rows = fetch_designation_rows(cursor)
        conn.close()

        return render_template(
            "settings/master_page.html",
            **get_designation_grid_context(rows),
            active_group="settings",
            active_page="setting_designations",
            page_title="Designations",
            page_heading="Designations",
            master_type="designations",
            modal_id="designationModal",
            modal_title="Designation",
            add_title="Add Designation",
            form_type="designation",
        )

    @require_permission('settings', 'user_management')
    @app.route("/settings/user/api/designations")
    def designations_data():
        conn = get_db_connection()
        with conn.cursor() as cursor:
            rows = fetch_designation_rows(cursor)
        conn.close()
        return jsonify({"success": True, "data": rows})

    @require_permission('settings', 'user_management')
    @app.route("/settings/user/api/designations/delete-selected", methods=["POST"])
    def delete_selected_designations():
        payload = request.get_json(silent=True) or {}
        designation_uuids = sorted({
            str(value or "").strip()
            for value in payload.get("ids", [])
            if str(value or "").strip()
        })

        if not designation_uuids:
            return json_error("No designations selected.")

        placeholders = ", ".join(["%s"] * len(designation_uuids))
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(f"""
                DELETE FROM designations
                WHERE designation_uuid IN ({placeholders})
                  AND id NOT IN (
                      SELECT DISTINCT designation_id
                      FROM users
                      WHERE designation_id IS NOT NULL
                  )
            """, designation_uuids)
            deleted_count = cursor.rowcount

        conn.commit()
        conn.close()

        skipped_count = len(designation_uuids) - deleted_count
        message = f"{deleted_count} designation(s) deleted."
        if skipped_count:
            message += f" {skipped_count} skipped because users are assigned or records were not found."

        return jsonify({"success": True, "message": message})

    @require_permission('settings', 'user_management')
    @app.route("/settings/user/api/designations/save", methods=["POST"])
    def save_designation():
        payload = request.get_json(silent=True) or {}
        designation_uuid = payload.get("record_uuid")
        designation_name = (payload.get("designation_name") or "").strip()
        status = payload.get("status", 1)

        if not designation_name:
            return json_error("Designation name is required.")

        try:
            status = parse_int(status, "Status", 0, 1)
        except ValueError as error:
            return json_error(str(error))

        conn = get_db_connection()
        with conn.cursor() as cursor:
            if designation_uuid:
                cursor.execute("""
                    UPDATE designations
                    SET designation_name = %s, status = %s
                    WHERE designation_uuid = %s
                """, (designation_name, status, designation_uuid))
                message = "Designation updated successfully."
            else:
                designation_uuid = make_unique_code(cursor, "designations", "designation_uuid", "DSG")
                cursor.execute("""
                    INSERT INTO designations (designation_uuid, designation_name, status)
                    VALUES (%s, %s, %s)
                """, (designation_uuid, designation_name, status))
                message = "Designation added successfully."
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": message})

    @require_permission('settings', 'user_management')
    @app.route("/settings/user/api/designations/<designation_uuid>/users")
    def designation_users(designation_uuid):
        conn = get_db_connection()
        with conn.cursor() as cursor:
            designation_id = resolve_uuid_to_id(cursor, "designations", "designation_uuid", designation_uuid)
            if not designation_id:
                conn.close()
                return json_error("Designation not found.", 404)
            rows = fetch_assigned_users(cursor, "designation_id", designation_id)
        conn.close()
        return jsonify({"success": True, "data": rows})
