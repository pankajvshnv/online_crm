from utils.permissions import require_permission
from flask import render_template, request, redirect, url_for, flash, session

from config import get_db_connection
from routes.settings_helpers import (
    get_page_size_options,
    make_unique_code,
    parse_int,
    serialize_rows,
)


def get_current_user_id(cursor):
    user_id = session.get("user_id")

    if user_id:
        return user_id

    user_uuid = session.get("user_uuid")

    if not user_uuid:
        return None

    cursor.execute("""
        SELECT id
        FROM users
        WHERE user_uuid = %s
        LIMIT 1
    """, (user_uuid,))

    user = cursor.fetchone()

    if not user:
        return None

    return user["id"]


def fetch_lead_source_limit_rows(cursor):
    cursor.execute("""
        SELECT
            l.lead_source_limits_uuid,
            l.source_id,
            s.source_uuid,
            s.source_name,
            l.role_id,
            r.role_uuid,
            r.role_name,
            l.pending_lead_limit,
            l.daily_lead_limit,
            l.fetch_lead_limit,
            l.created_by,
            u.full_name AS created_by_name
        FROM lead_source_limits l
        LEFT JOIN lead_sources s
            ON s.id = l.source_id
        LEFT JOIN roles r
            ON r.id = l.role_id
        LEFT JOIN users u
            ON u.id = l.created_by
        ORDER BY l.id DESC
    """)

    return serialize_rows(cursor.fetchall())


def fetch_form_options(cursor):
    cursor.execute("""
        SELECT id, source_uuid, source_name
        FROM lead_sources
        ORDER BY source_name ASC
    """)
    lead_sources = serialize_rows(cursor.fetchall())

    cursor.execute("""
        SELECT id, role_uuid, role_name
        FROM roles
        ORDER BY role_name ASC
    """)
    roles = serialize_rows(cursor.fetchall())

    return lead_sources, roles


def get_lead_source_limit_columns():
    return [
        {
            "headerName": "Role",
            "field": "role_name",
            "minWidth": 220,
            "flex": 1,
        },
        {
            "headerName": "Lead Source",
            "field": "source_name",
            "minWidth": 220,
            "flex": 1,
        },
        {
            "headerName": "Pending Lead Limit",
            "field": "pending_lead_limit",
            "minWidth": 150,
            "flex": 0.5,
        },
        {
            "headerName": "Daily Lead Limit",
            "field": "daily_lead_limit",
            "minWidth": 150,
            "flex": 0.5,
        },
        {
            "headerName": "Fetch Lead Limit",
            "field": "fetch_lead_limit",
            "minWidth": 150,
            "flex": 0.5,
        },
    ]


def get_lead_source_limit_grid_context(rows, lead_sources, roles):
    return {
        "grid_id": "leadSourceLimitsGrid",
        "data": rows,
        "columns": get_lead_source_limit_columns(),
        "filters": [
            {
                "name": "source_id",
                "label": "Lead Source",
                "options": [
                    {
                        "value": source["id"],
                        "label": source["source_name"],
                    }
                    for source in lead_sources
                ],
            },
            {
                "name": "role_id",
                "label": "Role",
                "options": [
                    {
                        "value": role["id"],
                        "label": role["role_name"],
                    }
                    for role in roles
                ],
            },
        ],
        "toolbar_buttons": [
            {
                "type": "link",
                "label": "Add Lead Source Limit",
                "icon": "mdi mdi-plus",
                "class": "btn btn-outline-primary",
                "url": url_for("add_lead_source_limit"),
            }
        ],
        "grid_wrapper_class": "settings-master-wrap",
        "grid_wrapper_attrs": {
            "data-master-type": "lead_source_limits",
        },
        "row_id_field": "lead_source_limits_uuid",
        "action_id_field": "lead_source_limits_uuid",
        "edit_url": "/settings/lead/source-limits/edit/",
        "delete_url": "/settings/lead/source-limits/delete/",
        "page_size": 10,
        "page_size_options": get_page_size_options(),
        "show_status_counts": False,
    }


def lead_source_limits(app):

    @app.route("/settings/lead/source-limits", endpoint="lead_source_limits")
    def setting_lead_source_limits():
        conn = get_db_connection()

        with conn.cursor() as cursor:
            rows = fetch_lead_source_limit_rows(cursor)
            lead_sources, roles = fetch_form_options(cursor)

        conn.close()

        return render_template(
            "settings/lead_source_limits.html",
            **get_lead_source_limit_grid_context(
                rows,
                lead_sources,
                roles,
            ),
            active_group="settings",
            active_page="lead_source_limits",
            page_title="Lead Source Limits",
            page_heading="Lead Source Limits",
        )

    @require_permission('settings', 'lead_management')
    @app.route(
        "/settings/lead/source-limits/add",
        methods=["GET", "POST"],
        endpoint="add_lead_source_limit",
    )
    def add_lead_source_limit():
        conn = get_db_connection()

        if request.method == "POST":
            source_id = request.form.get("source_id")
            role_id = request.form.get("role_id")

            if not source_id:
                conn.close()
                flash("Lead source is required.", "warning")
                return redirect(url_for("add_lead_source_limit"))

            if not role_id:
                conn.close()
                flash("Role is required.", "warning")
                return redirect(url_for("add_lead_source_limit"))

            try:
                source_id = parse_int(source_id, "Lead source", 1, 1000000)
                role_id = parse_int(role_id, "Role", 1, 1000000)

                pending_lead_limit = parse_int(
                    request.form.get("pending_lead_limit"),
                    "Pending lead limit",
                    1,
                    100000,
                )

                daily_lead_limit = parse_int(
                    request.form.get("daily_lead_limit"),
                    "Daily lead limit",
                    1,
                    100000,
                )

                fetch_lead_limit = parse_int(
                    request.form.get("fetch_lead_limit"),
                    "Fetch lead limit",
                    1,
                    1000,
                )
            except ValueError as error:
                conn.close()
                flash(str(error), "warning")
                return redirect(url_for("add_lead_source_limit"))

            with conn.cursor() as cursor:
                created_by = get_current_user_id(cursor)

                cursor.execute("""
                    SELECT lead_source_limits_uuid
                    FROM lead_source_limits
                    WHERE source_id = %s
                      AND role_id = %s
                    LIMIT 1
                """, (
                    source_id,
                    role_id,
                ))

                if cursor.fetchone():
                    conn.close()
                    flash(
                        "Same lead source and role already exists.",
                        "warning",
                    )
                    return redirect(url_for("add_lead_source_limit"))

                lead_source_limits_uuid = make_unique_code(
                    cursor,
                    "lead_source_limits",
                    "lead_source_limits_uuid",
                    "LSL",
                )

                cursor.execute("""
                    INSERT INTO lead_source_limits (
                        lead_source_limits_uuid,
                        source_id,
                        role_id,
                        pending_lead_limit,
                        daily_lead_limit,
                        fetch_lead_limit,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    lead_source_limits_uuid,
                    source_id,
                    role_id,
                    pending_lead_limit,
                    daily_lead_limit,
                    fetch_lead_limit,
                    created_by,
                ))

            conn.commit()
            conn.close()

            flash("Limit Set Successfully.", "success")
            return redirect(url_for("lead_source_limits"))

        with conn.cursor() as cursor:
            lead_sources, roles = fetch_form_options(cursor)

        conn.close()

        return render_template(
            "settings/lead_source_limit_form.html",
            lead_sources=lead_sources,
            roles=roles,
            record=None,
            form_mode="add",
            active_group="settings",
            active_page="lead_source_limits",
            page_title="Add Lead Source Limit",
            page_heading="Add Lead Source Limit",
        )

    @require_permission('settings', 'lead_management')
    @app.route(
        "/settings/lead/source-limits/edit/<lead_source_limits_uuid>",
        methods=["GET", "POST"],
        endpoint="edit_lead_source_limit",
    )
    def edit_lead_source_limit(lead_source_limits_uuid):
        conn = get_db_connection()

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    lead_source_limits_uuid,
                    source_id,
                    role_id,
                    pending_lead_limit,
                    daily_lead_limit,
                    fetch_lead_limit,
                    created_by
                FROM lead_source_limits
                WHERE lead_source_limits_uuid = %s
                LIMIT 1
            """, (lead_source_limits_uuid,))

            record = cursor.fetchone()

        if not record:
            conn.close()
            flash("Lead source limit not found.", "warning")
            return redirect(url_for("lead_source_limits"))

        if request.method == "POST":
            source_id = request.form.get("source_id")
            role_id = request.form.get("role_id")

            if not source_id:
                conn.close()
                flash("Lead source is required.", "warning")
                return redirect(
                    url_for(
                        "edit_lead_source_limit",
                        lead_source_limits_uuid=lead_source_limits_uuid,
                    )
                )

            if not role_id:
                conn.close()
                flash("Role is required.", "warning")
                return redirect(
                    url_for(
                        "edit_lead_source_limit",
                        lead_source_limits_uuid=lead_source_limits_uuid,
                    )
                )

            try:
                source_id = parse_int(source_id, "Lead source", 1, 1000000)
                role_id = parse_int(role_id, "Role", 1, 1000000)

                pending_lead_limit = parse_int(
                    request.form.get("pending_lead_limit"),
                    "Pending lead limit",
                    1,
                    100000,
                )
                daily_lead_limit = parse_int(
                    request.form.get("daily_lead_limit"),
                    "Daily lead limit",
                    1,
                    100000,
                )
                fetch_lead_limit = parse_int(
                    request.form.get("fetch_lead_limit"),
                    "Fetch lead limit",
                    1,
                    1000,
                )
            except ValueError as error:
                conn.close()
                flash(str(error), "warning")
                return redirect(
                    url_for(
                        "edit_lead_source_limit",
                        lead_source_limits_uuid=lead_source_limits_uuid,
                    )
                )

            with conn.cursor() as cursor:
                created_by = get_current_user_id(cursor)

                cursor.execute("""
                    SELECT lead_source_limits_uuid
                    FROM lead_source_limits
                    WHERE source_id = %s
                      AND role_id = %s
                      AND lead_source_limits_uuid != %s
                    LIMIT 1
                """, (
                    source_id,
                    role_id,
                    lead_source_limits_uuid,
                ))

                if cursor.fetchone():
                    conn.close()
                    flash(
                        "Same lead source and role already exists.",
                        "warning",
                    )
                    return redirect(
                        url_for(
                            "edit_lead_source_limit",
                            lead_source_limits_uuid=lead_source_limits_uuid,
                        )
                    )

                cursor.execute("""
                    UPDATE lead_source_limits
                    SET
                        source_id = %s,
                        role_id = %s,
                        pending_lead_limit = %s,
                        daily_lead_limit = %s,
                        fetch_lead_limit = %s,
                        created_by = %s
                    WHERE lead_source_limits_uuid = %s
                """, (
                    source_id,
                    role_id,
                    pending_lead_limit,
                    daily_lead_limit,
                    fetch_lead_limit,
                    created_by,
                    lead_source_limits_uuid,
                ))

            conn.commit()
            conn.close()

            flash("Limit Updated Successfully.", "success")
            return redirect(url_for("lead_source_limits"))

        with conn.cursor() as cursor:
            lead_sources, roles = fetch_form_options(cursor)

        conn.close()

        return render_template(
            "settings/lead_source_limit_form.html",
            lead_sources=lead_sources,
            roles=roles,
            record=record,
            form_mode="edit",
            active_group="settings",
            active_page="lead_source_limits",
            page_title="Edit Lead Source Limit",
            page_heading="Edit Lead Source Limit",
        )

    @require_permission('settings', 'lead_management')
    @app.route(
        "/settings/lead/source-limits/delete/<lead_source_limits_uuid>",
        methods=["POST", "GET"],
        endpoint="delete_lead_source_limit",
    )
    def delete_lead_source_limit(lead_source_limits_uuid):
        conn = get_db_connection()

        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE FROM lead_source_limits
                WHERE lead_source_limits_uuid = %s
            """, (lead_source_limits_uuid,))

            deleted_count = cursor.rowcount

        conn.commit()
        conn.close()

        if deleted_count:
            flash(
                "Lead source limit deleted successfully.",
                "success",
            )
        else:
            flash(
                "Lead source limit not found.",
                "warning",
            )

        return redirect(url_for("lead_source_limits"))