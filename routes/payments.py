import datetime
import uuid
from flask import render_template, session, jsonify, request, url_for, redirect, flash

from utils.permissions import has_permission
from config import get_db_connection
from routes.lead_action import get_action_permissions, get_current_user
from routes.lead_upload_common import serialize_grid_rows
from routes.settings_helpers import (
    decrypt_mobile, 
    fetch_owner_filter_options,
    fetch_logged_user_settings,
    fetch_last_dialed_lead_uuid,
    apply_mobile_and_last_dialed_context,
    build_mobile_button_context,
    resolve_selected_owner,
)


def get_payments_filter_metadata(cursor, logged_user_uuid):
    owner_context = fetch_owner_filter_options(cursor, logged_user_uuid)
    owners = owner_context["owners"]

    cursor.execute("SELECT id, status_name FROM lead_statuses ORDER BY id ASC")
    lead_statuses = cursor.fetchall() or []

    cursor.execute("SELECT id, source_name FROM lead_sources ORDER BY id ASC")
    lead_sources = cursor.fetchall() or []

    cursor.execute("SELECT id, product_name, weekly, two_weekly, monthly, two_monthly, quarterly, six_monthly, nine_monthly, yearly, eighteen_monthly, twenty_four_monthly FROM products WHERE status = 1 ORDER BY product_name ASC")
    products = cursor.fetchall() or []
    for p in products:
        for k, v in p.items():
            if k == "id" and v is not None:
                p[k] = int(v)
            elif hasattr(v, '__float__') and not isinstance(v, (int, bool)):
                p[k] = float(v)

    return {
        "owners": owners,
        "lead_statuses": lead_statuses,
        "lead_sources": lead_sources,
        "products": products
    }


def fetch_sales_orders_paged(cursor, logged_user_uuid, filter_params):
    user = get_current_user(cursor, logged_user_uuid)
    permissions = get_action_permissions(user)

    from utils.permissions import has_permission
    is_global = bool(user.get("is_admin")) or str(user.get("role_name", "")).lower() == "admin" or has_permission('global_access_scope', 'global_data_access')

    owner_context = fetch_owner_filter_options(cursor, logged_user_uuid)
    allowed_user_ids = None
    if not is_global:
        allowed_user_ids = owner_context["allowed_user_ids"]

    where_clauses = ["1=1"]
    where_params = []

    if allowed_user_ids:
        placeholders = ", ".join(["%s"] * len(allowed_user_ids))
        where_clauses.append(f"(l.current_owner_user_id IN ({placeholders}) OR so.created_by_user_id IN ({placeholders}))")
        where_params.extend(allowed_user_ids)
        where_params.extend(allowed_user_ids)

    # 1. Mode / Status
    status_filter = str(filter_params.get("status") or "all").lower().strip()
    mode_filter = str(filter_params.get("mode") or "all").lower().strip()

    target_status = status_filter if status_filter != "all" else mode_filter
    if target_status == "approved":
        where_clauses.append("so.order_status = 'approved'")
    elif target_status == "pending":
        where_clauses.append("so.order_status = 'pending'")
    elif target_status in ("rejected", "cancelled"):
        where_clauses.append("so.order_status IN ('rejected', 'cancelled')")

    # 2. Payment Mode
    pay_mode = str(filter_params.get("payment_mode") or filter_params.get("mode_val") or "all").lower().strip()
    if pay_mode and pay_mode != "all":
        where_clauses.append("LOWER(so.payment_mode) LIKE %s")
        where_params.append(f"%{pay_mode}%")

    # 3. Product
    product_val = str(filter_params.get("product") or "all").strip()
    if product_val and product_val.lower() != "all":
        where_clauses.append("LOWER(so.product_name) = %s")
        where_params.append(product_val.lower())

    # 4. Owner
    owner_val = str(filter_params.get("owner") or "all").strip()
    if owner_val and owner_val != "all":
        if owner_val == "unassigned":
            where_clauses.append("(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0)")
        else:
            where_clauses.append("u_owner.user_uuid = %s")
            where_params.append(owner_val)

    # 5. Date Filter (using so.created_at)
    date_preset = str(filter_params.get("date_preset") or "all").strip().lower()
    start_date = str(filter_params.get("start_date") or "").strip()
    end_date = str(filter_params.get("end_date") or "").strip()

    if date_preset == "today":
        where_clauses.append("DATE(so.created_at) = CURRENT_DATE()")
    elif date_preset == "yesterday":
        where_clauses.append("DATE(so.created_at) = CURRENT_DATE() - INTERVAL 1 DAY")
    elif date_preset == "this_week":
        where_clauses.append("YEARWEEK(so.created_at, 1) = YEARWEEK(CURRENT_DATE(), 1)")
    elif date_preset == "this_month":
        where_clauses.append("YEAR(so.created_at) = YEAR(CURRENT_DATE()) AND MONTH(so.created_at) = MONTH(CURRENT_DATE())")
    elif date_preset == "custom":
        if start_date:
            where_clauses.append("DATE(so.created_at) >= %s")
            where_params.append(start_date)
        if end_date:
            where_clauses.append("DATE(so.created_at) <= %s")
            where_params.append(end_date)

    # 6. Search
    search = str(filter_params.get("search") or "").strip()
    if search:
        s_term = f"%{search}%"
        where_clauses.append("""
            (
                so.order_number LIKE %s
                OR so.invoice_name LIKE %s
                OR l.name LIKE %s
                OR l.id LIKE %s
                OR l.mobile_number LIKE %s
                OR l.email LIKE %s
                OR so.pan_number LIKE %s
                OR so.reference_number LIKE %s
                OR so.notes LIKE %s
                OR so.product_name LIKE %s
            )
        """)
        where_params.extend([s_term] * 10)

    where_sql = " AND ".join(where_clauses)

    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM sales_orders so
        JOIN leads l ON l.id = so.lead_id
        LEFT JOIN users u_owner ON u_owner.id = l.current_owner_user_id
        WHERE {where_sql}
    """
    cursor.execute(count_sql, where_params)
    count_row = cursor.fetchone()
    total_records = count_row["total"] if count_row else 0

    page_size = max(1, min(int(filter_params.get("page_size") or 10), 1000))
    total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
    page = max(1, min(int(filter_params.get("page") or 1), total_pages))
    offset = (page - 1) * page_size

    data_sql = f"""
        SELECT
            so.id,
            so.sales_order_uuid,
            so.order_number,
            COALESCE(so.order_amount, 0.0) AS order_amount,
            so.gross_amount,
            so.tax_percentage,
            so.tax_amount,
            so.net_amount,
            COALESCE(so.order_status, 'pending') AS order_status,
            COALESCE(so.payment_mode, 'N/A') AS payment_mode,
            COALESCE(so.reference_number, '') AS reference_number,
            COALESCE(so.invoice_name, '') AS invoice_name,
            COALESCE(so.product_name, 'N/A') AS product_name,
            COALESCE(so.plan_name, 'N/A') AS plan_name,
            COALESCE(so.kyc_status, 'Pending') AS kyc_status,
            COALESCE(so.email_sent, 0) AS email_sent,
            COALESCE(so.notes, '') AS notes,
            so.gst_number,
            so.pan_number,
            so.aadhaar_number,
            DATE_FORMAT(so.dob, '%%Y-%%m-%%d') AS dob,
            DATE_FORMAT(COALESCE(so.payment_date, so.service_start_date), '%%Y-%%m-%%d') AS payment_date,
            DATE_FORMAT(so.service_start_date, '%%Y-%%m-%%d') AS service_start_date,
            DATE_FORMAT(so.service_expiry_date, '%%Y-%%m-%%d') AS service_expiry_date,
            so.created_at,
            l.id AS lead_id,
            l.lead_uuid,
            COALESCE(NULLIF(TRIM(so.invoice_name), ''), NULLIF(TRIM(l.name), ''), 'No Name') AS lead_name,
            l.mobile_number,
            l.email,
            COALESCE(NULLIF(TRIM(so.address), ''), NULLIF(TRIM(l.address), ''), '') AS address,
            COALESCE(NULLIF(TRIM(so.city), ''), NULLIF(TRIM(l.city), ''), '') AS city,
            COALESCE(NULLIF(TRIM(so.state), ''), NULLIF(TRIM(l.state), ''), '') AS state,
            l.call_status,
            l.lead_status AS current_lead_status_id,
            COALESCE(ls.source_name, 'No Source') AS lead_source,
            COALESCE(st.status_name, 'No Status') AS lead_status,
            COALESCE(st.id, 0) AS lead_status_id,
            COALESCE(st.status_tone, 'slate') AS status_tone,
            COALESCE(st.status_tone, 'slate') AS status_color,
            COALESCE(u_creator.full_name, so.created_by_name, 'System') AS creator_name,
            COALESCE(u_owner.full_name, 'Unassigned') AS owner_name,
            u_owner.user_uuid AS owner_uuid,
            COALESCE(u_manager.full_name, 'N/A') AS manager_name,
            u_manager.user_uuid AS manager_uuid
        FROM sales_orders so
        JOIN leads l ON l.id = so.lead_id
        LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)
        LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_name = l.lead_status)
        LEFT JOIN users u_creator ON u_creator.id = so.created_by_user_id
        LEFT JOIN users u_owner ON u_owner.id = l.current_owner_user_id
        LEFT JOIN users u_manager ON u_manager.id = u_owner.reporting_to_user_id
        WHERE {where_sql}
        ORDER BY so.id DESC
        LIMIT %s OFFSET %s
    """
    cursor.execute(data_sql, where_params + [page_size, offset])
    rows = cursor.fetchall() or []

    user_settings = fetch_logged_user_settings(cursor, logged_user_uuid)
    last_dialed_lead_uuid = fetch_last_dialed_lead_uuid(cursor, logged_user_uuid)
    from utils.product_helpers import get_plan_label

    for row in rows:
        apply_mobile_and_last_dialed_context(row, user_settings, last_dialed_lead_uuid)
        row["client_code"] = f"{row['lead_id']}"
        display_name = (row.get("invoice_name") or "").strip() or (row.get("lead_name") or "").strip()
        if not display_name or display_name.lower() in ("none", "no name", "none none", "null", "n/a", "na"):
            display_name = "No Name"
        row["lead_name"] = display_name
        row["plan_label"] = get_plan_label(row.get("plan_name"))

        addr = (row.get("address") or "").strip()
        city = (row.get("city") or "").strip()
        state = (row.get("state") or "").strip()
        loc_parts = []
        if city and state:
            loc_parts.append(f"{city} - {state}")
        elif city:
            loc_parts.append(city)
        elif state:
            loc_parts.append(state)

        row["full_address"] = addr
        row["city_state"] = loc_parts[0] if loc_parts else ""
        row["pan_number"] = (row.get("pan_number") or "").strip().upper() or "N/A"

        if "decrypted_mobile" not in row:
            row["decrypted_mobile"] = decrypt_mobile(row["mobile_number"]) if permissions["can_view_mobile"] else "Hidden"

        if row.get("created_at"):
            if isinstance(row["created_at"], (datetime.date, datetime.datetime)):
                row["created_at_fmt"] = row["created_at"].strftime("%d %b %Y, %I:%M %p")
                row["created_at"] = str(row["created_at"])
            else:
                row["created_at_fmt"] = str(row["created_at"])
        else:
            row["created_at_fmt"] = "N/A"

        for date_key, fmt_key in [("payment_date", "payment_date_fmt"), ("service_start_date", "service_start_date_fmt"), ("service_expiry_date", "service_expiry_date_fmt"), ("dob", "dob_fmt")]:
            val = row.get(date_key)
            if val and str(val).strip() not in ("None", "N/A", ""):
                if isinstance(val, (datetime.date, datetime.datetime)):
                    row[fmt_key] = val.strftime("%d %b %Y")
                else:
                    try:
                        d_obj = datetime.datetime.strptime(str(val)[:10], "%Y-%m-%d")
                        row[fmt_key] = d_obj.strftime("%d %b %Y")
                    except Exception:
                        row[fmt_key] = str(val)
            else:
                row[fmt_key] = "N/A"

        row["gross_amount"] = float(row.get("gross_amount") or row.get("order_amount") or 0.0)
        row["tax_amount"] = float(row.get("tax_amount") or 0.0)
        row["tax_percentage"] = float(row.get("tax_percentage") or 0.0)
        row["net_amount"] = float(row.get("net_amount") or 0.0)

    return {
        "success": True,
        "payments": serialize_grid_rows(rows),
        "total_records": total_records,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size
    }


def get_payments_data(cursor, logged_user_uuid, mode="all", target_lead_uuid=""):
    user = get_current_user(cursor, logged_user_uuid)
    permissions = get_action_permissions(user)

    from utils.permissions import has_permission
    is_global = bool(user.get("is_admin")) or str(user.get("role_name", "")).lower() == "admin" or has_permission('global_access_scope', 'global_data_access')

    owner_context = fetch_owner_filter_options(cursor, logged_user_uuid)
    owners = owner_context["owners"]
    allowed_user_ids = None
    if not is_global:
        allowed_user_ids = owner_context["allowed_user_ids"]

    # Fetch active lead statuses, sources, and products for filter bar
    cursor.execute("SELECT id, status_name FROM lead_statuses ORDER BY id ASC")
    lead_statuses = cursor.fetchall() or []

    cursor.execute("SELECT id, source_name FROM lead_sources ORDER BY id ASC")
    lead_sources = cursor.fetchall() or []

    cursor.execute("SELECT id, product_name, weekly, two_weekly, monthly, two_monthly, quarterly, six_monthly, nine_monthly, yearly, eighteen_monthly, twenty_four_monthly FROM products WHERE status = 1 ORDER BY product_name ASC")
    products = cursor.fetchall() or []
    for p in products:
        for k, v in p.items():
            if k == "id" and v is not None:
                p[k] = int(v)
            elif hasattr(v, '__float__') and not isinstance(v, (int, bool)):
                p[k] = float(v)

    # Build base hierarchy filter for sales_orders & leads
    hierarchy_where = ""
    hierarchy_params = []
    if allowed_user_ids:
        placeholders = ", ".join(["%s"] * len(allowed_user_ids))
        hierarchy_where = f" AND (l.current_owner_user_id IN ({placeholders}) OR so.created_by_user_id IN ({placeholders}))"
        hierarchy_params.extend(allowed_user_ids)
        hierarchy_params.extend(allowed_user_ids)

    # 1. Fetch KPIs
    kpi_sql = f"""
        SELECT 
            COUNT(*) AS total_count,
            COALESCE(SUM(so.net_amount), 0) AS total_amount,
            COALESCE(SUM(CASE WHEN so.order_status = 'approved' THEN 1 ELSE 0 END), 0) AS approved_count,
            COALESCE(SUM(CASE WHEN so.order_status = 'approved' THEN so.net_amount ELSE 0 END), 0) AS approved_amount,
            COALESCE(SUM(CASE WHEN so.order_status = 'pending' THEN 1 ELSE 0 END), 0) AS pending_count,
            COALESCE(SUM(CASE WHEN so.order_status = 'pending' THEN so.net_amount ELSE 0 END), 0) AS pending_amount,
            COALESCE(SUM(CASE WHEN so.order_status IN ('rejected', 'cancelled') THEN 1 ELSE 0 END), 0) AS rejected_count,
            COALESCE(SUM(CASE WHEN so.order_status IN ('rejected', 'cancelled') THEN so.net_amount ELSE 0 END), 0) AS rejected_amount
        FROM sales_orders so
        JOIN leads l ON l.id = so.lead_id
        WHERE 1=1 {hierarchy_where}
    """
    cursor.execute(kpi_sql, hierarchy_params)
    kpis = cursor.fetchone() or {
        "total_count": 0, "total_amount": 0,
        "approved_count": 0, "approved_amount": 0,
        "pending_count": 0, "pending_amount": 0,
        "rejected_count": 0, "rejected_amount": 0
    }

    # 2. Detailed Payments List
    sql = f"""
        SELECT
            so.id,
            so.sales_order_uuid,
            so.order_number,
            COALESCE(so.order_amount, 0.0) AS order_amount,
            so.gross_amount,
            so.tax_percentage,
            so.tax_amount,
            so.net_amount,
            COALESCE(so.order_status, 'pending') AS order_status,
            COALESCE(so.payment_mode, 'N/A') AS payment_mode,
            COALESCE(so.reference_number, '') AS reference_number,
            COALESCE(so.invoice_name, '') AS invoice_name,
            COALESCE(so.product_name, 'N/A') AS product_name,
            COALESCE(so.plan_name, 'N/A') AS plan_name,
            COALESCE(so.kyc_status, 'Pending') AS kyc_status,
            COALESCE(so.email_sent, 0) AS email_sent,
            COALESCE(so.notes, '') AS notes,
            so.gst_number,
            so.pan_number,
            so.aadhaar_number,
            DATE_FORMAT(so.dob, '%%Y-%%m-%%d') AS dob,
            DATE_FORMAT(COALESCE(so.payment_date, so.service_start_date), '%%Y-%%m-%%d') AS payment_date,
            DATE_FORMAT(so.service_start_date, '%%Y-%%m-%%d') AS service_start_date,
            DATE_FORMAT(so.service_expiry_date, '%%Y-%%m-%%d') AS service_expiry_date,
            so.created_at,
            l.id AS lead_id,
            l.lead_uuid,
            COALESCE(NULLIF(TRIM(so.invoice_name), ''), NULLIF(TRIM(l.name), ''), 'No Name') AS lead_name,
            l.mobile_number,
            l.email,
            COALESCE(NULLIF(TRIM(so.address), ''), NULLIF(TRIM(l.address), ''), '') AS address,
            COALESCE(NULLIF(TRIM(so.city), ''), NULLIF(TRIM(l.city), ''), '') AS city,
            COALESCE(NULLIF(TRIM(so.state), ''), NULLIF(TRIM(l.state), ''), '') AS state,
            l.call_status,
            l.lead_status AS current_lead_status_id,
            COALESCE(ls.source_name, 'No Source') AS lead_source,
            COALESCE(st.status_name, 'No Status') AS lead_status,
            COALESCE(st.id, 0) AS lead_status_id,
            COALESCE(st.status_tone, 'slate') AS status_tone,
            COALESCE(st.status_tone, 'slate') AS status_color,
            COALESCE(u_creator.full_name, so.created_by_name, 'System') AS creator_name,
            COALESCE(u_owner.full_name, 'Unassigned') AS owner_name,
            u_owner.user_uuid AS owner_uuid,
            COALESCE(u_manager.full_name, 'N/A') AS manager_name,
            u_manager.user_uuid AS manager_uuid
        FROM sales_orders so
        JOIN leads l ON l.id = so.lead_id
        LEFT JOIN lead_sources ls ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)
        LEFT JOIN lead_statuses st ON (st.id = l.lead_status OR st.status_name = l.lead_status)
        LEFT JOIN users u_creator ON u_creator.id = so.created_by_user_id
        LEFT JOIN users u_owner ON u_owner.id = l.current_owner_user_id
        LEFT JOIN users u_manager ON u_manager.id = u_owner.reporting_to_user_id
        WHERE 1=1 {hierarchy_where}
    """

    params = list(hierarchy_params)

    if mode == "approved":
        sql += " AND so.order_status = 'approved'"
    elif mode == "pending":
        sql += " AND so.order_status = 'pending'"
    elif mode == "rejected":
        sql += " AND so.order_status IN ('rejected', 'cancelled')"

    if target_lead_uuid:
        sql += " AND (l.lead_uuid = %s OR l.id = %s)"
        params.extend([target_lead_uuid, int(target_lead_uuid) if str(target_lead_uuid).isdigit() else -1])

    sql += " ORDER BY so.id DESC"

    cursor.execute(sql, params)
    rows = cursor.fetchall() or []

    user_settings = fetch_logged_user_settings(cursor, logged_user_uuid)
    last_dialed_lead_uuid = fetch_last_dialed_lead_uuid(cursor, logged_user_uuid)

    for row in rows:
        apply_mobile_and_last_dialed_context(row, user_settings, last_dialed_lead_uuid)
        row["client_code"] = f"{row['lead_id']}"
        display_name = (row.get("invoice_name") or "").strip() or (row.get("lead_name") or "").strip()
        if not display_name or display_name.lower() in ("none", "no name", "none none", "null", "n/a", "na"):
            display_name = "No Name"
        row["lead_name"] = display_name

        # Address & City-State formatting
        addr = (row.get("address") or "").strip()
        city = (row.get("city") or "").strip()
        state = (row.get("state") or "").strip()
        loc_parts = []
        if city and state:
            loc_parts.append(f"{city} - {state}")
        elif city:
            loc_parts.append(city)
        elif state:
            loc_parts.append(state)

        row["full_address"] = addr
        row["city_state"] = loc_parts[0] if loc_parts else ""
        row["pan_number"] = (row.get("pan_number") or "").strip().upper() or "N/A"

        if "decrypted_mobile" not in row:
            row["decrypted_mobile"] = decrypt_mobile(row["mobile_number"]) if permissions["can_view_mobile"] else "Hidden"

        if row.get("created_at"):
            if isinstance(row["created_at"], (datetime.date, datetime.datetime)):
                row["created_at_fmt"] = row["created_at"].strftime("%d %b %Y, %I:%M %p")
                row["created_at"] = str(row["created_at"])
            else:
                row["created_at_fmt"] = str(row["created_at"])
        else:
            row["created_at_fmt"] = "N/A"

        for date_key, fmt_key in [("payment_date", "payment_date_fmt"), ("service_start_date", "service_start_date_fmt"), ("service_expiry_date", "service_expiry_date_fmt"), ("dob", "dob_fmt")]:
            val = row.get(date_key)
            if val and str(val).strip() not in ("None", "N/A", ""):
                if isinstance(val, (datetime.date, datetime.datetime)):
                    row[fmt_key] = val.strftime("%d %b %Y")
                else:
                    try:
                        d_obj = datetime.datetime.strptime(str(val)[:10], "%Y-%m-%d")
                        row[fmt_key] = d_obj.strftime("%d %b %Y")
                    except Exception:
                        row[fmt_key] = str(val)
            else:
                row[fmt_key] = "N/A"

        # Ensure amounts are floats for template formatting
        row["gross_amount"] = float(row.get("gross_amount") or row.get("order_amount") or 0.0)
        row["tax_amount"] = float(row.get("tax_amount") or 0.0)
        row["tax_percentage"] = float(row.get("tax_percentage") or 0.0)
        row["net_amount"] = float(row.get("net_amount") or 0.0)

    return {
        "kpis": kpis,
        "payments": serialize_grid_rows(rows),
        "owners": owners,
        "lead_statuses": lead_statuses,
        "lead_sources": lead_sources,
        "products": products
    }


def resolve_selected_owner(logged_user_uuid):
    owner_req = request.args.get("owner")
    if owner_req is not None and owner_req != "":
        return owner_req
    return logged_user_uuid or "all"


def payments_routes(app):

    @app.route("/api/sales-orders/list", methods=["POST", "GET"])
    def api_sales_orders_list():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Login is required."}), 401

        payload = request.get_json(silent=True) or {}
        if request.method == "GET":
            payload = request.args.to_dict()

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                result = fetch_sales_orders_paged(cursor, logged_user_uuid, payload)
                return jsonify(result)
        except Exception as e:
            print("[Sales Orders API Error]:", e)
            return jsonify({
                "success": False,
                "message": f"Error loading sales orders: {str(e)}",
                "payments": [],
                "total_records": 0,
                "total_pages": 1,
                "current_page": 1,
            }), 500
        finally:
            conn.close()

    @app.route("/payments")
    @app.route("/sales-order")
    @app.route("/sales-orders", endpoint="all_payments")
    def all_payments():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                metadata = get_payments_filter_metadata(cursor, logged_user_uuid)
        finally:
            conn.close()

        saved_filters = session.get("sales_orders_filters", {})

        return render_template(
            "payments/all_payments.html",
            owners=metadata["owners"],
            lead_statuses=metadata["lead_statuses"],
            lead_sources=metadata["lead_sources"],
            products=metadata["products"],
            logged_user_uuid=logged_user_uuid,
            selected_owner=resolve_selected_owner(logged_user_uuid),
            saved_filters=saved_filters,
            active_group="payments",
            active_page="all_payments",
            page_title="Sales Orders",
            page_heading="All Sales Orders",
            mode="all",
        )

    @app.route("/payments/approved")
    @app.route("/sales-order/approved")
    @app.route("/sales-orders/approved", endpoint="approved_payments")
    def approved_payments():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                metadata = get_payments_filter_metadata(cursor, logged_user_uuid)
        finally:
            conn.close()

        saved_filters = session.get("sales_orders_filters", {})

        return render_template(
            "payments/all_payments.html",
            owners=metadata["owners"],
            lead_statuses=metadata["lead_statuses"],
            lead_sources=metadata["lead_sources"],
            products=metadata["products"],
            logged_user_uuid=logged_user_uuid,
            selected_owner=resolve_selected_owner(logged_user_uuid),
            saved_filters=saved_filters,
            active_group="payments",
            active_page="all_payments",
            page_title="Approved Sales Orders",
            page_heading="Approved Sales Orders",
            mode="approved",
        )

    @app.route("/payments/pending")
    @app.route("/sales-order/pending")
    @app.route("/sales-orders/pending", endpoint="pending_payments")
    def pending_payments():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                metadata = get_payments_filter_metadata(cursor, logged_user_uuid)
        finally:
            conn.close()

        saved_filters = session.get("sales_orders_filters", {})

        return render_template(
            "payments/all_payments.html",
            owners=metadata["owners"],
            lead_statuses=metadata["lead_statuses"],
            lead_sources=metadata["lead_sources"],
            products=metadata["products"],
            logged_user_uuid=logged_user_uuid,
            selected_owner=resolve_selected_owner(logged_user_uuid),
            saved_filters=saved_filters,
            active_group="payments",
            active_page="all_payments",
            page_title="Pending Sales Orders",
            page_heading="Pending Sales Orders",
            mode="pending",
        )

    @app.route("/payments/rejected")
    @app.route("/sales-order/rejected")
    @app.route("/sales-orders/rejected", endpoint="rejected_payments")
    def rejected_payments():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                metadata = get_payments_filter_metadata(cursor, logged_user_uuid)
        finally:
            conn.close()

        saved_filters = session.get("sales_orders_filters", {})

        return render_template(
            "payments/all_payments.html",
            owners=metadata["owners"],
            lead_statuses=metadata["lead_statuses"],
            lead_sources=metadata["lead_sources"],
            products=metadata["products"],
            logged_user_uuid=logged_user_uuid,
            selected_owner=resolve_selected_owner(logged_user_uuid),
            saved_filters=saved_filters,
            active_group="payments",
            active_page="all_payments",
            page_title="Rejected Sales Orders",
            page_heading="Rejected Sales Orders",
            mode="rejected",
        )

    @app.route("/api/sales-orders/save-filters", methods=["POST"])
    def api_save_sales_orders_filters():
        data = request.get_json(silent=True) or {}
        session["sales_orders_filters"] = {
            "status": str(data.get("status") or "all").strip(),
            "mode": str(data.get("mode") or "all").strip(),
            "product": str(data.get("product") or "all").strip(),
            "owner": str(data.get("owner") or "all").strip(),
            "date_preset": str(data.get("date_preset") or "all").strip(),
            "start_date": str(data.get("start_date") or "").strip(),
            "end_date": str(data.get("end_date") or "").strip(),
            "search": str(data.get("search") or "").strip(),
            "page_size": int(data.get("page_size") or 10),
            "page": int(data.get("page") or 1),
        }
        session.modified = True
        return jsonify({"success": True, "saved_filters": session["sales_orders_filters"]})

    @app.route("/api/sales-orders/send-invoice", methods=["POST"])
    def api_send_sales_order_invoice():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Login is required."}), 401

        payload = request.get_json(silent=True) or {}
        so_uuid = payload.get("sales_order_uuid")
        if not so_uuid:
            return jsonify({"success": False, "message": "Sales order UUID is required."}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT so.id, so.order_number, so.order_status, so.email, so.lead_id, l.name AS lead_name
                    FROM sales_orders so
                    JOIN leads l ON l.id = so.lead_id
                    WHERE so.sales_order_uuid = %s LIMIT 1
                """, (so_uuid,))
                so = cursor.fetchone()
                if not so:
                    return jsonify({"success": False, "message": "Sales order not found."}), 404

                if so.get("order_status") != "approved":
                    return jsonify({"success": False, "message": "Invoice email can only be sent for approved sales orders."}), 400

                cursor.execute("""
                    UPDATE sales_orders
                    SET email_sent = 1, updated_at = NOW()
                    WHERE sales_order_uuid = %s
                """, (so_uuid,))

                # Log activity
                act_uuid = f"ACT{uuid.uuid4().hex[:12].upper()}"
                cursor.execute("""
                    INSERT INTO lead_activities (
                        activity_uuid, lead_id, user_id, action_type, status_name, comment
                    ) VALUES (%s, %s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), 'Invoice Email Sent', 'approved', %s)
                """, (act_uuid, so["lead_id"], logged_user_uuid, f"Invoice email sent for Sales Order {so['order_number']}"))

                conn.commit()
                return jsonify({"success": True, "message": f"Invoice email sent successfully for order {so['order_number']}!"})
        finally:
            conn.close()

    @app.route("/sales-orders/download-invoice/<sales_order_uuid>")
    def download_sales_order_invoice(sales_order_uuid):
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            flash("Login is required to download invoice.", "warning")
            return redirect(url_for("login"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT so.*, l.name AS lead_name, l.mobile_number, l.email AS lead_email, l.address AS lead_address, l.client_code
                    FROM sales_orders so
                    JOIN leads l ON l.id = so.lead_id
                    WHERE so.sales_order_uuid = %s LIMIT 1
                """, (sales_order_uuid,))
                so = cursor.fetchone()
                if not so:
                    flash("Sales order not found.", "danger")
                    return redirect(url_for("all_payments"))

                for k in ["gross_amount", "order_amount", "tax_percentage", "tax_amount", "net_amount"]:
                    if so.get(k) is not None:
                        so[k] = float(so[k])
        finally:
            conn.close()

        return render_template("payments/invoice_print.html", so=so)

    @app.route("/api/sales-orders/delete", methods=["POST"])
    def api_delete_sales_order():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Login is required."}), 401

        from utils.permissions import has_permission
        if not has_permission("payments", "delete"):
            return jsonify({"success": False, "message": "Access Denied: You do not have permission to delete Sales Orders."}), 403

        payload = request.get_json(silent=True) or {}
        so_uuid = payload.get("sales_order_uuid")
        if not so_uuid:
            return jsonify({"success": False, "message": "Sales order UUID is required."}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, order_number, order_status, lead_id FROM sales_orders WHERE sales_order_uuid = %s LIMIT 1", (so_uuid,))
                so = cursor.fetchone()
                if not so:
                    return jsonify({"success": False, "message": "Sales order not found."}), 404

                if (so.get("order_status") or "").lower() == "approved":
                    return jsonify({"success": False, "message": "Approved Sales Orders cannot be deleted."}), 400

                cursor.execute("DELETE FROM sales_orders WHERE sales_order_uuid = %s", (so_uuid,))

                user_act_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
                cursor.execute("""
                    INSERT INTO user_activities (
                        user_activity_uuid, user_id, lead_id, action_type, description
                    ) VALUES (%s, (SELECT id FROM users WHERE user_uuid = %s LIMIT 1), %s, 'Delete Sales Order', %s)
                """, (user_act_uuid, logged_user_uuid, so["lead_id"], f"Deleted Sales Order {so['order_number']}"))

                conn.commit()
                return jsonify({"success": True, "message": f"Sales Order '{so['order_number']}' deleted successfully."})
        finally:
            conn.close()

    @app.route("/clients", endpoint="all_clients")
    def all_clients():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                owner_context = fetch_owner_filter_options(cursor, logged_user_uuid)
                owners = owner_context["owners"]

                cursor.execute("""
                    SELECT DISTINCT u_mgr.user_uuid, u_mgr.full_name
                    FROM users u_mgr
                    JOIN users u ON u.reporting_to_user_id = u_mgr.id
                    WHERE u_mgr.status = 1
                    ORDER BY u_mgr.full_name ASC
                """)
                managers = cursor.fetchall() or []
        finally:
            conn.close()

        saved_filters = session.get("clients_filters", {})

        return render_template(
            "payments/all_clients.html",
            owners=owners,
            managers=managers,
            logged_user_uuid=logged_user_uuid,
            selected_owner=resolve_selected_owner(logged_user_uuid),
            saved_filters=saved_filters,
            active_group="clients",
            active_page="all_clients",
            page_title="Clients",
            page_heading="Clients Management"
        )

    @app.route("/api/clients/data", methods=["GET"])
    def api_clients_data():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                user = get_current_user(cursor, logged_user_uuid)
                is_global = bool(user.get("is_admin")) or str(user.get("role_name", "")).lower() == "admin" or has_permission('global_access_scope', 'global_data_access')

                owner_context = fetch_owner_filter_options(cursor, logged_user_uuid)
                allowed_user_ids = None if is_global else owner_context["allowed_user_ids"]

                try:
                    page = max(1, int(request.args.get("page", 1)))
                except (ValueError, TypeError):
                    page = 1
                try:
                    per_page = min(100, max(1, int(request.args.get("per_page", 10))))
                except (ValueError, TypeError):
                    per_page = 10
                offset = (page - 1) * per_page

                status_filter = str(request.args.get("status") or "all").strip().lower()
                owner_filter = str(request.args.get("owner") or "all").strip()
                manager_filter = str(request.args.get("manager") or "all").strip()
                date_preset = str(request.args.get("date_preset") or "all").strip().lower()
                search_query = str(request.args.get("search") or "").strip()

                where_clauses = ["1=1"]
                params = []

                # Scope hierarchy
                if allowed_user_ids:
                    placeholders = ", ".join(["%s"] * len(allowed_user_ids))
                    where_clauses.append(f"(l.current_owner_user_id IN ({placeholders}) OR c.created_by_user_id IN ({placeholders}))")
                    params.extend(allowed_user_ids)
                    params.extend(allowed_user_ids)

                # Status filter
                if status_filter and status_filter != "all":
                    where_clauses.append("LOWER(c.client_status) = %s")
                    params.append(status_filter)

                # Owner filter
                if owner_filter and owner_filter != "all":
                    if owner_filter == "unassigned":
                        where_clauses.append("(l.current_owner_user_id IS NULL OR l.current_owner_user_id = 0)")
                    else:
                        where_clauses.append("u_owner.user_uuid = %s")
                        params.append(owner_filter)

                # Manager filter
                if manager_filter and manager_filter != "all":
                    where_clauses.append("u_manager.user_uuid = %s")
                    params.append(manager_filter)

                # Date preset
                if date_preset == "today":
                    where_clauses.append("c.created_at >= CURDATE()")
                elif date_preset == "yesterday":
                    where_clauses.append("c.created_at >= CURDATE() - INTERVAL 1 DAY AND c.created_at < CURDATE()")
                elif date_preset == "this_week":
                    where_clauses.append("c.created_at >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)")
                elif date_preset == "this_month":
                    where_clauses.append("c.created_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')")

                # Search query
                if search_query:
                    q_like = f"%{search_query}%"
                    where_clauses.append("""(
                        c.client_name LIKE %s OR 
                        c.client_code LIKE %s OR 
                        c.email LIKE %s OR 
                        c.mobile_number LIKE %s OR 
                        u_owner.full_name LIKE %s OR 
                        u_manager.full_name LIKE %s OR 
                        so.order_number LIKE %s
                    )""")
                    params.extend([q_like, q_like, q_like, q_like, q_like, q_like, q_like])

                where_sql = " AND ".join(where_clauses)

                # Count total distinct leads
                count_sql = f"""
                    SELECT COUNT(DISTINCT c.lead_id) AS total_count
                    FROM clients c
                    JOIN leads l ON l.id = c.lead_id
                    LEFT JOIN sales_orders so ON (so.id = c.sales_order_id OR so.sales_order_uuid = c.sales_order_uuid)
                    LEFT JOIN users u_owner ON u_owner.id = l.current_owner_user_id
                    LEFT JOIN users u_creator ON u_creator.id = c.created_by_user_id
                    LEFT JOIN users u_manager ON u_manager.id = u_owner.reporting_to_user_id
                    WHERE {where_sql}
                """
                cursor.execute(count_sql, tuple(params))
                total_records = (cursor.fetchone() or {}).get("total_count") or 0

                # Fetch paginated distinct leads
                leads_sql = f"""
                    SELECT 
                        c.lead_id,
                        l.lead_uuid,
                        l.call_status,
                        MAX(c.client_code) AS client_code,
                        MAX(c.client_name) AS client_name,
                        MAX(c.mobile_number) AS mobile_number,
                        MAX(c.email) AS email,
                        MAX(c.address) AS address,
                        MAX(c.client_status) AS client_status,
                        MAX(c.notes) AS notes,
                        MAX(c.created_at) AS created_at,
                        COUNT(c.id) AS invoices_count,
                        COALESCE(SUM(c.grand_total), 0) AS total_payment,
                        COALESCE(MAX(u_owner.full_name), 'Unassigned') AS owner_name,
                        MAX(u_owner.user_uuid) AS owner_uuid,
                        COALESCE(MAX(u_manager.full_name), 'N/A') AS manager_name,
                        MAX(u_manager.user_uuid) AS manager_uuid,
                        COALESCE(MAX(u_creator.full_name), MAX(c.created_by_name), 'System') AS creator_name
                    FROM clients c
                    JOIN leads l ON l.id = c.lead_id
                    LEFT JOIN sales_orders so ON (so.id = c.sales_order_id OR so.sales_order_uuid = c.sales_order_uuid)
                    LEFT JOIN users u_owner ON u_owner.id = l.current_owner_user_id
                    LEFT JOIN users u_creator ON u_creator.id = c.created_by_user_id
                    LEFT JOIN users u_manager ON u_manager.id = u_owner.reporting_to_user_id
                    WHERE {where_sql}
                    GROUP BY c.lead_id, l.lead_uuid, l.call_status
                    ORDER BY MAX(c.id) DESC
                    LIMIT %s OFFSET %s
                """
                fetch_params = list(params) + [per_page, offset]
                cursor.execute(leads_sql, tuple(fetch_params))
                client_rows = cursor.fetchall() or []

                user_settings = fetch_logged_user_settings(cursor, logged_user_uuid)
                last_dialed_lead_uuid = fetch_last_dialed_lead_uuid(cursor, logged_user_uuid)

                # Fetch invoices for only the current page's leads
                lead_ids = [r["lead_id"] for r in client_rows]
                invoices_map = {}
                if lead_ids:
                    lead_placeholders = ", ".join(["%s"] * len(lead_ids))
                    cursor.execute(f"""
                        SELECT c.*, so.order_number
                        FROM clients c
                        LEFT JOIN sales_orders so ON (so.id = c.sales_order_id OR so.sales_order_uuid = c.sales_order_uuid)
                        WHERE c.lead_id IN ({lead_placeholders})
                        ORDER BY c.sales_order_id ASC
                    """, tuple(lead_ids))
                    for inv in cursor.fetchall() or []:
                        lid = inv["lead_id"]
                        for k in ["total_amount", "tax_amount", "grand_total"]:
                            if inv.get(k) is not None:
                                inv[k] = float(inv[k])
                        for d_k in ["service_start_date", "service_expiry_date", "created_at"]:
                            if inv.get(d_k):
                                inv[d_k] = str(inv[d_k])
                        invoices_map.setdefault(lid, []).append(inv)

                clients_list = []
                for r in client_rows:
                    lid = r["lead_id"]
                    raw_mob = str(r.get("mobile_number") or "").strip()
                    lead_uuid_val = str(r.get("lead_uuid") or "").strip()
                    lead_name_val = str(r.get("client_name") or "Client").strip()
                    call_status_val = int(r.get("call_status") or 0)
                    tot_pay = float(r.get("total_payment") or 0.0)

                    c_at = r.get("created_at")
                    created_at_fmt = c_at.strftime("%d %b %Y, %I:%M %p") if hasattr(c_at, "strftime") else (str(c_at)[:16] if c_at else "")

                    c_dict = {
                        "lead_id": lid,
                        "lead_uuid": lead_uuid_val,
                        "client_code": r.get("client_code") or str(lid),
                        "client_name": lead_name_val,
                        "name": lead_name_val,
                        "mobile_number": raw_mob,
                        "call_status": call_status_val,
                        "email": r.get("email") or "N/A",
                        "address": r.get("address") or "N/A",
                        "owner_name": r.get("owner_name") or "Unassigned",
                        "owner_uuid": r.get("owner_uuid") or "",
                        "manager_name": r.get("manager_name") or "N/A",
                        "manager_uuid": r.get("manager_uuid") or "",
                        "client_status": r.get("client_status") or "active",
                        "created_at": str(c_at) if c_at else "",
                        "created_at_fmt": created_at_fmt,
                        "creator_name": r.get("creator_name") or "System",
                        "notes": r.get("notes") or "",
                        "invoices": invoices_map.get(lid, []),
                        "invoices_count": int(r.get("invoices_count") or len(invoices_map.get(lid, []))),
                        "total_payment": tot_pay,
                    }
                    apply_mobile_and_last_dialed_context(c_dict, user_settings, last_dialed_lead_uuid)
                    clients_list.append(c_dict)

                import math
                total_pages = max(1, math.ceil(total_records / per_page)) if total_records > 0 else 1
                start_index = offset + 1 if total_records > 0 else 0
                end_index = min(offset + per_page, total_records)

                return jsonify({
                    "success": True,
                    "clients": clients_list,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total_records": total_records,
                        "total_pages": total_pages,
                        "start_index": start_index,
                        "end_index": end_index,
                        "has_prev": page > 1,
                        "has_next": page < total_pages
                    }
                })
        finally:
            conn.close()

    @app.route("/api/clients/save-filters", methods=["POST"])
    def api_save_clients_filters():
        data = request.get_json(silent=True) or {}
        session["clients_filters"] = {
            "status": str(data.get("status") or "all").strip(),
            "owner": str(data.get("owner") or "all").strip(),
            "manager": str(data.get("manager") or "all").strip(),
            "date_preset": str(data.get("date_preset") or "all").strip(),
            "start_date": str(data.get("start_date") or "").strip(),
            "end_date": str(data.get("end_date") or "").strip(),
            "search": str(data.get("search") or "").strip(),
            "page_size": int(data.get("page_size") or 10),
            "page": int(data.get("page") or 1),
        }
        session.modified = True
        return jsonify({"success": True, "saved_filters": session["clients_filters"]})

    @app.route("/api/clients/update-status", methods=["POST"], endpoint="api_update_client_status")
    def api_update_client_status():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Login is required."}), 401

        payload = request.get_json(silent=True) or {}
        client_id = payload.get("client_id")
        new_status = (payload.get("client_status") or "").strip().lower()

        if not client_id or not new_status:
            return jsonify({"success": False, "message": "Client ID and status are required."}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, client_name, client_status FROM clients WHERE id = %s LIMIT 1", (client_id,))
                client_row = cursor.fetchone()
                if not client_row:
                    return jsonify({"success": False, "message": "Client record not found."}), 404

                cursor.execute("UPDATE clients SET client_status = %s, updated_at = NOW() WHERE id = %s", (new_status, client_id))
                conn.commit()

                return jsonify({"success": True, "message": f"Service status updated to '{new_status.title()}' successfully."})
        finally:
            conn.close()

