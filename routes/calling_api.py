from utils.permissions import require_permission
from flask import render_template, request, redirect, url_for, flash, session

from config import get_db_connection
from routes.settings_helpers import (
    get_page_size_options,
    make_unique_code,
    parse_int,
    serialize_rows,
)


def fetch_calling_api_rows(cursor):
    cursor.execute("""
        SELECT
            c.calling_api_uuid,
            c.api_name,
            c.api_link,
            c.provider_type,
            c.token_id,
            c.default_did,
            c.server_host,
            c.server_username,
            c.server_db_name,
            c.source_variable,
            c.destination_variable,
            c.status,
            c.created_by,
            u.full_name AS created_by_name
        FROM calling_apis c
        LEFT JOIN users u
            ON u.user_uuid = c.created_by
        ORDER BY c.id DESC
    """)
    return serialize_rows(cursor.fetchall())


def get_calling_api_columns():
    return [
        {
            "headerName": "API Name",
            "field": "api_name",
            "minWidth": 200,
            "flex": 1,
        },
        {
            "headerName": "Provider",
            "field": "provider_type",
            "minWidth": 150,
            "flex": 0.6,
        },
        {
            "headerName": "Server Host / Link",
            "field": "server_host",
            "minWidth": 170,
            "flex": 0.8,
        },
        {
            "headerName": "DID Number",
            "field": "default_did",
            "minWidth": 130,
            "flex": 0.5,
        },
        {
            "headerName": "Status",
            "field": "status",
            "minWidth": 100,
            "flex": 0.4,
            "renderer": "statusBadge",
        },
    ]


def get_calling_api_grid_context(rows):
    return {
        "grid_id": "callingApisGrid",
        "data": rows,
        "columns": get_calling_api_columns(),
        "filters": [],
        "toolbar_buttons": [
            {
                "type": "link",
                "label": "Add New Api",
                "icon": "mdi mdi-plus",
                "class": "btn btn-outline-primary",
                "url": url_for("add_calling_api"),
            }
        ],
        "grid_wrapper_class": "settings-master-wrap",
        "grid_wrapper_attrs": {
            "data-master-type": "calling_apis",
        },
        "row_id_field": "calling_api_uuid",
        "action_id_field": "calling_api_uuid",
        "edit_url": "/settings/calling/apis/edit/",
        "delete_url": "/settings/calling/apis/delete/",
        "page_size": 10,
        "page_size_options": get_page_size_options(),
        "status_field": "status",
        "active_values": [1, "1", True],
    }


def calling_apis(app):

    @app.route("/settings/calling/apis", endpoint="calling_apis")
    def setting_calling_apis():
        conn = get_db_connection()

        with conn.cursor() as cursor:
            rows = fetch_calling_api_rows(cursor)

        conn.close()

        return render_template(
            "settings/calling_apis.html",
            calling_apis=rows,
            **get_calling_api_grid_context(rows),
            active_group="settings",
            active_page="calling_apis",
            page_title="Calling APIs",
            page_heading="Calling APIs",
        )

    @require_permission('settings', 'calling_management')
    @app.route(
        "/settings/calling/apis/add",
        methods=["GET", "POST"],
        endpoint="add_calling_api",
    )
    def add_calling_api():
        conn = get_db_connection()

        if request.method == "POST":
            provider_type = (request.form.get("provider_type") or "issabel").strip().lower()
            token_id = (request.form.get("token_id") or "").strip()
            default_did = (request.form.get("default_did") or "").strip()
            api_name = (request.form.get("api_name") or "").strip()
            api_link = (request.form.get("api_link") or "").strip()
            server_host = (request.form.get("server_host") or "").strip()
            server_username = (request.form.get("server_username") or "").strip()
            server_password = (request.form.get("server_password") or "").strip()
            server_db_name = (request.form.get("server_db_name") or "").strip()
            source_variable = (request.form.get("source_variable") or "").strip()
            destination_variable = (request.form.get("destination_variable") or "").strip()
            created_by = session.get("user_uuid")

            if not api_name:
                conn.close()
                flash("API name is required.", "warning")
                return redirect(url_for("add_calling_api"))

            if provider_type == "cloudconnect":
                if not api_link:
                    api_link = "https://crm2.cloud-connect.in/ccpl_api/v1.4/api/info/click2call"
                if not server_host:
                    server_host = "https://crm2.cloud-connect.in"
                if not token_id:
                    conn.close()
                    flash("CloudConnect Token ID is required.", "warning")
                    return redirect(url_for("add_calling_api"))
                if not server_db_name:
                    server_db_name = "cloudconnect"
                if not source_variable:
                    source_variable = "extension_number"
                if not destination_variable:
                    destination_variable = "phone_number"
            else:
                if not api_link:
                    conn.close()
                    flash("API link is required.", "warning")
                    return redirect(url_for("add_calling_api"))
                if not server_host:
                    conn.close()
                    flash("Server host is required.", "warning")
                    return redirect(url_for("add_calling_api"))
                if not server_username:
                    conn.close()
                    flash("Server username is required.", "warning")
                    return redirect(url_for("add_calling_api"))
                if not server_password:
                    conn.close()
                    flash("Server password is required.", "warning")
                    return redirect(url_for("add_calling_api"))
                if not server_db_name:
                    conn.close()
                    flash("Server DB name is required.", "warning")
                    return redirect(url_for("add_calling_api"))
                if not source_variable:
                    conn.close()
                    flash("Source variable is required.", "warning")
                    return redirect(url_for("add_calling_api"))
                if not destination_variable:
                    conn.close()
                    flash("Destination variable is required.", "warning")
                    return redirect(url_for("add_calling_api"))

            try:
                status = parse_int(
                    request.form.get("status", 1),
                    "Status",
                    0,
                    1,
                )
            except ValueError as error:
                conn.close()
                flash(str(error), "warning")
                return redirect(url_for("add_calling_api"))

            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT calling_api_uuid
                    FROM calling_apis
                    WHERE api_name = %s
                    LIMIT 1
                """, (api_name,))

                if cursor.fetchone():
                    conn.close()
                    flash("This API name already exists.", "warning")
                    return redirect(url_for("add_calling_api"))

                calling_api_uuid = make_unique_code(
                    cursor,
                    "calling_apis",
                    "calling_api_uuid",
                    "CAPI",
                )

                cursor.execute("""
                    INSERT INTO calling_apis (
                        calling_api_uuid,
                        api_name,
                        api_link,
                        provider_type,
                        token_id,
                        default_did,
                        server_host,
                        server_username,
                        server_password,
                        server_db_name,
                        source_variable,
                        destination_variable,
                        status,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    calling_api_uuid,
                    api_name,
                    api_link,
                    provider_type,
                    token_id,
                    default_did,
                    server_host,
                    server_username,
                    server_password,
                    server_db_name,
                    source_variable,
                    destination_variable,
                    status,
                    created_by,
                ))

            conn.commit()
            conn.close()

            flash("Calling API added successfully.", "success")
            return redirect(url_for("calling_apis"))

        conn.close()

        return render_template(
            "settings/calling_api_form.html",
            record=None,
            form_mode="add",
            active_group="settings",
            active_page="calling_apis",
            page_title="Add Calling API",
            page_heading="Add Calling API",
        )

    @require_permission('settings', 'calling_management')
    @app.route(
        "/settings/calling/apis/edit/<calling_api_uuid>",
        methods=["GET", "POST"],
        endpoint="edit_calling_api",
    )
    def edit_calling_api(calling_api_uuid):
        conn = get_db_connection()

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    calling_api_uuid,
                    api_name,
                    api_link,
                    provider_type,
                    token_id,
                    default_did,
                    server_host,
                    server_username,
                    server_password,
                    server_db_name,
                    source_variable,
                    destination_variable,
                    status,
                    created_by
                FROM calling_apis
                WHERE calling_api_uuid = %s
                LIMIT 1
            """, (calling_api_uuid,))

            record = cursor.fetchone()

        if not record:
            conn.close()
            flash("Calling API not found.", "warning")
            return redirect(url_for("calling_apis"))

        if request.method == "POST":
            provider_type = (request.form.get("provider_type") or "issabel").strip().lower()
            token_id = (request.form.get("token_id") or "").strip()
            default_did = (request.form.get("default_did") or "").strip()
            api_name = (request.form.get("api_name") or "").strip()
            api_link = (request.form.get("api_link") or "").strip()
            server_host = (request.form.get("server_host") or "").strip()
            server_username = (request.form.get("server_username") or "").strip()
            server_password = (request.form.get("server_password") or "").strip()
            server_db_name = (request.form.get("server_db_name") or "").strip()
            source_variable = (request.form.get("source_variable") or "").strip()
            destination_variable = (request.form.get("destination_variable") or "").strip()

            if not api_name:
                conn.close()
                flash("API name is required.", "warning")
                return redirect(url_for("edit_calling_api", calling_api_uuid=calling_api_uuid))

            if provider_type == "cloudconnect":
                if not api_link:
                    api_link = "https://crm2.cloud-connect.in/ccpl_api/v1.4/api/info/click2call"
                if not server_host:
                    server_host = "https://crm2.cloud-connect.in"
                if not token_id:
                    conn.close()
                    flash("CloudConnect Token ID is required.", "warning")
                    return redirect(url_for("edit_calling_api", calling_api_uuid=calling_api_uuid))
                if not server_db_name:
                    server_db_name = "cloudconnect"
                if not source_variable:
                    source_variable = "extension_number"
                if not destination_variable:
                    destination_variable = "phone_number"
            else:
                if not api_link:
                    conn.close()
                    flash("API link is required.", "warning")
                    return redirect(url_for("edit_calling_api", calling_api_uuid=calling_api_uuid))
                if not server_host:
                    conn.close()
                    flash("Server host is required.", "warning")
                    return redirect(url_for("edit_calling_api", calling_api_uuid=calling_api_uuid))
                if not server_username:
                    conn.close()
                    flash("Server username is required.", "warning")
                    return redirect(url_for("edit_calling_api", calling_api_uuid=calling_api_uuid))
                if not server_password:
                    conn.close()
                    flash("Server password is required.", "warning")
                    return redirect(url_for("edit_calling_api", calling_api_uuid=calling_api_uuid))
                if not server_db_name:
                    conn.close()
                    flash("Server DB name is required.", "warning")
                    return redirect(url_for("edit_calling_api", calling_api_uuid=calling_api_uuid))
                if not source_variable:
                    conn.close()
                    flash("Source variable is required.", "warning")
                    return redirect(url_for("edit_calling_api", calling_api_uuid=calling_api_uuid))
                if not destination_variable:
                    conn.close()
                    flash("Destination variable is required.", "warning")
                    return redirect(url_for("edit_calling_api", calling_api_uuid=calling_api_uuid))

            try:
                status = parse_int(
                    request.form.get("status", 1),
                    "Status",
                    0,
                    1,
                )
            except ValueError as error:
                conn.close()
                flash(str(error), "warning")
                return redirect(url_for("edit_calling_api", calling_api_uuid=calling_api_uuid))

            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT calling_api_uuid
                    FROM calling_apis
                    WHERE api_name = %s
                      AND calling_api_uuid != %s
                    LIMIT 1
                """, (
                    api_name,
                    calling_api_uuid,
                ))

                if cursor.fetchone():
                    conn.close()
                    flash("This API name already exists.", "warning")
                    return redirect(url_for("edit_calling_api", calling_api_uuid=calling_api_uuid))

                cursor.execute("""
                    UPDATE calling_apis
                    SET
                        api_name = %s,
                        api_link = %s,
                        provider_type = %s,
                        token_id = %s,
                        default_did = %s,
                        server_host = %s,
                        server_username = %s,
                        server_password = %s,
                        server_db_name = %s,
                        source_variable = %s,
                        destination_variable = %s,
                        status = %s
                    WHERE calling_api_uuid = %s
                """, (
                    api_name,
                    api_link,
                    provider_type,
                    token_id,
                    default_did,
                    server_host,
                    server_username,
                    server_password,
                    server_db_name,
                    source_variable,
                    destination_variable,
                    status,
                    calling_api_uuid,
                ))

            conn.commit()
            conn.close()

            flash("Calling API updated successfully.", "success")
            return redirect(url_for("calling_apis"))

        conn.close()

        return render_template(
            "settings/calling_api_form.html",
            record=record,
            form_mode="edit",
            active_group="settings",
            active_page="calling_apis",
            page_title="Edit Calling API",
            page_heading="Edit Calling API",
        )

    @require_permission('settings', 'calling_management')
    @app.route(
        "/settings/calling/apis/delete/<calling_api_uuid>",
        methods=["GET", "POST"],
        endpoint="delete_calling_api",
    )
    def delete_calling_api(calling_api_uuid):
        conn = get_db_connection()

        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE FROM calling_apis
                WHERE calling_api_uuid = %s
            """, (calling_api_uuid,))

            deleted_count = cursor.rowcount

        conn.commit()
        conn.close()

        if deleted_count:
            flash("Calling API deleted successfully.", "success")
        else:
            flash("Calling API not found.", "warning")

        return redirect(url_for("calling_apis"))