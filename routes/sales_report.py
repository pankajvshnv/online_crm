import io
import csv
import re
from datetime import datetime, date
from decimal import Decimal
from functools import wraps
from flask import render_template, session, jsonify, request, flash, redirect, url_for, Response

from config import get_db_connection
from utils.permissions import has_permission
from routes.lead_action import get_action_permissions, get_current_user
from routes.settings_helpers import decrypt_mobile, fetch_user_tree


def require_sales_report_permission(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_info = session.get("user", {})
        role_name = str(user_info.get("role_name") or "").lower()
        if user_info.get("is_admin") == 1 or role_name in ["admin", "super admin", "superadmin"] or user_info.get("id") in [1, 20]:
            return f(*args, **kwargs)
        if not (has_permission("reports", "sales_report") or has_permission("reports", "view") or has_permission("payments", "view")):
            if request.path.startswith("/api/") or request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "message": "Access Denied: You do not have permission for Sales Report."}), 403
            flash("Access Denied: You do not have permission to access Sales Report.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function


def clean_text(val):
    if val is None:
        return ""
    # Strip excess spaces and normalize whitespace
    return " ".join(str(val).split())


def serialize_num(val):
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


def build_sales_query_conditions(args, allowed_user_ids=None):
    where_clauses = ["1=1"]
    params = []

    # Hierarchy filter
    if allowed_user_ids:
        placeholders = ", ".join(["%s"] * len(allowed_user_ids))
        where_clauses.append(f"(so.created_by_user_id IN ({placeholders}) OR l.current_owner_user_id IN ({placeholders}))")
        params.extend(allowed_user_ids)
        params.extend(allowed_user_ids)

    # Date preset or custom date range
    # Date column used for sales reporting: COALESCE(so.payment_date, DATE(so.created_at))
    date_col = "COALESCE(so.payment_date, DATE(so.created_at))"
    preset = (args.get("preset") or "").strip().lower()
    start_date = (args.get("start_date") or "").strip()
    end_date = (args.get("end_date") or "").strip()

    if preset == "today":
        where_clauses.append(f"{date_col} = CURRENT_DATE()")
    elif preset == "yesterday":
        where_clauses.append(f"{date_col} = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)")
    elif preset == "this_week":
        where_clauses.append(f"{date_col} >= DATE_SUB(CURRENT_DATE(), INTERVAL WEEKDAY(CURRENT_DATE()) DAY)")
    elif preset == "this_month":
        where_clauses.append(f"{date_col} >= DATE_FORMAT(CURRENT_DATE(), '%%Y-%%m-01')")
    elif preset == "last_month":
        where_clauses.append(f"{date_col} >= DATE_FORMAT(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), '%%Y-%%m-01') AND {date_col} < DATE_FORMAT(CURRENT_DATE(), '%%Y-%%m-01')")
    elif preset == "custom" or (start_date or end_date):
        if start_date:
            where_clauses.append(f"{date_col} >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append(f"{date_col} <= %s")
            params.append(end_date)
    # If preset == "all_time" or empty, no date restriction applied

    # Order Status filter
    status = (args.get("status") or "").strip().lower()
    if status and status != "all":
        if status in ["approved", "pending", "rejected", "cancelled"]:
            where_clauses.append("so.order_status = %s")
            params.append(status)

    # Sales Rep filter
    rep_id = (args.get("rep_id") or "").strip()
    if rep_id and rep_id != "all":
        where_clauses.append("(so.created_by_user_id = %s OR l.current_owner_user_id = %s)")
        params.extend([rep_id, rep_id])

    # Product filter
    product = (args.get("product") or "").strip()
    if product and product != "all":
        where_clauses.append("so.product_name = %s")
        params.append(product)

    # Payment Mode filter
    payment_mode = (args.get("payment_mode") or "").strip()
    if payment_mode and payment_mode != "all":
        where_clauses.append("so.payment_mode = %s")
        params.append(payment_mode)

    # Search filter
    search = (args.get("search") or "").strip()
    if search:
        search_pattern = f"%{search}%"
        where_clauses.append("""
            (so.order_number LIKE %s 
             OR so.invoice_name LIKE %s 
             OR l.name LIKE %s 
             OR l.mobile_number LIKE %s 
             OR so.reference_number LIKE %s)
        """)
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern, search_pattern])

    return " AND ".join(where_clauses), params


def sales_report_routes(app):

    @app.route("/reports/sales", endpoint="sales_report")
    @app.route("/reports/sales-report", endpoint="sales_report_page")
    @require_sales_report_permission
    def sales_report_view():
        """
        Renders the Sales Report page with dynamic KPI overview,
        filter bar, sales orders table, sales reps leaderboard, and product breakdown.
        """
        user_info = session.get("user", {})
        logged_user_uuid = session.get("user_uuid")
        role_name = str(user_info.get("role_name") or "").lower()
        is_global = bool(user_info.get("is_admin")) or role_name in ["admin", "super admin", "superadmin"] or user_info.get("id") in [1, 20] or has_permission("global_access_scope", "global_data_access")
        can_export = is_global or has_permission("global_access_scope", "global_data_export")

        conn = get_db_connection()
        reps = []
        products = []
        payment_modes = ["UPI", "Net Banking", "Card", "Cheque", "Cash", "Other"]

        if conn:
            try:
                with conn.cursor() as cursor:
                    # Allowed hierarchy
                    allowed_user_ids = None
                    if not is_global and logged_user_uuid:
                        allowed_user_ids, _ = fetch_user_tree(cursor, logged_user_uuid)

                    # Fetch active reps who have orders or are in the team
                    if allowed_user_ids:
                        placeholders = ", ".join(["%s"] * len(allowed_user_ids))
                        cursor.execute(f"""
                            SELECT DISTINCT u.id, u.full_name
                            FROM users u
                            WHERE u.id IN ({placeholders}) AND u.status = 1
                            ORDER BY u.full_name ASC
                        """, allowed_user_ids)
                    else:
                        cursor.execute("""
                            SELECT DISTINCT u.id, u.full_name
                            FROM users u
                            WHERE u.status = 1 AND (
                                u.id IN (SELECT DISTINCT created_by_user_id FROM sales_orders WHERE created_by_user_id IS NOT NULL)
                                OR u.role_id IN (SELECT id FROM roles WHERE LOWER(role_name) LIKE '%sale%')
                            )
                            ORDER BY u.full_name ASC
                        """)
                    reps = cursor.fetchall() or []

                    # Fetch distinct products present in sales orders or product catalog
                    cursor.execute("""
                        SELECT DISTINCT product_name 
                        FROM sales_orders 
                        WHERE product_name IS NOT NULL AND product_name != '' 
                        ORDER BY product_name ASC
                    """)
                    prod_rows = cursor.fetchall() or []
                    products = [r["product_name"] for r in prod_rows if r.get("product_name")]
            except Exception as e:
                print("Error loading sales report filter options:", e)
            finally:
                conn.close()

        return render_template(
            "reports/sales_report.html",
            active_group="reports",
            active_page="sales_report",
            page_title="Sales Report",
            reps=reps,
            products=products,
            payment_modes=payment_modes,
            can_export=can_export,
        )

    @app.route("/api/reports/sales-data")
    @require_sales_report_permission
    def api_reports_sales_data():
        """
        API endpoint returning sales KPIs, paginated sales orders,
        sales reps performance, and product revenue breakdown.
        """
        user_info = session.get("user", {})
        logged_user_uuid = session.get("user_uuid")
        role_name = str(user_info.get("role_name") or "").lower()
        is_global = bool(user_info.get("is_admin")) or role_name in ["admin", "super admin", "superadmin"] or user_info.get("id") in [1, 20] or has_permission("global_access_scope", "global_data_access")

        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(5, int(request.args.get("per_page", 20))))
        offset = (page - 1) * per_page

        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection error"}), 500

        try:
            with conn.cursor() as cursor:
                # Allowed hierarchy
                allowed_user_ids = None
                if not is_global and logged_user_uuid:
                    allowed_user_ids, _ = fetch_user_tree(cursor, logged_user_uuid)

                # Check can view plain mobile
                user = get_current_user(cursor, logged_user_uuid)
                permissions = get_action_permissions(user)
                can_view_mobile = permissions.get("can_view_mobile", False)

                where_sql, params = build_sales_query_conditions(request.args, allowed_user_ids)

                # 1. KPI Aggregation
                kpi_sql = f"""
                    SELECT 
                        COUNT(*) AS total_orders,
                        COALESCE(SUM(so.gross_amount), 0) AS total_gross,
                        COALESCE(SUM(so.net_amount), 0) AS total_revenue,
                        COALESCE(SUM(CASE WHEN so.order_status = 'approved' THEN 1 ELSE 0 END), 0) AS approved_orders,
                        COALESCE(SUM(CASE WHEN so.order_status = 'approved' THEN so.net_amount ELSE 0 END), 0) AS approved_revenue,
                        COALESCE(SUM(CASE WHEN so.order_status = 'pending' THEN 1 ELSE 0 END), 0) AS pending_orders,
                        COALESCE(SUM(CASE WHEN so.order_status = 'pending' THEN so.net_amount ELSE 0 END), 0) AS pending_revenue,
                        COALESCE(SUM(CASE WHEN so.order_status IN ('rejected', 'cancelled') THEN 1 ELSE 0 END), 0) AS rejected_orders,
                        COALESCE(SUM(CASE WHEN so.order_status IN ('rejected', 'cancelled') THEN so.net_amount ELSE 0 END), 0) AS rejected_revenue,
                        COUNT(DISTINCT so.created_by_user_id) AS active_reps_count
                    FROM sales_orders so
                    LEFT JOIN leads l ON l.id = so.lead_id
                    WHERE {where_sql}
                """
                cursor.execute(kpi_sql, params)
                kpi_row = cursor.fetchone() or {}

                total_orders = int(kpi_row.get("total_orders") or 0)
                total_gross = serialize_num(kpi_row.get("total_gross"))
                total_revenue = serialize_num(kpi_row.get("total_revenue"))
                approved_orders = int(kpi_row.get("approved_orders") or 0)
                approved_revenue = serialize_num(kpi_row.get("approved_revenue"))
                pending_orders = int(kpi_row.get("pending_orders") or 0)
                pending_revenue = serialize_num(kpi_row.get("pending_revenue"))
                rejected_orders = int(kpi_row.get("rejected_orders") or 0)
                rejected_revenue = serialize_num(kpi_row.get("rejected_revenue"))
                active_reps_count = int(kpi_row.get("active_reps_count") or 0)
                avg_deal_size = round(approved_revenue / approved_orders, 2) if approved_orders > 0 else 0.0

                # 2. Paginated Sales Orders
                orders_sql = f"""
                    SELECT 
                        so.id,
                        so.sales_order_uuid,
                        so.order_number,
                        DATE_FORMAT(COALESCE(so.payment_date, DATE(so.created_at)), '%%d %%b %%Y') AS order_date,
                        DATE_FORMAT(so.created_at, '%%d %%b %%Y %%h:%%i %%p') AS created_at_fmt,
                        DATE_FORMAT(so.approved_at, '%%d %%b %%Y %%h:%%i %%p') AS approved_at_fmt,
                        COALESCE(so.gross_amount, 0.0) AS gross_amount,
                        COALESCE(so.tax_percentage, 0.0) AS tax_percentage,
                        COALESCE(so.tax_amount, 0.0) AS tax_amount,
                        COALESCE(so.net_amount, 0.0) AS net_amount,
                        COALESCE(so.order_status, 'pending') AS order_status,
                        COALESCE(so.payment_mode, 'N/A') AS payment_mode,
                        COALESCE(so.reference_number, '') AS reference_number,
                        COALESCE(NULLIF(TRIM(so.invoice_name), ''), NULLIF(TRIM(l.name), ''), 'No Name') AS lead_name,
                        l.mobile_number,
                        COALESCE(l.email, so.email, '') AS email,
                        COALESCE(so.city, l.city, '') AS city,
                        COALESCE(so.state, l.state, '') AS state,
                        COALESCE(so.product_name, 'N/A') AS product_name,
                        COALESCE(so.plan_name, 'N/A') AS plan_name,
                        COALESCE(so.notes, '') AS notes,
                        COALESCE(u_creator.full_name, so.created_by_name, 'System') AS rep_name,
                        so.created_by_user_id,
                        l.lead_uuid
                    FROM sales_orders so
                    LEFT JOIN leads l ON l.id = so.lead_id
                    LEFT JOIN users u_creator ON u_creator.id = so.created_by_user_id
                    WHERE {where_sql}
                    ORDER BY COALESCE(so.payment_date, DATE(so.created_at)) DESC, so.id DESC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(orders_sql, params + [per_page, offset])
                raw_orders = cursor.fetchall() or []

                orders = []
                for idx, o in enumerate(raw_orders, start=offset + 1):
                    raw_mob = o.get("mobile_number")
                    dec_mob = decrypt_mobile(raw_mob) if raw_mob else ""
                    if not can_view_mobile and dec_mob:
                        # Mask mobile number if no permission
                        dec_mob = ("*" * (len(dec_mob) - 4)) + dec_mob[-4:] if len(dec_mob) >= 4 else "******"

                    orders.append({
                        "sno": idx,
                        "id": o.get("id"),
                        "sales_order_uuid": o.get("sales_order_uuid"),
                        "order_number": clean_text(o.get("order_number")),
                        "order_date": o.get("order_date") or "",
                        "created_at_fmt": o.get("created_at_fmt") or "",
                        "approved_at_fmt": o.get("approved_at_fmt") or "",
                        "lead_name": clean_text(o.get("lead_name")),
                        "mobile_number": dec_mob,
                        "email": clean_text(o.get("email")),
                        "city": clean_text(o.get("city")),
                        "state": clean_text(o.get("state")),
                        "product_name": clean_text(o.get("product_name")),
                        "plan_name": clean_text(o.get("plan_name")),
                        "gross_amount": serialize_num(o.get("gross_amount")),
                        "tax_percentage": serialize_num(o.get("tax_percentage")),
                        "tax_amount": serialize_num(o.get("tax_amount")),
                        "net_amount": serialize_num(o.get("net_amount")),
                        "payment_mode": clean_text(o.get("payment_mode")),
                        "reference_number": clean_text(o.get("reference_number")),
                        "order_status": (o.get("order_status") or "pending").lower(),
                        "rep_name": clean_text(o.get("rep_name")),
                        "notes": clean_text(o.get("notes")),
                        "lead_uuid": o.get("lead_uuid") or "",
                    })

                total_pages = (total_orders + per_page - 1) // per_page if total_orders > 0 else 1

                # 3. Sales Reps Leaderboard / Performance
                reps_sql = f"""
                    SELECT 
                        so.created_by_user_id AS rep_id,
                        COALESCE(u.full_name, so.created_by_name, 'Unknown Rep') AS rep_name,
                        COUNT(*) AS total_orders,
                        COALESCE(SUM(CASE WHEN so.order_status = 'approved' THEN 1 ELSE 0 END), 0) AS approved_orders,
                        COALESCE(SUM(CASE WHEN so.order_status = 'pending' THEN 1 ELSE 0 END), 0) AS pending_orders,
                        COALESCE(SUM(so.net_amount), 0) AS total_revenue,
                        COALESCE(SUM(CASE WHEN so.order_status = 'approved' THEN so.net_amount ELSE 0 END), 0) AS approved_revenue,
                        COALESCE(SUM(CASE WHEN so.order_status = 'pending' THEN so.net_amount ELSE 0 END), 0) AS pending_revenue
                    FROM sales_orders so
                    LEFT JOIN leads l ON l.id = so.lead_id
                    LEFT JOIN users u ON u.id = so.created_by_user_id
                    WHERE {where_sql}
                    GROUP BY so.created_by_user_id, rep_name
                    ORDER BY approved_revenue DESC, total_revenue DESC
                """
                cursor.execute(reps_sql, params)
                raw_reps = cursor.fetchall() or []

                reps_breakdown = []
                for idx, r in enumerate(raw_reps, start=1):
                    appr_rev = serialize_num(r.get("approved_revenue"))
                    tot_rev = serialize_num(r.get("total_revenue"))
                    appr_ord = int(r.get("approved_orders") or 0)
                    share_pct = round((appr_rev / approved_revenue) * 100, 1) if approved_revenue > 0 else 0.0
                    avg_ticket = round(appr_rev / appr_ord, 2) if appr_ord > 0 else 0.0

                    reps_breakdown.append({
                        "rank": idx,
                        "rep_id": r.get("rep_id"),
                        "rep_name": clean_text(r.get("rep_name")),
                        "total_orders": int(r.get("total_orders") or 0),
                        "approved_orders": appr_ord,
                        "pending_orders": int(r.get("pending_orders") or 0),
                        "total_revenue": tot_rev,
                        "approved_revenue": appr_rev,
                        "pending_revenue": serialize_num(r.get("pending_revenue")),
                        "avg_deal": avg_ticket,
                        "share_pct": share_pct,
                    })

                # 4. Products Breakdown
                prod_sql = f"""
                    SELECT 
                        COALESCE(NULLIF(TRIM(so.product_name), ''), 'Unspecified Product') AS product_name,
                        COUNT(*) AS total_orders,
                        COALESCE(SUM(CASE WHEN so.order_status = 'approved' THEN 1 ELSE 0 END), 0) AS approved_orders,
                        COALESCE(SUM(so.gross_amount), 0) AS total_gross,
                        COALESCE(SUM(so.net_amount), 0) AS total_net,
                        COALESCE(SUM(CASE WHEN so.order_status = 'approved' THEN so.net_amount ELSE 0 END), 0) AS approved_net
                    FROM sales_orders so
                    LEFT JOIN leads l ON l.id = so.lead_id
                    WHERE {where_sql}
                    GROUP BY product_name
                    ORDER BY approved_net DESC, total_net DESC
                """
                cursor.execute(prod_sql, params)
                raw_prods = cursor.fetchall() or []

                products_breakdown = []
                for p in raw_prods:
                    p_appr_net = serialize_num(p.get("approved_net"))
                    p_tot_net = serialize_num(p.get("total_net"))
                    p_orders = int(p.get("total_orders") or 0)
                    p_appr_orders = int(p.get("approved_orders") or 0)
                    share_pct = round((p_appr_net / approved_revenue) * 100, 1) if approved_revenue > 0 else 0.0
                    avg_ticket = round(p_appr_net / p_appr_orders, 2) if p_appr_orders > 0 else 0.0

                    products_breakdown.append({
                        "product_name": clean_text(p.get("product_name")),
                        "total_orders": p_orders,
                        "approved_orders": p_appr_orders,
                        "total_gross": serialize_num(p.get("total_gross")),
                        "total_net": p_tot_net,
                        "approved_net": p_appr_net,
                        "avg_price": avg_ticket,
                        "share_pct": share_pct,
                    })

                # 5. Timeline Trend
                timeline_sql = f"""
                    SELECT 
                        DATE_FORMAT(COALESCE(so.payment_date, DATE(so.created_at)), '%%Y-%%m-%%d') AS sale_date,
                        DATE_FORMAT(COALESCE(so.payment_date, DATE(so.created_at)), '%%d %%b') AS date_label,
                        COUNT(*) AS orders_count,
                        COALESCE(SUM(so.net_amount), 0) AS total_amount,
                        COALESCE(SUM(CASE WHEN so.order_status = 'approved' THEN so.net_amount ELSE 0 END), 0) AS approved_amount,
                        COALESCE(SUM(CASE WHEN so.order_status = 'pending' THEN so.net_amount ELSE 0 END), 0) AS pending_amount
                    FROM sales_orders so
                    LEFT JOIN leads l ON l.id = so.lead_id
                    WHERE {where_sql}
                    GROUP BY sale_date, date_label
                    ORDER BY sale_date ASC
                """
                cursor.execute(timeline_sql, params)
                raw_timeline = cursor.fetchall() or []
                timeline = []
                for t in raw_timeline:
                    timeline.append({
                        "sale_date": t.get("sale_date"),
                        "date_label": t.get("date_label"),
                        "orders_count": int(t.get("orders_count") or 0),
                        "total_amount": serialize_num(t.get("total_amount")),
                        "approved_amount": serialize_num(t.get("approved_amount")),
                        "pending_amount": serialize_num(t.get("pending_amount")),
                    })

                # 6. Payment Modes Breakdown
                paymode_sql = f"""
                    SELECT 
                        COALESCE(NULLIF(TRIM(so.payment_mode), ''), 'Other') AS mode_name,
                        COUNT(*) AS orders_count,
                        COALESCE(SUM(so.net_amount), 0) AS total_amount
                    FROM sales_orders so
                    LEFT JOIN leads l ON l.id = so.lead_id
                    WHERE {where_sql}
                    GROUP BY mode_name
                    ORDER BY total_amount DESC
                """
                cursor.execute(paymode_sql, params)
                raw_modes = cursor.fetchall() or []
                payment_modes_data = []
                for m in raw_modes:
                    payment_modes_data.append({
                        "mode_name": clean_text(m.get("mode_name")),
                        "orders_count": int(m.get("orders_count") or 0),
                        "total_amount": serialize_num(m.get("total_amount")),
                    })

                # 7. Status Breakdown
                status_sql = f"""
                    SELECT 
                        COALESCE(so.order_status, 'pending') AS status_name,
                        COUNT(*) AS orders_count,
                        COALESCE(SUM(so.net_amount), 0) AS total_amount
                    FROM sales_orders so
                    LEFT JOIN leads l ON l.id = so.lead_id
                    WHERE {where_sql}
                    GROUP BY status_name
                    ORDER BY total_amount DESC
                """
                cursor.execute(status_sql, params)
                raw_status = cursor.fetchall() or []
                status_breakdown = []
                for s in raw_status:
                    status_breakdown.append({
                        "status_name": clean_text(s.get("status_name")).capitalize(),
                        "orders_count": int(s.get("orders_count") or 0),
                        "total_amount": serialize_num(s.get("total_amount")),
                    })

                return jsonify({
                    "success": True,
                    "kpis": {
                        "total_orders": total_orders,
                        "total_gross": total_gross,
                        "total_revenue": total_revenue,
                        "approved_orders": approved_orders,
                        "approved_revenue": approved_revenue,
                        "pending_orders": pending_orders,
                        "pending_revenue": pending_revenue,
                        "rejected_orders": rejected_orders,
                        "rejected_revenue": rejected_revenue,
                        "avg_deal_size": avg_deal_size,
                        "active_reps_count": active_reps_count,
                    },
                    "orders": {
                        "data": orders,
                        "page": page,
                        "per_page": per_page,
                        "total_records": total_orders,
                        "total_pages": total_pages,
                    },
                    "reps_breakdown": reps_breakdown,
                    "products_breakdown": products_breakdown,
                    "timeline": timeline,
                    "payment_modes_breakdown": payment_modes_data,
                    "status_breakdown": status_breakdown,
                })
        except Exception as e:
            print("Error in api_reports_sales_data:", e)
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

    @app.route("/reports/sales/export")
    @require_sales_report_permission
    def export_sales_report():
        """
        Exports filtered sales records into a well-formatted CSV file
        with clean column headers and trimmed values.
        """
        user_info = session.get("user", {})
        logged_user_uuid = session.get("user_uuid")
        role_name = str(user_info.get("role_name") or "").lower()
        is_global = bool(user_info.get("is_admin")) or role_name in ["admin", "super admin", "superadmin"] or user_info.get("id") in [1, 20] or has_permission("global_access_scope", "global_data_access")

        can_export = is_global or has_permission("global_access_scope", "global_data_export")
        if not can_export:
            return jsonify({"success": False, "message": "Access Denied: Export permission required."}), 403

        conn = get_db_connection()
        if not conn:
            flash("Database connection error during export.", "danger")
            return redirect(url_for("sales_report"))

        try:
            with conn.cursor() as cursor:
                # Allowed hierarchy
                allowed_user_ids = None
                if not is_global and logged_user_uuid:
                    allowed_user_ids, _ = fetch_user_tree(cursor, logged_user_uuid)

                user = get_current_user(cursor, logged_user_uuid)
                permissions = get_action_permissions(user)
                can_view_mobile = permissions.get("can_view_mobile", False)

                where_sql, params = build_sales_query_conditions(request.args, allowed_user_ids)

                export_sql = f"""
                    SELECT 
                        so.id,
                        so.order_number,
                        DATE_FORMAT(COALESCE(so.payment_date, DATE(so.created_at)), '%%Y-%%m-%%d') AS order_date,
                        DATE_FORMAT(so.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at_fmt,
                        DATE_FORMAT(so.approved_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS approved_at_fmt,
                        COALESCE(so.gross_amount, 0.0) AS gross_amount,
                        COALESCE(so.tax_percentage, 0.0) AS tax_percentage,
                        COALESCE(so.tax_amount, 0.0) AS tax_amount,
                        COALESCE(so.net_amount, 0.0) AS net_amount,
                        COALESCE(so.order_status, 'pending') AS order_status,
                        COALESCE(so.payment_mode, 'N/A') AS payment_mode,
                        COALESCE(so.reference_number, '') AS reference_number,
                        COALESCE(NULLIF(TRIM(so.invoice_name), ''), NULLIF(TRIM(l.name), ''), 'No Name') AS lead_name,
                        l.mobile_number,
                        COALESCE(l.email, so.email, '') AS email,
                        COALESCE(so.city, l.city, '') AS city,
                        COALESCE(so.state, l.state, '') AS state,
                        COALESCE(so.product_name, 'N/A') AS product_name,
                        COALESCE(so.plan_name, 'N/A') AS plan_name,
                        COALESCE(so.notes, '') AS notes,
                        COALESCE(u_creator.full_name, so.created_by_name, 'System') AS rep_name
                    FROM sales_orders so
                    LEFT JOIN leads l ON l.id = so.lead_id
                    LEFT JOIN users u_creator ON u_creator.id = so.created_by_user_id
                    WHERE {where_sql}
                    ORDER BY COALESCE(so.payment_date, DATE(so.created_at)) DESC, so.id DESC
                    LIMIT 20000
                """
                cursor.execute(export_sql, params)
                records = cursor.fetchall() or []

                rows = []
                for idx, r in enumerate(records, start=1):
                    raw_mob = r.get("mobile_number")
                    dec_mob = decrypt_mobile(raw_mob) if raw_mob else ""
                    if not can_view_mobile and dec_mob:
                        dec_mob = ("*" * (len(dec_mob) - 4)) + dec_mob[-4:] if len(dec_mob) >= 4 else "******"

                    rows.append({
                        "S.No": idx,
                        "Order Number": clean_text(r.get("order_number")),
                        "Order Date": clean_text(r.get("order_date")),
                        "Client / Lead Name": clean_text(r.get("lead_name")),
                        "Mobile Number": clean_text(dec_mob),
                        "Email": clean_text(r.get("email")),
                        "City": clean_text(r.get("city")),
                        "State": clean_text(r.get("state")),
                        "Product Name": clean_text(r.get("product_name")),
                        "Plan Name": clean_text(r.get("plan_name")),
                        "Gross Amount": f"{serialize_num(r.get('gross_amount')):.2f}",
                        "Tax Percentage": f"{serialize_num(r.get('tax_percentage')):.2f}%",
                        "Tax Amount": f"{serialize_num(r.get('tax_amount')):.2f}",
                        "Net Amount": f"{serialize_num(r.get('net_amount')):.2f}",
                        "Payment Mode": clean_text(r.get("payment_mode")),
                        "Reference Number": clean_text(r.get("reference_number")),
                        "Order Status": clean_text(r.get("order_status")).upper(),
                        "Sales Representative": clean_text(r.get("rep_name")),
                        "Notes": clean_text(r.get("notes")),
                        "Created At": clean_text(r.get("created_at_fmt")),
                        "Approved At": clean_text(r.get("approved_at_fmt")),
                    })

                fieldnames = [
                    "S.No", "Order Number", "Order Date", "Client / Lead Name", "Mobile Number", "Email",
                    "City", "State", "Product Name", "Plan Name", "Gross Amount", "Tax Percentage", "Tax Amount",
                    "Net Amount", "Payment Mode", "Reference Number", "Order Status", "Sales Representative",
                    "Notes", "Created At", "Approved At"
                ]

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"sales_report_{timestamp}.csv"

                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)

                return Response(
                    output.getvalue(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"},
                )
        except Exception as e:
            print("Error exporting sales report:", e)
            flash(f"Error during export: {str(e)}", "danger")
            return redirect(url_for("sales_report"))
        finally:
            conn.close()
