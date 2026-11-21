import json

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


PERMISSION_STRUCTURE = [
    {
        "menu": "Leads",
        "key": "leads",
        "actions": [
            {"label": "Add Lead", "key": "add"},
            {"label": "Edit Info", "key": "edit"},
            {"label": "Delete", "key": "delete"},
            {"label": "Export", "key": "export"},
            {"label": "Assign Lead", "key": "transfer"},
            {"label": "Dispose Lead", "key": "dispose"},
            {"label": "Assign Disposed Lead", "key": "assign_disposed_lead"},
            {"label": "View History", "key": "view_history"}
        ]
    },
    {
        "menu": "Follow-ups",
        "key": "followups",
        "actions": [
            {"label": "Create", "key": "create"},
            {"label": "Edit", "key": "edit"},
            {"label": "Delete", "key": "delete"},
            {"label": "Assign Follow-up", "key": "transfer"},
            {"label": "Export", "key": "export"}
        ]
    },
    {
        "menu": "Free Trials",
        "key": "free_trials",
        "actions": [
            {"label": "Create", "key": "create"},
            {"label": "Edit", "key": "edit"},
            {"label": "Delete", "key": "delete"},
            {"label": "Assign Free Trial", "key": "transfer"},
            {"label": "Export", "key": "export"}
        ]
    },
    {
        "menu": "Sales Orders",
        "key": "payments",
        "actions": [
            {"label": "Add Sales Order", "key": "add"},
            {"label": "Edit Sales Order", "key": "edit"},
            {"label": "Delete", "key": "delete"},
            {"label": "Back Date Sales Order", "key": "back_date_sales_order"},
            {"label": "Manual Expiry Date Select", "key": "manual_expiry_date"},
            {"label": "SO Approve", "key": "so_approve"}
        ]
    },
    {
        "menu": "Clients",
        "key": "clients",
        "actions": [
            {"label": "Add Client", "key": "add"},
            {"label": "Edit Client", "key": "edit"},
            {"label": "Delete", "key": "delete"}
        ]
    },
    {
        "menu": "Contacts",
        "key": "contacts",
        "actions": [
            {"label": "Add Contact", "key": "add"},
            {"label": "Edit Contact", "key": "edit"},
            {"label": "Delete", "key": "delete"},
            {"label": "Assign Contact", "key": "transfer"}
        ]
    },
    {
        "menu": "Email",
        "key": "email",
        "actions": [
            {"label": "Compose / Send Email", "key": "send"},
            {"label": "Select All Users", "key": "select_all_users"},
            {"label": "Delete Email", "key": "delete"}
        ]
    },
    {
        "menu": "WhatsApp",
        "key": "whatsapp",
        "actions": []
    },
    {
        "menu": "Internal Chat",
        "key": "chat",
        "actions": []
    },
    {
        "menu": "Research",
        "key": "research",
        "actions": []
    },
    {
        "menu": "Handbook",
        "key": "handbook",
        "actions": [
            {"label": "Add Handbook", "key": "add"},
            {"label": "Edit Handbook", "key": "edit"},
            {"label": "Delete Handbook", "key": "delete"}
        ]
    },
    {
        "menu": "Call Summary",
        "key": "call_summary",
        "actions": []
    },
    {
        "menu": "Call History",
        "key": "call_history",
        "actions": []
    },
    {
        "menu": "Reports",
        "key": "reports",
        "actions": [
            {"label": "Lead Report", "key": "lead_report"},
            {"label": "Sales Report", "key": "sales_report"},
            {"label": "Employee Report", "key": "employee_report"},
            {"label": "User Report", "key": "user_report"}
        ]
    },
    {
        "menu": "Lead Upload",
        "key": "operations",
        "actions": [
            {"label": "Upload Leads", "key": "upload_leads"},
            {"label": "Paste Leads", "key": "paste_leads"}
        ]
    },
    {
        "menu": "Settings",
        "key": "settings",
        "actions": [
            {"label": "User Management", "key": "user_management"},
            {"label": "Lead Management", "key": "lead_management"},
            {"label": "Calling Management", "key": "calling_management"},
            {"label": "System Management", "key": "system_controls"}
        ]
    },
    {
        "menu": "Global Access Scope",
        "key": "global_access_scope",
        "is_menu": False,
        "actions": [
            {"label": "Global Data Access", "key": "global_data_access"},
            {"label": "Global Data Export", "key": "global_data_export"},
            {"label": "Outside Office Login", "key": "outside_login"}
        ]
    }
]


def fetch_role_rows(cursor):
    cursor.execute("""
        SELECT
            r.role_uuid,
            r.role_name,
            r.permissions,
            r.status,
            r.created_at,
            r.updated_at,
            COUNT(u.id) AS user_count
        FROM roles r
        LEFT JOIN users u ON u.role_id = r.id
        GROUP BY r.id, r.role_uuid, r.role_name, r.permissions, r.status, r.created_at, r.updated_at
        ORDER BY r.id DESC
    """)
    return serialize_rows(cursor.fetchall())


def get_role_columns():
    return [
        {"headerName": "Role Name", "field": "role_name", "minWidth": 220, "flex": 1.3},
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


def get_role_grid_context(rows):
    return {
        "grid_id": "rolesGrid",
        "data": rows,
        "columns": get_role_columns(),
        "filters": get_status_filter(),
        "toolbar_buttons": [
            {
                "type": "button",
                "label": "Add Role",
                "icon": "mdi mdi-plus",
                "class": "btn btn-outline-primary",
                "attrs": {"data-master-add": ""},
            }
        ],
        "grid_wrapper_class": "settings-master-wrap",
        "grid_wrapper_attrs": {
            "data-master-type": "roles",
            "data-save-url": url_for("save_role"),
            "data-users-url-template": "/settings/user/api/roles/__id__/users",
            "data-edit-url-template": url_for("edit_user", user_key="__key__"),
        },
        "row_id_field": "role_uuid",
        "action_id_field": "role_uuid",
        "bulk_delete_url": url_for("delete_selected_roles"),
        "page_size": 10,
        "page_size_options": get_page_size_options(),
        "status_field": "status",
        "active_values": [1, "1", True],
    }


def role_permission_routes(app):
    @require_permission('settings', 'user_management')
    @app.route("/settings/user/roles")
    def setting_roles():
        conn = get_db_connection()
        with conn.cursor() as cursor:
            rows = fetch_role_rows(cursor)
        conn.close()

        return render_template(
            "settings/roles_settings.html",
            roles=rows,
            active_group="settings",
            active_page="setting_roles",
            page_title="Roles"
        )

    @require_permission('settings', 'user_management')
    @app.route("/settings/user/roles/add", endpoint="add_role_page")
    def add_role_page():
        return render_template(
            "settings/role_form.html",
            role=None,
            permission_structure=PERMISSION_STRUCTURE,
            active_group="settings",
            active_page="setting_roles",
            page_title="Add Role"
        )

    @require_permission('settings', 'user_management')
    @app.route("/settings/user/roles/edit/<role_uuid>", endpoint="edit_role_page")
    def edit_role_page(role_uuid):
        conn = get_db_connection()
        role = None
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM roles WHERE role_uuid = %s
            """, (role_uuid,))
            role = cursor.fetchone()
        conn.close()

        if not role:
            return "Role not found", 404

        if role.get("permissions") and isinstance(role["permissions"], str):
            import json
            try:
                role["permissions"] = json.loads(role["permissions"])
            except:
                role["permissions"] = {}

        return render_template(
            "settings/role_form.html",
            role=role,
            permission_structure=PERMISSION_STRUCTURE,
            active_group="settings",
            active_page="setting_roles",
            page_title="Edit Role"
        )

    @require_permission('settings', 'user_management')
    @app.route("/settings/user/api/roles")
    def roles_data():
        conn = get_db_connection()
        with conn.cursor() as cursor:
            rows = fetch_role_rows(cursor)
        conn.close()
        return jsonify({"success": True, "data": rows})

    @app.route("/settings/api/roles/delete-selected", methods=["POST"])
    @app.route("/settings/user/api/roles/delete-selected", methods=["POST"])
    @require_permission('settings', 'user_management')
    def delete_selected_roles():
        payload = request.get_json(silent=True) or {}
        role_uuids = sorted({
            str(value or "").strip()
            for value in payload.get("ids", [])
            if str(value or "").strip()
        })

        if not role_uuids:
            return json_error("No roles selected.")

        placeholders = ", ".join(["%s"] * len(role_uuids))
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Safety check: Block deletion if any active user is assigned to any selected role
            cursor.execute(f"""
                SELECT r.role_name, COUNT(u.id) AS assigned_users_count
                FROM roles r
                JOIN users u ON u.role_id = r.id
                WHERE r.role_uuid IN ({placeholders}) AND (u.status = 1 OR u.status IS NULL)
                GROUP BY r.id, r.role_name
            """, role_uuids)
            assigned_roles = cursor.fetchall() or []

            if assigned_roles:
                role_details = ", ".join([f"'{r['role_name']}' ({r['assigned_users_count']} user(s))" for r in assigned_roles])
                conn.close()
                return jsonify({
                    "success": False,
                    "message": f"Cannot delete role: Active users are currently assigned to {role_details}. Reassign these users to another role before deleting."
                }), 400

            cursor.execute(f"""
                DELETE FROM roles
                WHERE role_uuid IN ({placeholders})
            """, role_uuids)
            deleted_count = cursor.rowcount

        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": f"{deleted_count} role(s) deleted successfully."})

    @require_permission('settings', 'user_management')
    @app.route("/settings/user/api/roles/save", methods=["POST"])
    def save_role():
        payload = request.get_json(silent=True) or {}
        role_uuid = payload.get("record_uuid")
        role_name = (payload.get("role_name") or "").strip()
        permissions = payload.get("permissions") or {}
        status = payload.get("status", 1)

        if not role_name:
            return json_error("Role name is required.")

        if not isinstance(permissions, dict):
            permissions = {}

        try:
            status = parse_int(status, "Status", 0, 1)
        except ValueError as error:
            return json_error(str(error))

        conn = get_db_connection()
        with conn.cursor() as cursor:
            if role_uuid:
                cursor.execute("""
                    UPDATE roles
                    SET role_name = %s, permissions = %s, status = %s
                    WHERE role_uuid = %s
                """, (role_name, json.dumps(permissions), status, role_uuid))
                message = "Role updated successfully."
            else:
                role_uuid = make_unique_code(cursor, "roles", "role_uuid", "ROL")
                cursor.execute("""
                    INSERT INTO roles (role_uuid, role_name, permissions, status)
                    VALUES (%s, %s, %s, %s)
                """, (role_uuid, role_name, json.dumps(permissions), status))
                message = "Role added successfully."
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": message})

    @require_permission('settings', 'user_management')
    @app.route("/settings/user/api/roles/<role_uuid>/users")
    def role_users(role_uuid):
        conn = get_db_connection()
        with conn.cursor() as cursor:
            role_id = resolve_uuid_to_id(cursor, "roles", "role_uuid", role_uuid)
            if not role_id:
                conn.close()
                return json_error("Role not found.", 404)
            rows = fetch_assigned_users(cursor, "role_id", role_id)
        conn.close()
        return jsonify({"success": True, "data": rows})
