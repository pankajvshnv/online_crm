from utils.permissions import require_permission
from flask import jsonify, render_template, request, redirect, url_for, flash

from config import get_db_connection
from routes.settings_helpers import (
    get_page_size_options,
    json_error,
    make_unique_code,
    parse_int,
    resolve_uuid_to_id,
    serialize_rows,
)


def fetch_extension_rows(cursor):
    cursor.execute("""
        SELECT
            e.id,
            e.extension_uuid,
            e.extension_number,
            e.calling_api_id,
            c.api_name AS calling_api_name,
            c.provider_type AS calling_api_provider,
            e.account_id,
            e.did_number,
            e.status,
            u.full_name AS assigned_user_name,
            u.user_uuid AS assigned_user_uuid
        FROM extensions e
        LEFT JOIN calling_apis c
            ON c.id = e.calling_api_id
        LEFT JOIN users u
            ON u.extension_id = e.id
        ORDER BY e.extension_number ASC
    """)

    return serialize_rows(cursor.fetchall())


def fetch_calling_apis(cursor):
    cursor.execute("""
        SELECT
            id,
            calling_api_uuid,
            api_name,
            provider_type
        FROM calling_apis
        WHERE status = 1
        ORDER BY api_name ASC
    """)

    return serialize_rows(cursor.fetchall())


def get_extension_columns():
    return [
        {
            "headerName": "Extension Number",
            "field": "extension_number",
            "minWidth": 160,
            "flex": 1,
        },
        {
            "headerName": "Calling API",
            "field": "calling_api_name",
            "minWidth": 160,
            "flex": 1,
        },
        {
            "headerName": "DID / Caller ID",
            "field": "did_number",
            "minWidth": 160,
            "flex": 1,
        },
        {
            "headerName": "Assigned User",
            "field": "assigned_user_name",
            "minWidth": 190,
            "flex": 1,
        },
        {
            "headerName": "Status",
            "field": "status",
            "minWidth": 120,
            "flex": 0.5,
            "renderer": "statusBadge",
        },
    ]


def get_extension_grid_context(rows, calling_apis):
    return {
        "grid_id": "extensionsGrid",
        "data": rows,
        "columns": get_extension_columns(),
        "filters": [
            {
                "name": "status",
                "label": "Status",
                "options": [
                    {
                        "value": "1",
                        "label": "Active",
                    },
                    {
                        "value": "0",
                        "label": "Inactive",
                    },
                ],
            },
            {
                "name": "calling_api_id",
                "label": "Calling API",
                "options": [
                    {
                        "value": api["id"],
                        "label": api["api_name"],
                    }
                    for api in calling_apis
                ],
            },
        ],
        "toolbar_buttons": [
            {
                "type": "link",
                "label": "Add Extensions",
                "icon": "mdi mdi-plus",
                "class": "btn btn-outline-primary",
                "url": url_for("add_extension"),
            }
        ],
        "grid_wrapper_class": "settings-master-wrap",
        "grid_wrapper_attrs": {
            "data-master-type": "extensions",
        },
        "row_id_field": "extension_uuid",
        "action_id_field": "extension_uuid",
        "edit_url": "/settings/calling/extensions/edit/",
        "delete_url": "/settings/calling/extensions/delete/",
        "bulk_delete_url": url_for("delete_selected_extensions"),
        "page_size": 10,
        "page_size_options": get_page_size_options(),
        "status_field": "status",
        "active_values": [1, "1", True],
    }


def extension_routes(app):

    @require_permission('settings', 'calling_management')
    @app.route(
        "/settings/calling/extensions",
        endpoint="setting_extensions",
    )
    def setting_extensions():
        conn = get_db_connection()

        with conn.cursor() as cursor:
            calling_apis = fetch_calling_apis(cursor)

        conn.close()

        return render_template(
            "settings/extensions.html",
            calling_apis=calling_apis,
            active_group="settings",
            active_page="setting_extensions",
            page_title="Extensions",
            page_heading="Extensions",
        )

    @require_permission('settings', 'calling_management')
    @app.route(
        "/settings/api/extensions/list",
        methods=["GET", "POST"],
        endpoint="api_extensions_list",
    )
    def api_extensions_list():
        import math
        payload = request.get_json(silent=True) or {}
        args = request.args

        try:
            page = int(payload.get("page") or args.get("page") or 1)
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = int(payload.get("page_size") or args.get("page_size") or 10)
        except (ValueError, TypeError):
            page_size = 10

        search = str(payload.get("search") or args.get("search") or "").strip()
        status = str(payload.get("status") or args.get("status") or "all").strip()
        api_id = str(payload.get("api_id") or args.get("api_id") or "all").strip()

        if page < 1:
            page = 1
        if page_size not in [10, 25, 50, 100]:
            page_size = 10

        offset = (page - 1) * page_size

        where_clauses = ["1=1"]
        params = []

        if status in ["0", "1"]:
            where_clauses.append("e.status = %s")
            params.append(int(status))

        if api_id != "all" and api_id.isdigit():
            where_clauses.append("e.calling_api_id = %s")
            params.append(int(api_id))

        if search:
            search_pattern = f"%{search}%"
            where_clauses.append("""(
                CAST(e.extension_number AS CHAR) LIKE %s 
                OR e.did_number LIKE %s 
                OR e.account_id LIKE %s 
                OR u.full_name LIKE %s 
                OR c.api_name LIKE %s
            )""")
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern, search_pattern])

        where_sql = " AND ".join(where_clauses)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            count_sql = f"""
                SELECT COUNT(*) as total
                FROM extensions e
                LEFT JOIN calling_apis c ON c.id = e.calling_api_id
                LEFT JOIN users u ON u.extension_id = e.id
                WHERE {where_sql}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()["total"]

            data_sql = f"""
                SELECT
                    e.id,
                    e.extension_uuid,
                    e.extension_number,
                    e.calling_api_id,
                    c.api_name AS calling_api_name,
                    c.provider_type AS calling_api_provider,
                    e.account_id,
                    e.did_number,
                    e.status,
                    u.full_name AS assigned_user_name,
                    u.user_uuid AS assigned_user_uuid
                FROM extensions e
                LEFT JOIN calling_apis c ON c.id = e.calling_api_id
                LEFT JOIN users u ON u.extension_id = e.id
                WHERE {where_sql}
                ORDER BY e.extension_number ASC
                LIMIT %s OFFSET %s
            """
            cursor.execute(data_sql, params + [page_size, offset])
            rows = serialize_rows(cursor.fetchall())

        conn.close()

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return jsonify({
            "success": True,
            "data": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        })

    @require_permission('settings', 'calling_management')
    @app.route(
        "/settings/calling/extensions/add",
        methods=["GET", "POST"],
        endpoint="add_extension",
    )
    def add_extension():
        conn = get_db_connection()

        if request.method == "POST":
            try:
                calling_api_id = parse_int(
                    request.form.get("calling_api_id"),
                    "Calling API",
                    1,
                )

                start_number = parse_int(
                    request.form.get("start_number"),
                    "Starting range",
                    1,
                )

                count = parse_int(
                    request.form.get("count"),
                    "Step count",
                    1,
                    50,
                )

                status = parse_int(
                    request.form.get("status", 1),
                    "Status",
                    0,
                    1,
                )

                extension_password = request.form.get("extension_password", "").strip() or None
                account_id = request.form.get("account_id", "").strip() or None
                did_number = request.form.get("did_number", "").strip() or None

            except ValueError as error:
                conn.close()
                flash(str(error), "warning")
                return redirect(url_for("add_extension"))

            numbers = []
            skipped_numbers = []
            current_number = start_number

            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id
                    FROM calling_apis
                    WHERE id = %s
                      AND status = 1
                    LIMIT 1
                """, (calling_api_id,))

                if not cursor.fetchone():
                    conn.close()

                    flash(
                        "Calling API not found.",
                        "warning",
                    )

                    return redirect(
                        url_for("add_extension")
                    )

                while len(numbers) < count:
                    cursor.execute("""
                        SELECT id
                        FROM extensions
                        WHERE extension_number = %s
                        LIMIT 1
                    """, (current_number,))

                    if cursor.fetchone():
                        skipped_numbers.append(
                            current_number
                        )
                    else:
                        numbers.append(
                            current_number
                        )

                    current_number += 1

                for number in numbers:
                    extension_uuid = make_unique_code(
                        cursor,
                        "extensions",
                        "extension_uuid",
                        "EXT",
                    )

                    cursor.execute("""
                        INSERT INTO extensions (
                            extension_uuid,
                            calling_api_id,
                            extension_number,
                            extension_password,
                            account_id,
                            did_number,
                            status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        extension_uuid,
                        calling_api_id,
                        number,
                        extension_password,
                        account_id,
                        did_number,
                        status,
                    ))

            conn.commit()
            conn.close()

            message = (
                f"{len(numbers)} extension(s) "
                f"added successfully."
            )

            if skipped_numbers:
                skipped_text = ", ".join(
                    str(number)
                    for number in skipped_numbers
                )

                message += (
                    " Existing extension(s) skipped: "
                    f"{skipped_text}."
                )

            flash(message, "success")

            return redirect(
                url_for("setting_extensions")
            )

        with conn.cursor() as cursor:
            calling_apis = fetch_calling_apis(cursor)

        conn.close()

        return render_template(
            "settings/extensions_form.html",
            calling_apis=calling_apis,
            record=None,
            form_mode="add",
            active_group="settings",
            active_page="setting_extensions",
            page_title="Add Extensions",
            page_heading="Add Extensions",
        )

    @require_permission('settings', 'calling_management')
    @app.route(
        "/settings/calling/extensions/edit/<extension_uuid>",
        methods=["GET", "POST"],
        endpoint="edit_extension",
    )
    def edit_extension(extension_uuid):
        conn = get_db_connection()

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    id,
                    extension_uuid,
                    calling_api_id,
                    extension_number,
                    extension_password,
                    account_id,
                    did_number,
                    status
                FROM extensions
                WHERE extension_uuid = %s
                LIMIT 1
            """, (extension_uuid,))

            record = cursor.fetchone()

        if not record:
            conn.close()

            flash(
                "Extension not found.",
                "warning",
            )

            return redirect(
                url_for("setting_extensions")
            )

        if request.method == "POST":
            try:
                calling_api_id = parse_int(
                    request.form.get("calling_api_id"),
                    "Calling API",
                    1,
                )

                extension_number = parse_int(
                    request.form.get("extension_number"),
                    "Extension number",
                    1,
                )

                status = parse_int(
                    request.form.get("status", 1),
                    "Status",
                    0,
                    1,
                )

                extension_password = request.form.get("extension_password", "").strip() or None
                account_id = request.form.get("account_id", "").strip() or None
                did_number = request.form.get("did_number", "").strip() or None

            except ValueError as error:
                conn.close()
                flash(str(error), "warning")

                return redirect(
                    url_for(
                        "edit_extension",
                        extension_uuid=extension_uuid,
                    )
                )

            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id
                    FROM calling_apis
                    WHERE id = %s
                      AND status = 1
                    LIMIT 1
                """, (calling_api_id,))

                if not cursor.fetchone():
                    conn.close()

                    flash(
                        "Calling API not found.",
                        "warning",
                    )

                    return redirect(
                        url_for(
                            "edit_extension",
                            extension_uuid=extension_uuid,
                        )
                    )

                extension_id = resolve_uuid_to_id(
                    cursor,
                    "extensions",
                    "extension_uuid",
                    extension_uuid,
                )

                if not extension_id:
                    conn.close()

                    flash(
                        "Extension not found.",
                        "warning",
                    )

                    return redirect(
                        url_for("setting_extensions")
                    )

                cursor.execute("""
                    SELECT id
                    FROM extensions
                    WHERE extension_number = %s
                      AND id != %s
                    LIMIT 1
                """, (
                    extension_number,
                    extension_id,
                ))

                if cursor.fetchone():
                    conn.close()

                    flash(
                        "This extension number already exists.",
                        "warning",
                    )

                    return redirect(
                        url_for(
                            "edit_extension",
                            extension_uuid=extension_uuid,
                        )
                    )

                cursor.execute("""
                    UPDATE extensions
                    SET
                        calling_api_id = %s,
                        extension_number = %s,
                        extension_password = %s,
                        account_id = %s,
                        did_number = %s,
                        status = %s
                    WHERE extension_uuid = %s
                """, (
                    calling_api_id,
                    extension_number,
                    extension_password,
                    account_id,
                    did_number,
                    status,
                    extension_uuid,
                ))

            conn.commit()
            conn.close()

            flash(
                "Extension updated successfully.",
                "success",
            )

            return redirect(
                url_for("setting_extensions")
            )

        with conn.cursor() as cursor:
            calling_apis = fetch_calling_apis(cursor)

        conn.close()

        return render_template(
            "settings/extensions_form.html",
            calling_apis=calling_apis,
            record=record,
            form_mode="edit",
            active_group="settings",
            active_page="setting_extensions",
            page_title="Edit Extension",
            page_heading="Edit Extension",
        )

    @require_permission('settings', 'calling_management')
    @app.route(
        "/settings/calling/extensions/delete/<extension_uuid>",
        methods=["GET", "POST"],
        endpoint="delete_extension",
    )
    def delete_extension(extension_uuid):
        conn = get_db_connection()

        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE FROM extensions
                WHERE extension_uuid = %s
            """, (extension_uuid,))

            deleted_count = cursor.rowcount

        conn.commit()
        conn.close()

        if deleted_count:
            flash(
                "Extension deleted successfully.",
                "success",
            )
        else:
            flash(
                "Extension not found.",
                "warning",
            )

        return redirect(
            url_for("setting_extensions")
        )

    @require_permission('settings', 'calling_management')
    @app.route(
        "/settings/api/extensions/delete-selected",
        methods=["POST"],
        endpoint="delete_selected_extensions",
    )
    def delete_selected_extensions():
        payload = request.get_json(silent=True) or {}

        extension_uuids = sorted({
            str(value or "").strip()
            for value in payload.get("ids", [])
            if str(value or "").strip()
        })

        if not extension_uuids:
            return json_error(
                "No extensions selected."
            )

        placeholders = ", ".join(
            ["%s"] * len(extension_uuids)
        )

        conn = get_db_connection()

        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                    DELETE FROM extensions
                    WHERE extension_uuid IN ({placeholders})
                """,
                extension_uuids,
            )

            deleted_count = cursor.rowcount

        conn.commit()
        conn.close()

        skipped_count = (
            len(extension_uuids) - deleted_count
        )

        message = (
            f"{deleted_count} extension(s) deleted."
        )

        if skipped_count:
            message += (
                f" {skipped_count} skipped because "
                "records were not found."
            )

        return jsonify({
            "success": True,
            "message": message,
        })