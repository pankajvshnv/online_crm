from utils.permissions import require_permission
from flask import jsonify, render_template, request, redirect, url_for, flash, session
from config import get_db_connection
from datetime import date, datetime
from decimal import Decimal
import secrets
import re


def to_db_date(val):
    if not val:
        return None
    s = str(val).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", s)
    if match:
        dd, mm, yyyy = match.groups()
        return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
    return None


def serialize_grid_value(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, Decimal):
        return float(value)

    return value


def serialize_grid_rows(rows):
    return [
        {key: serialize_grid_value(value) for key, value in row.items()}
        for row in rows
    ]


def format_display_date(val):
    if not val:
        return ""
    if isinstance(val, (date, datetime)):
        return val.strftime("%d/%m/%Y")
    s = str(val).strip()
    if not s or s.lower() in ("none", "n/a", "null"):
        return ""
    if " " in s:
        s = s.split(" ")[0]

    match_iso = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
    if match_iso:
        yyyy, mm, dd = match_iso.groups()
        return f"{int(dd):02d}/{int(mm):02d}/{yyyy}"

    match_dmy = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if match_dmy:
        dd, mm, yyyy = match_dmy.groups()
        return f"{int(dd):02d}/{int(mm):02d}/{yyyy}"

    return s


def fetch_user_by_key(cursor, user_key):
    cursor.execute("""
        SELECT
            u.*,
            e.extension_uuid,
            r.role_uuid,
            d.designation_uuid,
            manager.user_uuid AS reporting_to_uuid,
            COALESCE(manager.full_name, 'None') AS reporting_manager_name
        FROM users u
        LEFT JOIN extensions e
            ON e.id = u.extension_id
        LEFT JOIN roles r
            ON r.id = u.role_id
        LEFT JOIN designations d
            ON d.id = u.designation_id
        LEFT JOIN users manager
            ON manager.id = u.reporting_to_user_id
        WHERE u.user_uuid = %s
        LIMIT 1
    """, (user_key,))

    row = cursor.fetchone()
    if row:
        row["date_of_birth_display"] = format_display_date(row.get("date_of_birth"))
        row["date_of_joining_display"] = format_display_date(row.get("date_of_joining"))
    return row


def resolve_uuid_to_id(cursor, table_name, uuid_column, uuid_value):
    if not uuid_value:
        return None

    cursor.execute(
        f"""
            SELECT id
            FROM {table_name}
            WHERE {uuid_column} = %s
            LIMIT 1
        """,
        (uuid_value,),
    )

    row = cursor.fetchone()

    return row["id"] if row else None


def fetch_admin_user_id(cursor):
    cursor.execute("""
        SELECT u.id
        FROM users u
        LEFT JOIN roles r
            ON r.id = u.role_id
        WHERE u.status = 1
          AND (
              LOWER(COALESCE(r.role_name, '')) = 'admin'
              OR LOWER(COALESCE(u.username, '')) = 'admin'
              OR LOWER(COALESCE(u.full_name, '')) LIKE '%admin%'
          )
        ORDER BY
            CASE
                WHEN LOWER(COALESCE(r.role_name, '')) = 'admin' THEN 0
                WHEN LOWER(COALESCE(u.username, '')) = 'admin' THEN 1
                ELSE 2
            END,
            u.id ASC
        LIMIT 1
    """)

    admin = cursor.fetchone()

    return admin["id"] if admin else None


def resolve_reporting_to_id(
    cursor,
    reporting_user_uuid,
    current_internal_user_id=None,
):
    reporting_to_user_id = resolve_uuid_to_id(
        cursor,
        "users",
        "user_uuid",
        reporting_user_uuid,
    )

    admin_user_id = fetch_admin_user_id(cursor)

    if not reporting_to_user_id:
        reporting_to_user_id = admin_user_id

    if (
        current_internal_user_id
        and reporting_to_user_id == current_internal_user_id
    ):
        if admin_user_id == current_internal_user_id:
            return None

        return admin_user_id

    return reporting_to_user_id


def resolve_user_form_values(
    cursor,
    form,
    current_internal_user_id=None,
):
    return {
        "extension_id": resolve_uuid_to_id(
            cursor,
            "extensions",
            "extension_uuid",
            form.get("extension_uuid"),
        ),
        "role_id": resolve_uuid_to_id(
            cursor,
            "roles",
            "role_uuid",
            form.get("role_uuid"),
        ),
        "designation_id": resolve_uuid_to_id(
            cursor,
            "designations",
            "designation_uuid",
            form.get("designation_uuid"),
        ),
        "reporting_to_user_id": resolve_reporting_to_id(
            cursor,
            form.get("reporting_to_uuid"),
            current_internal_user_id=current_internal_user_id,
        ),
    }


def make_unique_code(cursor, table_name, column_name, prefix):
    while True:
        code = f"{prefix}{secrets.token_hex(4).upper()}"

        cursor.execute(
            f"""
                SELECT 1
                FROM {table_name}
                WHERE {column_name} = %s
                LIMIT 1
            """,
            (code,),
        )

        if not cursor.fetchone():
            return code


def fetch_user_form_options(cursor, exclude_internal_user_id=None):
    admin_user_id = fetch_admin_user_id(cursor)

    cursor.execute("""
        SELECT
            e.extension_uuid,
            e.extension_number,
            ca.api_name,
            assigned.id AS assigned_user_id,
            assigned.user_uuid AS assigned_user_uuid,
            assigned.full_name AS assigned_user_name
        FROM extensions e
        LEFT JOIN calling_apis ca
            ON ca.id = e.calling_api_id
        LEFT JOIN users assigned
            ON assigned.extension_id = e.id
        WHERE e.status = 1
        ORDER BY e.extension_number ASC
    """)

    extensions = cursor.fetchall()

    for extension in extensions:
        extension["is_assigned_to_other"] = bool(
            extension.get("assigned_user_id")
            and str(extension.get("assigned_user_id"))
            != str(exclude_internal_user_id or "")
        )

    cursor.execute("""
        SELECT
            role_uuid,
            role_name
        FROM roles
        WHERE status = 1
        ORDER BY role_name ASC
    """)

    roles = cursor.fetchall()

    cursor.execute("""
        SELECT
            designation_uuid,
            designation_name
        FROM designations
        WHERE status = 1
        ORDER BY designation_name ASC
    """)

    designations = cursor.fetchall()

    if exclude_internal_user_id:
        cursor.execute("""
            SELECT
                user_uuid,
                full_name,
                id
            FROM users
            WHERE status = 1
              AND id <> %s
            ORDER BY full_name ASC
        """, (exclude_internal_user_id,))
    else:
        cursor.execute("""
            SELECT
                user_uuid,
                full_name,
                id
            FROM users
            WHERE status = 1
            ORDER BY full_name ASC
        """)

    reporting_users = cursor.fetchall()

    for reporting_user in reporting_users:
        reporting_user["is_default_admin"] = bool(
            admin_user_id
            and reporting_user.get("id") == admin_user_id
        )

    return {
        "extensions": extensions,
        "roles": roles,
        "designations": designations,
        "reporting_users": reporting_users,
    }


def build_reporting_hierarchy(cursor):
    cursor.execute("""
        SELECT
            u.id,
            u.user_uuid,
            u.full_name,
            u.username,
            u.mobile,
            u.reporting_to_user_id,
            u.status,
            COALESCE(u.target, 0) AS target,
            COALESCE(
                CAST(e.extension_number AS CHAR),
                ''
            ) AS extension_name,
            COALESCE(
                r.role_name,
                ''
            ) AS role_name,
            COALESCE(
                d.designation_name,
                ''
            ) AS designation_name
        FROM users u
        LEFT JOIN extensions e
            ON e.id = u.extension_id
        LEFT JOIN roles r
            ON r.id = u.role_id
        LEFT JOIN designations d
            ON d.id = u.designation_id
        ORDER BY
            CASE
                WHEN LOWER(COALESCE(r.role_name, '')) = 'admin' THEN 0
                WHEN LOWER(COALESCE(u.username, '')) = 'admin' THEN 1
                ELSE 2
            END,
            u.full_name ASC
    """)

    rows = cursor.fetchall()
    admin_user_id = fetch_admin_user_id(cursor)
    nodes = {}

    for row in rows:
        self_tgt = float(row.get("target") or 0)
        nodes[row["id"]] = {
            "internal_id": row["id"],
            "user_uuid": row["user_uuid"],
            "full_name": row["full_name"],
            "username": row["username"],
            "mobile": row["mobile"],
            "reporting_to_user_id": row["reporting_to_user_id"],
            "extension_name": row["extension_name"],
            "role_name": row["role_name"],
            "designation_name": row["designation_name"],
            "status": row["status"],
            "target": self_tgt,
            "self_target": self_tgt,
            "team_target": 0.0,
            "total_target": self_tgt,
            "children": [],
            "team_count": 0,
            "level": 0,
        }

    # Ensure admin has no parent (breaks root cycle if admin reports to someone)
    if admin_user_id and admin_user_id in nodes:
        nodes[admin_user_id]["reporting_to_user_id"] = None

    # Detect and break any other circular dependencies cleanly
    for node_id, node in nodes.items():
        seen = {node_id}
        curr = node.get("reporting_to_user_id")
        while curr:
            if curr in seen:
                # Cycle detected: break this specific parent link
                node["reporting_to_user_id"] = None
                break
            seen.add(curr)
            curr = nodes[curr].get("reporting_to_user_id") if curr in nodes else None

    # Build Tree
    roots = []
    for node_id, node in nodes.items():
        parent_id = node.get("reporting_to_user_id")
        if parent_id and parent_id in nodes and parent_id != node_id:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)

    # Sort roots so Admin is first
    roots = sorted(
        roots,
        key=lambda item: (
            0 if admin_user_id and item["internal_id"] == admin_user_id else 1,
            item["full_name"] or "",
        ),
    )

    max_depth = 0

    def format_target_currency(val):
        try:
            val = float(val or 0)
        except Exception:
            val = 0.0

        if val == 0:
            return "₹0"
        if val >= 10000000:
            cr = val / 10000000
            return f"₹{cr:.2f}".rstrip("0").rstrip(".") + " Cr"
        if val >= 100000:
            l = val / 100000
            return f"₹{l:.2f}".rstrip("0").rstrip(".") + " L"
        if val >= 1000:
            k = val / 1000
            return f"₹{k:.2f}".rstrip("0").rstrip(".") + " k"
        return f"₹{int(val):,}"

    def annotate(node, level=0):
        nonlocal max_depth
        node["level"] = level
        max_depth = max(max_depth, level + 1)

        node["children"].sort(
            key=lambda item: (
                -(len(item.get("children", []))),
                item["full_name"] or ""
            )
        )

        team_count = 0
        team_target = 0.0

        for child in node["children"]:
            child_team_count, child_total_target = annotate(child, level + 1)
            team_count += 1 + child_team_count
            team_target += child_total_target

        node["team_count"] = team_count
        node["team_target"] = team_target
        node["total_target"] = node["self_target"] + team_target

        node["self_target_display"] = format_target_currency(node["self_target"])
        node["team_target_display"] = format_target_currency(node["team_target"])
        node["total_target_display"] = format_target_currency(node["total_target"])

        return team_count, node["total_target"]

    for root in roots:
        annotate(root)

    return {
        "roots": roots,
        "total_users": len(rows),
        "root_count": len(roots),
        "max_depth": max_depth,
    }


def user_management(app):

    @require_permission('settings', 'user_management')
    @app.route("/team")
    @app.route("/users")
    @app.route("/settings/user/list")
    def all_users():
        conn = get_db_connection()

        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    u.id,
                    u.user_uuid,
                    u.user_uuid AS action_key,
                    u.full_name,
                    u.username,
                    u.password,
                    u.mobile,
                    e.extension_uuid,
                    r.role_uuid,
                    d.designation_uuid,
                    u.date_of_birth,
                    u.date_of_joining,
                    u.biometric_id,
                    manager.user_uuid AS reporting_to_uuid,
                    u.target,
                    u.click_to_call,
                    u.number_show_hide,
                    u.status,
                    COALESCE(
                        CAST(e.extension_number AS CHAR),
                        'Not Assigned'
                    ) AS extension_name,
                    COALESCE(
                        r.role_name,
                        'Not Assigned'
                    ) AS role_name,
                    COALESCE(
                        d.designation_name,
                        'Not Assigned'
                    ) AS designation_name,
                    COALESCE(
                        manager.full_name,
                        'Not Assigned'
                    ) AS reporting_to_name
                FROM users u
                LEFT JOIN extensions e
                    ON e.id = u.extension_id
                LEFT JOIN roles r
                    ON r.id = u.role_id
                LEFT JOIN designations d
                    ON d.id = u.designation_id
                LEFT JOIN users manager
                    ON manager.id = u.reporting_to_user_id
                ORDER BY u.id DESC
            """)

            users = cursor.fetchall()
            for u in users:
                u["date_of_birth_display"] = format_display_date(u.get("date_of_birth"))
                u["date_of_joining_display"] = format_display_date(u.get("date_of_joining"))

            cursor.execute("""
                SELECT designation_uuid AS value, designation_name AS label
                FROM designations
                WHERE status = 1
                ORDER BY designation_name ASC
            """)
            designations = cursor.fetchall()

            cursor.execute("""
                SELECT role_uuid AS value, role_name AS label
                FROM roles
                ORDER BY role_name ASC
            """)
            roles = cursor.fetchall()

        conn.close()

        saved_filters = session.get("users_filters", {
            "role": "all",
            "designation": "all",
            "status": "all",
            "search": "",
            "page_size": 10,
            "page": 1,
        })

        return render_template(
            "users/all_users.html",
            users=users,
            roles=roles,
            designations=designations,
            saved_filters=saved_filters,
            active_group="settings",
            active_page="all_users",
            page_title="All Users",
        )

    @app.route("/api/users/save-filters", methods=["POST"])
    def api_save_users_filters():
        data = request.get_json(silent=True) or {}
        session["users_filters"] = {
            "role": str(data.get("role") or "all").strip().lower(),
            "designation": str(data.get("designation") or "all").strip().lower(),
            "status": str(data.get("status") or "all").strip(),
            "search": str(data.get("search") or "").strip(),
            "page_size": int(data.get("page_size") or 10),
            "page": int(data.get("page") or 1),
        }
        session.modified = True
        return jsonify({"success": True, "saved_filters": session["users_filters"]})

    @require_permission('settings', 'user_management')
    @app.route("/settings/user/groups")
    def user_groups():
        conn = get_db_connection()

        with conn.cursor() as cursor:
            hierarchy = build_reporting_hierarchy(cursor)

        conn.close()

        return render_template(
            "users/user_groups.html",
            hierarchy_roots=hierarchy["roots"],
            total_users=hierarchy["total_users"],
            root_count=hierarchy["root_count"],
            max_depth=hierarchy["max_depth"],
            active_group="settings",
            active_page="user_groups",
            page_title="Reporting Chart",
        )

    @app.route("/api/users/check-username", methods=["GET", "POST"])
    def api_check_username():
        data = request.get_json(silent=True) or {}
        username = (
            data.get("username")
            or request.form.get("username")
            or request.args.get("username")
            or ""
        ).strip()

        current_uuid = (
            data.get("current_uuid")
            or data.get("current_uui")
            or request.form.get("current_uuid")
            or request.form.get("current_uui")
            or request.args.get("current_uuid")
            or request.args.get("current_uui")
            or ""
        ).strip()

        if not username:
            return jsonify({"available": False, "message": "Username is required."})

        conn = get_db_connection()
        with conn.cursor() as cursor:
            if current_uuid:
                cursor.execute("""
                    SELECT id FROM users
                    WHERE LOWER(username) = LOWER(%s) AND user_uuid <> %s
                    LIMIT 1
                """, (username, current_uuid))
            else:
                cursor.execute("""
                    SELECT id FROM users
                    WHERE LOWER(username) = LOWER(%s)
                    LIMIT 1
                """, (username,))
            existing = cursor.fetchone()
        conn.close()

        if existing:
            return jsonify({"available": False, "message": "Username is already taken."})
        return jsonify({"available": True, "message": "Username is available."})

    @require_permission('settings', 'user_management')
    @app.route(
        "/settings/user/add",
        methods=["GET", "POST"],
    )
    def add_user():
        conn = get_db_connection()

        if request.method == "POST":
            username = (request.form.get("username") or "").strip()

            with conn.cursor() as cursor:
                # Check for duplicate username
                cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s) LIMIT 1", (username,))
                if cursor.fetchone():
                    form_options = fetch_user_form_options(cursor)
                    conn.close()
                    flash(f"Username '{username}' is already taken. Please choose a different username.", "danger")
                    return render_template(
                        "users/add_user.html",
                        user=request.form,
                        form_options=form_options,
                        form_action=url_for("add_user"),
                        button_text="Create User",
                        active_group="settings",
                        active_page="add_user",
                        page_title="Add User",
                    )

                user_uuid = make_unique_code(
                    cursor,
                    "users",
                    "user_uuid",
                    "USR",
                )

                resolved_values = resolve_user_form_values(
                    cursor,
                    request.form,
                )

                cursor.execute("""
                    INSERT INTO users (
                        user_uuid,
                        full_name,
                        username,
                        mobile,
                        password,
                        extension_id,
                        role_id,
                        designation_id,
                        date_of_birth,
                        date_of_joining,
                        biometric_id,
                        reporting_to_user_id,
                        target,
                        click_to_call,
                        number_show_hide,
                        status,
                        require_otp_for_login,
                        outside_login
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                """, (
                    user_uuid,
                    request.form.get("full_name"),
                    username,
                    request.form.get("mobile") or None,
                    request.form.get("password"),
                    resolved_values["extension_id"],
                    resolved_values["role_id"],
                    resolved_values["designation_id"],
                    to_db_date(request.form.get("date_of_birth")),
                    to_db_date(request.form.get("date_of_joining")),
                    request.form.get("biometric_id") or None,
                    resolved_values["reporting_to_user_id"],
                    request.form.get("target") or 0,
                    request.form.get("click_to_call") or 1,
                    request.form.get("number_show_hide") or 1,
                    request.form.get("status") or 1,
                    request.form.get("require_otp_for_login") or 0,
                    request.form.get("outside_login") or 0,
                ))

            conn.commit()
            conn.close()

            flash(
                "User created successfully.",
                "success",
            )

            return redirect(
                url_for("all_users")
            )

        with conn.cursor() as cursor:
            form_options = fetch_user_form_options(cursor)

        conn.close()

        return render_template(
            "users/add_user.html",
            user=None,
            form_options=form_options,
            form_action=url_for("add_user"),
            button_text="Create User",
            active_group="settings",
            active_page="add_user",
            page_title="Add User",
        )

    @require_permission('settings', 'user_management')
    @app.route(
        "/settings/user/edit/<user_key>",
        methods=["GET", "POST"],
    )
    def edit_user(user_key):
        conn = get_db_connection()

        with conn.cursor() as cursor:
            existing_user = fetch_user_by_key(
                cursor,
                user_key,
            )

        if not existing_user:
            conn.close()

            flash(
                "User not found.",
                "danger",
            )

            return redirect(
                url_for("all_users")
            )

        internal_user_id = existing_user["id"]

        if request.method == "POST":
            username = (request.form.get("username") or "").strip()

            with conn.cursor() as cursor:
                # Check for duplicate username
                cursor.execute("""
                    SELECT id FROM users
                    WHERE LOWER(username) = LOWER(%s) AND id <> %s
                    LIMIT 1
                """, (username, internal_user_id))
                if cursor.fetchone():
                    form_options = fetch_user_form_options(
                        cursor,
                        exclude_internal_user_id=internal_user_id,
                    )
                    conn.close()
                    flash(f"Username '{username}' is already in use by another user.", "danger")
                    return render_template(
                        "users/add_user.html",
                        user=request.form,
                        form_options=form_options,
                        form_action=url_for(
                            "edit_user",
                            user_key=existing_user["user_uuid"],
                        ),
                        button_text="Update User",
                        active_group="settings",
                        active_page="all_users",
                        page_title="Edit User",
                    )

                resolved_values = resolve_user_form_values(
                    cursor,
                    request.form,
                    current_internal_user_id=internal_user_id,
                )

                fields = [
                    "full_name = %s",
                    "username = %s",
                    "mobile = %s",
                    "extension_id = %s",
                    "role_id = %s",
                    "designation_id = %s",
                    "date_of_birth = %s",
                    "date_of_joining = %s",
                    "biometric_id = %s",
                    "reporting_to_user_id = %s",
                    "target = %s",
                    "click_to_call = %s",
                    "number_show_hide = %s",
                    "status = %s",
                    "require_otp_for_login = %s",
                    "outside_login = %s",
                ]

                values = [
                    request.form.get("full_name"),
                    username,
                    request.form.get("mobile") or None,
                    resolved_values["extension_id"],
                    resolved_values["role_id"],
                    resolved_values["designation_id"],
                    to_db_date(request.form.get("date_of_birth")),
                    to_db_date(request.form.get("date_of_joining")),
                    request.form.get("biometric_id") or None,
                    resolved_values["reporting_to_user_id"],
                    request.form.get("target") or 0,
                    request.form.get("click_to_call") or 1,
                    request.form.get("number_show_hide") or 1,
                    request.form.get("status") or 1,
                    request.form.get("require_otp_for_login") or 0,
                    request.form.get("outside_login") or 0,
                ]

                password = request.form.get("password")

                if password:
                    fields.append("password = %s")
                    values.append(password)

                values.append(internal_user_id)

                cursor.execute(
                    f"""
                        UPDATE users
                        SET {", ".join(fields)}
                        WHERE id = %s
                    """,
                    values,
                )

            conn.commit()
            conn.close()

            flash(
                "User updated successfully.",
                "success",
            )

            return redirect(
                url_for("all_users")
            )

        with conn.cursor() as cursor:
            user = existing_user

            form_options = fetch_user_form_options(
                cursor,
                exclude_internal_user_id=internal_user_id,
            )

        conn.close()

        return render_template(
            "users/add_user.html",
            user=user,
            form_options=form_options,
            form_action=url_for(
                "edit_user",
                user_key=user["user_uuid"],
            ),
            button_text="Update User",
            active_group="settings",
            active_page="all_users",
            page_title="Edit User",
        )

    @require_permission('settings', 'user_management')
    @app.route("/settings/user/delete/<user_key>", methods=["GET", "POST"])
    def delete_user(user_key):
        conn = get_db_connection()

        with conn.cursor() as cursor:
            user = fetch_user_by_key(
                cursor,
                user_key,
            )

            if not user:
                conn.close()
                flash("User not found.", "danger")
                return redirect(url_for("all_users"))

            # Unlink reporting manager hierarchy
            cursor.execute("UPDATE users SET reporting_to_user_id = NULL WHERE reporting_to_user_id = %s", (user["id"],))
            cursor.execute("UPDATE users SET extension_id = NULL WHERE id = %s", (user["id"],))

            # Check if user has any active leads
            cursor.execute("""
                SELECT COUNT(*) AS active_cnt 
                FROM leads 
                WHERE current_owner_user_id = %s 
                  AND (is_disposed = 0 OR is_disposed IS NULL)
            """, (user["id"],))
            active_cnt = (cursor.fetchone() or {}).get("active_cnt") or 0

            # If user has active leads or linked records, soft-deactivate to preserve active leads without disposal
            if active_cnt > 0:
                cursor.execute("UPDATE users SET status = 0, reporting_to_user_id = NULL, extension_id = NULL WHERE id = %s", (user["id"],))
                conn.commit()
                flash(f"User '{user['full_name']}' has been deactivated. {active_cnt} active lead(s) preserved safely without disposal (manage in User Report).", "warning")
            else:
                try:
                    cursor.execute("DELETE FROM users WHERE user_uuid = %s", (user["user_uuid"],))
                    conn.commit()
                    flash("User deleted successfully.", "success")
                except Exception as err:
                    conn.rollback()
                    # If foreign key prevents deletion, soft deactivate to preserve historical integrity
                    cursor.execute("UPDATE users SET status = 0, reporting_to_user_id = NULL, extension_id = NULL WHERE id = %s", (user["id"],))
                    conn.commit()
                    flash(f"User '{user['full_name']}' has linked activity/records and has been deactivated successfully. Leads are not disposed.", "warning")

        conn.close()
        return redirect(url_for("all_users"))

    @require_permission('settings', 'user_management')
    @app.route(
        "/settings/user/delete-selected",
        methods=["POST"],
    )
    def delete_selected_users():
        payload = request.get_json(silent=True) or {}
        user_uuids = payload.get("ids") or []

        if not user_uuids and request.form.get("selected_ids"):
            import json
            try:
                user_uuids = json.loads(request.form.get("selected_ids"))
            except Exception:
                user_uuids = [request.form.get("selected_ids")]

        safe_user_uuids = []
        for user_uuid in user_uuids:
            user_uuid = str(user_uuid or "").strip()
            if user_uuid:
                safe_user_uuids.append(user_uuid)

        safe_user_uuids = sorted(set(safe_user_uuids))

        if not safe_user_uuids:
            if request.is_json:
                return jsonify({"success": False, "message": "No users selected."}), 400
            flash("No users selected.", "warning")
            return redirect(url_for("all_users"))

        conn = get_db_connection()
        msg = ""
        with conn.cursor() as cursor:
            placeholders = ", ".join(["%s"] * len(safe_user_uuids))
            cursor.execute(f"SELECT id FROM users WHERE user_uuid IN ({placeholders})", safe_user_uuids)
            user_ids = [r["id"] for r in cursor.fetchall()]

            if user_ids:
                id_placeholders = ", ".join(["%s"] * len(user_ids))
                cursor.execute(f"UPDATE users SET reporting_to_user_id = NULL WHERE reporting_to_user_id IN ({id_placeholders})", user_ids)
                cursor.execute(f"UPDATE users SET extension_id = NULL WHERE id IN ({id_placeholders})", user_ids)

                # Check if any selected users have active leads
                cursor.execute(f"""
                    SELECT COUNT(*) AS active_cnt
                    FROM leads
                    WHERE current_owner_user_id IN ({id_placeholders})
                      AND (is_disposed = 0 OR is_disposed IS NULL)
                """, user_ids)
                total_active_leads = (cursor.fetchone() or {}).get("active_cnt") or 0

                if total_active_leads > 0:
                    cursor.execute(f"UPDATE users SET status = 0, extension_id = NULL, reporting_to_user_id = NULL WHERE id IN ({id_placeholders})", user_ids)
                    conn.commit()
                    msg = f"{len(user_ids)} user(s) deactivated successfully. {total_active_leads} active lead(s) preserved without disposal."
                else:
                    try:
                        cursor.execute(f"DELETE FROM users WHERE id IN ({id_placeholders})", user_ids)
                        count = cursor.rowcount
                        conn.commit()
                        msg = f"{count} user(s) deleted successfully."
                    except Exception:
                        conn.rollback()
                        cursor.execute(f"UPDATE users SET status = 0, extension_id = NULL, reporting_to_user_id = NULL WHERE id IN ({id_placeholders})", user_ids)
                        conn.commit()
                        msg = f"{len(user_ids)} user(s) deactivated successfully (records preserved for history, leads not disposed)."

        conn.close()

        if request.is_json:
            return jsonify({"success": True, "message": msg})

        flash(msg, "success")
        return redirect(url_for("all_users"))

    @app.route("/profile", methods=["GET"])
    @app.route("/my-profile", methods=["GET"])
    @app.route("/settings/user/profile", methods=["GET"], endpoint="user_profile")
    def user_profile_page():
        user_uuid = session.get("user_uuid")
        if not user_uuid:
            flash("Please log in to view your profile.", "warning")
            return redirect(url_for("login"))

        conn = get_db_connection()
        user_data = None
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        u.user_uuid,
                        u.full_name,
                        u.username,
                        u.mobile,
                        u.date_of_birth,
                        u.date_of_joining,
                        u.biometric_id,
                        u.target,
                        u.click_to_call,
                        u.number_show_hide,
                        u.status,
                        u.require_otp_for_login,
                        u.outside_login,
                        e.extension_number,
                        d.designation_name,
                        r.role_name,
                        manager.full_name AS reporting_manager_name
                    FROM users u
                    LEFT JOIN extensions e ON e.id = u.extension_id
                    LEFT JOIN designations d ON d.id = u.designation_id
                    LEFT JOIN roles r ON r.id = u.role_id
                    LEFT JOIN users manager ON manager.id = u.reporting_to_user_id
                    WHERE u.user_uuid = %s
                    LIMIT 1
                """, (user_uuid,))
                user_data = cursor.fetchone()
        finally:
            conn.close()

        if not user_data:
            flash("User profile not found.", "danger")
            return redirect(url_for("dashboard"))

        return render_template("users/user_profile.html", user=user_data, page_title="My Profile", active_group="profile", active_page="profile")

    @app.route("/profile/my-team", methods=["GET"], endpoint="my_team_page")
    @app.route("/settings/user/my-team", methods=["GET"])
    def my_team_page():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            flash("Please log in to view your team.", "warning")
            return redirect(url_for("login"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.id, u.user_uuid, u.full_name, u.is_admin, e.extension_number
                    FROM users u
                    LEFT JOIN extensions e ON e.id = u.extension_id
                    WHERE u.user_uuid = %s AND u.status = 1
                    LIMIT 1
                """, (logged_user_uuid,))
                logged_user = cursor.fetchone()
                if not logged_user:
                    flash("User account not found.", "danger")
                    return redirect(url_for("dashboard"))

                team_members = fetch_user_team_members(cursor, logged_user_uuid)
                
                total_members = len(team_members)
                active_members = sum(1 for m in team_members if int(m.get("status") or 0) == 1)
                extensions_assigned = sum(1 for m in team_members if m.get("extension_number"))
        finally:
            conn.close()

        return render_template(
            "users/my_team.html",
            team_members=team_members,
            logged_user=logged_user,
            total_members=total_members,
            active_members=active_members,
            extensions_assigned=extensions_assigned,
            page_title="My Team",
            active_group="profile",
            active_page="my_team",
        )

    @app.route("/profile/change-password", methods=["GET", "POST"], endpoint="change_password_page")
    @app.route("/settings/user/change-password", methods=["GET", "POST"])
    def change_password_page():
        user_uuid = session.get("user_uuid")
        if not user_uuid:
            flash("Please log in to change your password.", "warning")
            return redirect(url_for("login"))

        if request.method == "POST":
            new_password = (request.form.get("new_password") or "").strip()
            confirm_password = (request.form.get("confirm_password") or "").strip()

            if not new_password or not confirm_password:
                flash("Please enter both new password and confirm password.", "danger")
                return render_template("users/change_password.html", page_title="Change Password", active_group="profile", active_page="change_password")

            if new_password != confirm_password:
                flash("New Password and Confirm Password do not match.", "danger")
                return render_template("users/change_password.html", page_title="Change Password", active_group="profile", active_page="change_password")

            if len(new_password) < 4:
                flash("Password must be at least 4 characters long.", "warning")
                return render_template("users/change_password.html", page_title="Change Password", active_group="profile", active_page="change_password")

            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE user_uuid = %s LIMIT 1", (user_uuid,))
                    user = cursor.fetchone()
                    if not user:
                        flash("User account not found.", "danger")
                        return redirect(url_for("login"))

                    cursor.execute("UPDATE users SET password = %s, updated_at = NOW() WHERE id = %s", (new_password, user["id"]))
                    conn.commit()

                    flash("Password updated successfully! Please use your new password next time you log in.", "success")
                    return redirect(url_for("user_profile"))
            finally:
                conn.close()

        return render_template("users/change_password.html", page_title="Change Password", active_group="profile", active_page="change_password")

    @app.route("/api/telephony/supervise-call", methods=["POST"], endpoint="api_supervise_call")
    def api_supervise_call():
        supervisor_uuid = session.get("user_uuid")
        if not supervisor_uuid:
            return jsonify({"success": False, "message": "Login is required."}), 401

        payload = request.get_json(silent=True) or request.form.to_dict() or {}
        agent_user_uuid = payload.get("agent_user_uuid")
        agent_extension = payload.get("agent_extension")
        mode = payload.get("mode") or "listen"

        from routes.click_to_call import trigger_call_supervision
        try:
            result = trigger_call_supervision(
                supervisor_uuid=supervisor_uuid,
                agent_user_uuid=agent_user_uuid,
                agent_extension=agent_extension,
                mode=mode,
            )
            return jsonify(result)
        except ValueError as ve:
            return jsonify({"success": False, "message": str(ve)}), 400
        except Exception as e:
            return jsonify({"success": False, "message": f"Supervision failed: {str(e)}"}), 500


def fetch_user_team_members(cursor, logged_user_uuid):
    """
    Fetches all members who report directly or indirectly under the logged-in user.
    If the user has global/admin access, fetches all active users.
    Returns team members list with Name, Username, Password, Extension Number, Role, Designation, etc.
    """
    cursor.execute("""
        SELECT id, user_uuid, full_name, is_admin, role_id
        FROM users
        WHERE user_uuid = %s AND status = 1
        LIMIT 1
    """, (logged_user_uuid,))
    current_user = cursor.fetchone()
    if not current_user:
        return []

    from utils.permissions import has_permission
    is_global = has_permission("global_access_scope", "global_data_access") or int(current_user.get("is_admin") or 0) == 1

    if is_global:
        cursor.execute("""
            SELECT 
                u.id,
                u.user_uuid,
                u.full_name,
                u.username,
                u.password,
                u.mobile,
                u.status,
                u.click_to_call,
                e.extension_number,
                e.calling_api_id,
                d.designation_name,
                r.role_name,
                manager.full_name AS reporting_manager_name
            FROM users u
            LEFT JOIN extensions e ON e.id = u.extension_id
            LEFT JOIN designations d ON d.id = u.designation_id
            LEFT JOIN roles r ON r.id = u.role_id
            LEFT JOIN users manager ON manager.id = u.reporting_to_user_id
            WHERE u.status = 1
            ORDER BY u.id DESC
        """)
        return cursor.fetchall() or []

    cursor.execute("""
        SELECT 
            u.id,
            u.user_uuid,
            u.full_name,
            u.username,
            u.password,
            u.mobile,
            u.status,
            u.click_to_call,
            u.reporting_to_user_id,
            e.extension_number,
            e.calling_api_id,
            d.designation_name,
            r.role_name,
            manager.full_name AS reporting_manager_name
        FROM users u
        LEFT JOIN extensions e ON e.id = u.extension_id
        LEFT JOIN designations d ON d.id = u.designation_id
        LEFT JOIN roles r ON r.id = u.role_id
        LEFT JOIN users manager ON manager.id = u.reporting_to_user_id
        WHERE u.status = 1
    """)
    all_active_users = cursor.fetchall() or []

    children_map = {}
    users_by_id = {}
    for u in all_active_users:
        users_by_id[u["id"]] = u
        p_id = u.get("reporting_to_user_id")
        if p_id:
            children_map.setdefault(p_id, []).append(u["id"])

    team_members = []
    queue = [current_user["id"]]
    visited = {current_user["id"]}

    while queue:
        curr_id = queue.pop(0)
        children = children_map.get(curr_id, [])
        for ch_id in children:
            if ch_id not in visited:
                visited.add(ch_id)
                queue.append(ch_id)
                if ch_id in users_by_id:
                    team_members.append(users_by_id[ch_id])

    return team_members