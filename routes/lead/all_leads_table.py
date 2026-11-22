from config import get_db_connection
from routes.lead.all_leads_filters import (
    get_filter_request_values,
    normalize_value,
)
from routes.lead.all_leads_helpers import (
    fetch_logged_user_settings,
    fetch_user_tree,
)
from routes.lead.all_leads_rows import (
    prepare_lead_row,
)


# Page sizes accepted from the Bootstrap table.
ALLOWED_PAGE_SIZES = {
    5,
    10,
    25,
    50,
    100,
    250,
    500,
    1000,
}


def fetch_lead_rows(logged_user_uuid, request_args=None):
    """
    Backwards compatibility helper.
    """
    res = get_lead_table_data(logged_user_uuid, request_args or {})
    return res.get("data", [])


# Fields that users are allowed to sort.
ALLOWED_SORT_FIELDS = {
    "client_code",
    "name",
    "mobile_number",
    "status_name",
    "source_name",
    "owner_name",
    "latest_comment",
    "created_at",
    "updated_at",
    "assigned_at",
}

SORT_COLUMN_MAP = {
    "created_at": "l.created_at",
    "updated_at": "l.updated_at",
    "assigned_at": "l.assigned_at",
    "name": "l.name",
    "client_code": "l.id",
    "status_name": "st.status_name",
    "source_name": "ls.source_name",
    "owner_name": "u.full_name",
    "latest_comment": "l.comment",
    "mobile_number": "l.mobile_number",
}


def parse_positive_integer(
    value,
    default_value,
):
    """
    Convert a request value into a positive integer.
    """
    try:
        parsed_value = int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default_value

    return max(
        parsed_value,
        1,
    )


def get_table_request_values(
    request_args,
    logged_user_uuid="",
):
    """
    Read pagination, sorting, search and filter values.
    """
    page = parse_positive_integer(
        request_args.get("page"),
        1,
    )

    page_size = parse_positive_integer(
        request_args.get("page_size"),
        10,
    )

    if page_size not in ALLOWED_PAGE_SIZES:
        page_size = 10

    sort_field = str(
        request_args.get("sort")
        or "created_at"
    ).strip()

    if sort_field not in ALLOWED_SORT_FIELDS:
        sort_field = "created_at"

    sort_order = str(
        request_args.get("order")
        or "desc"
    ).strip().lower()

    if sort_order not in {
        "asc",
        "desc",
    }:
        sort_order = "desc"

    return {
        "page": page,
        "page_size": page_size,
        "sort": sort_field,
        "order": sort_order,
        "filters": get_filter_request_values(
            request_args,
            logged_user_uuid,
        ),
    }


def get_lead_table_data(
    logged_user_uuid,
    request_args,
):
    """
    Build the high-performance SQL server-side paginated response for the All Leads table.
    Directly executes LIMIT / OFFSET queries on MySQL to return in milliseconds.
    """
    table_request = get_table_request_values(
        request_args,
        logged_user_uuid,
    )
    filters = table_request["filters"]
    page = table_request["page"]
    page_size = table_request["page_size"]
    sort_field = table_request["sort"]
    sort_order = table_request["order"]

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            allowed_user_ids, allowed_user_uuids = fetch_user_tree(cursor, logged_user_uuid)
            user_settings = fetch_logged_user_settings(cursor, logged_user_uuid)
            from routes.settings_helpers import fetch_last_dialed_lead_uuid, encrypt_mobile
            last_dialed_lead_uuid = fetch_last_dialed_lead_uuid(cursor, logged_user_uuid)

            from utils.permissions import has_permission
            is_global = has_permission("global_access_scope", "global_data_access")
            if not is_global and logged_user_uuid:
                cursor.execute("SELECT id, is_admin, role_id FROM users WHERE user_uuid = %s LIMIT 1", (logged_user_uuid,))
                u_chk = cursor.fetchone() or {}
                if u_chk.get("is_admin") == 1 or u_chk.get("role_id") == 1:
                    is_global = True

            where_clauses = [
                "NOT EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id AND (so.order_status IS NULL OR LOWER(so.order_status) != 'rejected'))"
            ]
            where_params = []

            # 1. Hierarchy access scope
            if not is_global:
                if allowed_user_ids:
                    ph_ids = ", ".join(["%s"] * len(allowed_user_ids))
                    ph_uuids = ", ".join(["%s"] * len(allowed_user_uuids))
                    where_clauses.append(
                        f"(l.current_owner_user_id IN ({ph_ids}) "
                        f"OR l.created_by IN ({ph_ids}) "
                        f"OR l.created_by IN ({ph_uuids}))"
                    )
                    where_params.extend(list(allowed_user_ids) + list(allowed_user_ids) + list(allowed_user_uuids))
                else:
                    where_clauses.append("1 = 0")

            # 2. Call Status Filter
            call_status = filters.get("call_status")
            if call_status != "" and call_status is not None:
                where_clauses.append("l.call_status = %s")
                where_params.append(int(call_status))

            # 3. Source Filter (Pre-resolved)
            source = filters.get("source")
            if source not in ("", "all", "ALL", "All", None):
                resolved_source_id = None
                if str(source).isdigit():
                    resolved_source_id = int(source)
                else:
                    cursor.execute("SELECT id FROM lead_sources WHERE (source_uuid = %s OR source_name = %s) LIMIT 1", (source, source))
                    src_row = cursor.fetchone()
                    if src_row:
                        resolved_source_id = src_row["id"]

                if resolved_source_id:
                    where_clauses.append("(l.lead_source = %s OR l.lead_source = %s)")
                    where_params.extend([resolved_source_id, str(resolved_source_id)])
                else:
                    where_clauses.append("(ls.id = %s OR ls.source_name = %s OR ls.source_uuid = %s OR l.lead_source = %s)")
                    where_params.extend([source, source, source, source])

            # 4. Status Filter (Pre-resolved)
            status = filters.get("status")
            if status in ("no_status",):
                where_clauses.append("(l.lead_status IS NULL OR l.lead_status = '' OR l.lead_status = 'No Status' OR l.lead_status = '0')")
            elif status not in ("", "all", "ALL", "All", None):
                resolved_status_id = None
                if str(status).isdigit():
                    resolved_status_id = int(status)
                else:
                    cursor.execute("SELECT id FROM lead_statuses WHERE (status_uuid = %s OR status_name = %s) LIMIT 1", (status, status))
                    st_row = cursor.fetchone()
                    if st_row:
                        resolved_status_id = st_row["id"]

                if resolved_status_id:
                    where_clauses.append("(l.lead_status = %s OR l.lead_status = %s)")
                    where_params.extend([resolved_status_id, str(resolved_status_id)])
                else:
                    where_clauses.append("(st.id = %s OR st.status_uuid = %s OR st.status_name = %s OR l.lead_status = %s)")
                    where_params.extend([status, status, status, status])

            # 5. Owner Filter (Pre-resolved)
            owner = filters.get("owner")
            if owner in ("unassigned", "0", "not_assigned", "un_assigned"):
                where_clauses.append("(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0)")
            elif owner not in ("", "all", "ALL", "All", None):
                resolved_owner_id = None
                if str(owner).isdigit():
                    resolved_owner_id = int(owner)
                else:
                    cursor.execute("SELECT id FROM users WHERE user_uuid = %s LIMIT 1", (owner,))
                    u_row = cursor.fetchone()
                    if u_row:
                        resolved_owner_id = u_row["id"]

                if resolved_owner_id:
                    where_clauses.append("l.current_owner_user_id = %s")
                    where_params.append(resolved_owner_id)
                else:
                    where_clauses.append("(u.user_uuid = %s OR l.current_owner_user_id = %s)")
                    where_params.extend([owner, 0])

            # 6. Disposed Filter
            can_view_disposed = is_global or has_permission("leads", "assign_disposed_lead")

            disposed = filters.get("disposed", "0")
            if not can_view_disposed:
                where_clauses.append("(l.disposed_by IS NULL AND l.disposed_at IS NULL AND (l.is_disposed IS NULL OR l.is_disposed = 0))")
            elif disposed == "1":
                where_clauses.append("(l.disposed_by IS NOT NULL OR l.disposed_at IS NOT NULL OR l.is_disposed = 1)")
            elif disposed in ("all", "ALL"):
                pass  # Allow viewing all (active + disposed)
            else:
                where_clauses.append("(l.disposed_by IS NULL AND l.disposed_at IS NULL AND (l.is_disposed IS NULL OR l.is_disposed = 0))")

            # 7. Date Filters (Range indexed)
            if filters.get("created_from"):
                where_clauses.append("l.created_at >= %s")
                where_params.append(f"{filters['created_from']} 00:00:00")
            if filters.get("created_to"):
                where_clauses.append("l.created_at <= %s")
                where_params.append(f"{filters['created_to']} 23:59:59")
            if filters.get("modified_from"):
                where_clauses.append("l.updated_at >= %s")
                where_params.append(f"{filters['modified_from']} 00:00:00")
            if filters.get("modified_to"):
                where_clauses.append("l.updated_at <= %s")
                where_params.append(f"{filters['modified_to']} 23:59:59")
            if filters.get("assigned_from"):
                where_clauses.append("l.assigned_at >= %s")
                where_params.append(f"{filters['assigned_from']} 00:00:00")
            if filters.get("assigned_to"):
                where_clauses.append("l.assigned_at <= %s")
                where_params.append(f"{filters['assigned_to']} 23:59:59")

            # 8. Search Filter
            search = filters.get("search")
            if search:
                s_term = f"%{search}%"
                enc_num = encrypt_mobile(search) if (search.isdigit() and len(search) == 10) else None
                if enc_num:
                    where_clauses.append(
                        "(l.name LIKE %s OR l.email LIKE %s OR l.comment LIKE %s "
                        "OR l.lead_uuid LIKE %s OR l.id LIKE %s OR l.mobile_number = %s OR l.mobile_number LIKE %s)"
                    )
                    where_params.extend([s_term, s_term, s_term, s_term, s_term, enc_num, s_term])
                else:
                    where_clauses.append(
                        "(l.name LIKE %s OR l.email LIKE %s OR l.comment LIKE %s "
                        "OR l.lead_uuid LIKE %s OR l.id LIKE %s OR l.mobile_number LIKE %s)"
                    )
                    where_params.extend([s_term, s_term, s_term, s_term, s_term, s_term])

            where_sql = " AND ".join(where_clauses)

            joins_for_count = []
            if source not in ("", "all", "ALL", "All", None):
                joins_for_count.append("LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)")
            if status not in ("", "all", "ALL", "All", "no_status", None):
                joins_for_count.append("LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_uuid = l.lead_status OR st.status_name = l.lead_status)")
            if owner not in ("", "all", "ALL", "All", "unassigned", "0", "not_assigned", "un_assigned", None):
                joins_for_count.append("LEFT JOIN users u ON u.id = l.current_owner_user_id")

            count_joins_sql = " ".join(joins_for_count)
            count_sql = f"""
                SELECT COUNT(*) AS total
                FROM leads l
                {count_joins_sql}
                WHERE {where_sql}
            """
            cursor.execute(count_sql, where_params)
            count_row = cursor.fetchone()
            total_records = count_row["total"] if count_row else 0

            total_pages = max((total_records + page_size - 1) // page_size, 1)
            page = min(max(page, 1), total_pages)
            offset = (page - 1) * page_size

            # Sort mapping
            sort_column = SORT_COLUMN_MAP.get(sort_field, "l.created_at")
            sort_dir = "ASC" if str(sort_order).lower() == "asc" else "DESC"

            # Query the target page rows only
            data_sql = f"""
                SELECT
                    l.id, l.lead_uuid, l.name, l.mobile_number, l.email, l.address, l.state, l.city,
                    l.lead_source, ls.source_name AS source_name, ls.id AS source_id,
                    st.status_name AS status_name, st.id AS status_id, st.status_tone AS status_tone,
                    st.status_tone AS status_color,
                    l.lead_status, l.call_status, l.current_owner_user_id, l.lead_batch_id,
                    u.user_uuid AS owner_uuid, u.user_uuid AS user_uuid, u.full_name AS owner_name,
                    l.comment AS comment, l.created_at, l.updated_at, l.assigned_at,
                    0 AS has_contact,
                    0 AS has_followup,
                    0 AS has_free_trial,
                    0 AS has_so,
                    0 AS is_paid_client,
                    (CASE WHEN l.disposed_by IS NOT NULL OR l.disposed_at IS NOT NULL THEN 1 ELSE 0 END) AS is_disposed,
                    l.disposed_by, l.disposed_at,
                    NULL AS contact_uuid,
                    NULL AS followup_uuid,
                    NULL AS free_trial_uuid,
                    NULL AS sales_order_uuid,
                    l.comment AS latest_comment,
                    (SELECT u_act.full_name FROM lead_activities la JOIN users u_act ON u_act.id = la.user_id WHERE la.lead_id = l.id ORDER BY la.id DESC LIMIT 1) AS latest_comment_by,
                    0 AS comment_count
                FROM leads l
                LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)
                LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_uuid = l.lead_status OR st.status_name = l.lead_status)
                LEFT JOIN users u ON u.id = l.current_owner_user_id
                WHERE {where_sql}
                ORDER BY {sort_column} {sort_dir}
                LIMIT %s OFFSET %s
            """
            cursor.execute(data_sql, where_params + [page_size, offset])
            raw_rows = cursor.fetchall() or []

            prepared_rows = [
                prepare_lead_row(row, user_settings, last_dialed_lead_uuid)
                for row in raw_rows
            ]
    finally:
        connection.close()

    return {
        "success": True,
        "data": prepared_rows,
        "page": page,
        "page_size": page_size,
        "total": total_records,
        "total_pages": total_pages,
        "sort": sort_field,
        "order": sort_order,
    }