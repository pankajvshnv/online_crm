import json
from datetime import datetime
from flask import render_template, request, session, redirect, url_for, jsonify
from config import get_db_connection
from utils.permissions import has_permission
from routes.settings_helpers import format_mobile_display, fetch_logged_user_settings


def get_user_team_ids(cursor, user_id):
    """
    Returns list of user IDs in team of user_id (self + all direct & indirect reportees).
    """
    if not user_id:
        return []
    team_ids = {user_id}
    to_process = [user_id]
    
    while to_process:
        curr = to_process.pop(0)
        cursor.execute("SELECT id FROM users WHERE reporting_to_user_id = %s AND status = 1", (curr,))
        reportees = cursor.fetchall()
        for r in reportees:
            r_id = r["id"]
            if r_id not in team_ids:
                team_ids.add(r_id)
                to_process.append(r_id)
                
    return list(team_ids)


def dashboard_routes(app):
    @app.route("/", endpoint="dashboard_home")
    @app.route("/dashboard", endpoint="dashboard")
    def dashboard():
        user_uuid = session.get("user_uuid")
        if not user_uuid:
            return redirect(url_for("login"))

        connection = get_db_connection()
        if not connection:
            return render_template(
                "dashboard.html",
                active_group="dashboard",
                active_page="dashboard",
                page_title="Dashboard",
                logged_user={},
                sales_with_gst=True
            )

        try:
            with connection.cursor() as cursor:
                # 1. Logged-in user info (Instant lookup)
                cursor.execute("""
                    SELECT u.id, u.user_uuid, u.full_name, u.username, u.role_id, u.designation_id, u.target, r.role_name, d.designation_name
                    FROM users u
                    LEFT JOIN roles r ON r.id = u.role_id
                    LEFT JOIN designations d ON d.id = u.designation_id
                    WHERE u.user_uuid = %s LIMIT 1
                """, (user_uuid,))
                logged_user = cursor.fetchone()
                if not logged_user:
                    return redirect(url_for("login"))

                # 2. Sales Display with GST setting
                cursor.execute("SELECT setting_key, setting_value FROM system_settings WHERE setting_key = 'sales_display_with_gst' LIMIT 1")
                setting_row = cursor.fetchone()
                sales_with_gst = (str(setting_row.get("setting_value", "1") if setting_row else "1").strip() == "1")

                # Render HTML page INSTANTLY (0 delay). All KPI cards populate asynchronously via jQuery.
                return render_template(
                    "dashboard.html",
                    active_group="dashboard",
                    active_page="dashboard",
                    page_title="Sales & Operations Dashboard",
                    logged_user=logged_user,
                    sales_with_gst=sales_with_gst,
                    my_month_payment=0.0, my_month_payment_cnt=0,
                    my_today_sale=0.0, my_today_sale_cnt=0,
                    my_t1_goal=100000, my_t1_pct=0,
                    team_month_payment=0.0, team_month_payment_cnt=0,
                    team_today_sale=0.0, team_today_sale_cnt=0,
                    team_t1_goal=1000000, team_t1_pct=0,
                    today_leads_fetched=0, today_actions_taken=0, today_call_time="00:00:00",
                    today_free_trials=0, today_followups=0,
                    t3_achieved=0, t3_goal=20, t3_pct=0,
                    t4_achieved=0, t4_goal=50, t4_pct=0,
                    my_today_sales_list=[], month_sales_list=[], today_sales_list=[],
                    today_trials_list=[], today_followups_list=[], team_members_list=[],
                    lead_status_counts=[], designation_stats=[], desig_top5_bar_charts=[],
                    monthly_trend_labels_json="[]", monthly_trend_data_json="[]",
                    lead_status_labels_json="[]", lead_status_data_json="[]",
                    desig_labels_json="[]", desig_sales_json="[]"
                )
        except Exception as e:
            return render_template(
                "dashboard.html",
                active_group="dashboard",
                active_page="dashboard",
                page_title="Dashboard",
                logged_user={},
                sales_with_gst=True,
                my_month_payment=0.0, my_month_payment_cnt=0,
                my_today_sale=0.0, my_today_sale_cnt=0,
                my_t1_goal=100000, my_t1_pct=0,
                team_month_payment=0.0, team_month_payment_cnt=0,
                team_today_sale=0.0, team_today_sale_cnt=0,
                team_t1_goal=1000000, team_t1_pct=0,
                today_leads_fetched=0, today_actions_taken=0, today_call_time="00:00:00",
                today_free_trials=0, today_followups=0,
                t3_achieved=0, t3_goal=20, t3_pct=0,
                t4_achieved=0, t4_goal=50, t4_pct=0,
                my_today_sales_list=[], month_sales_list=[], today_sales_list=[],
                today_trials_list=[], today_followups_list=[], team_members_list=[],
                lead_status_counts=[], designation_stats=[], desig_top5_bar_charts=[],
                monthly_trend_labels_json="[]", monthly_trend_data_json="[]",
                lead_status_labels_json="[]", lead_status_data_json="[]",
                desig_labels_json="[]", desig_sales_json="[]"
            )
        finally:
            connection.close()

    @app.route("/api/dashboard/kpi-summary", methods=["GET", "POST"])
    def api_dashboard_kpi_summary():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        connection = get_db_connection()
        if not connection:
            return jsonify({"success": False, "message": "Database connection error"}), 500

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT u.id, u.user_uuid, u.full_name, u.username, u.role_id, u.designation_id, u.target, r.role_name, d.designation_name
                    FROM users u
                    LEFT JOIN roles r ON r.id = u.role_id
                    LEFT JOIN designations d ON d.id = u.designation_id
                    WHERE u.user_uuid = %s LIMIT 1
                """, (logged_user_uuid,))
                logged_user = cursor.fetchone()
                if not logged_user:
                    return jsonify({"success": False, "message": "User not found"}), 404

                user_id = logged_user["id"]
                is_admin = (logged_user.get("role_name") or "").lower() in ["admin", "super admin", "superadmin"] or user_id in [1, 20]
                has_global_access = is_admin or has_permission("global_access_scope", "global_data_access")

                cursor.execute("SELECT setting_key, setting_value FROM system_settings WHERE setting_key = 'sales_display_with_gst' LIMIT 1")
                setting_row = cursor.fetchone()
                sales_with_gst = (str(setting_row.get("setting_value", "1") if setting_row else "1").strip() == "1")
                amount_col = "gross_amount" if sales_with_gst else "net_amount"

                if has_global_access:
                    cursor.execute("SELECT id FROM users WHERE status = 1")
                    team_user_ids = [r["id"] for r in cursor.fetchall()]
                else:
                    team_user_ids = get_user_team_ids(cursor, user_id)

                team_size = len(team_user_ids)
                team_ids_str = ",".join(map(str, team_user_ids)) if team_user_ids else "0"

                # 1. Personal Sales
                cursor.execute(f"""
                    SELECT COALESCE(SUM({amount_col}), 0) as total, COUNT(*) as cnt
                    FROM sales_orders
                    WHERE order_status = 'approved'
                    AND created_by_user_id = %s
                    AND MONTH(COALESCE(payment_date, created_at)) = MONTH(CURRENT_DATE())
                    AND YEAR(COALESCE(payment_date, created_at)) = YEAR(CURRENT_DATE())
                """, (user_id,))
                my_m_row = cursor.fetchone()
                my_month_payment = float(my_m_row["total"] or 0)

                cursor.execute(f"""
                    SELECT COALESCE(SUM({amount_col}), 0) as total, COUNT(*) as cnt
                    FROM sales_orders
                    WHERE order_status = 'approved'
                    AND created_by_user_id = %s
                    AND DATE(COALESCE(payment_date, created_at)) = CURRENT_DATE()
                """, (user_id,))
                my_t_row = cursor.fetchone()
                my_today_sale = float(my_t_row["total"] or 0)

                my_target = float(logged_user.get("target") or 0)
                my_t1_goal = int(my_target) if my_target > 0 else 100000
                my_t1_pct = round((my_month_payment / my_t1_goal) * 100, 1) if my_t1_goal > 0 else 0

                # 2. Team Sales
                if has_global_access:
                    cursor.execute(f"""
                        SELECT COALESCE(SUM({amount_col}), 0) as total, COUNT(*) as cnt
                        FROM sales_orders
                        WHERE order_status = 'approved'
                        AND MONTH(COALESCE(payment_date, created_at)) = MONTH(CURRENT_DATE())
                        AND YEAR(COALESCE(payment_date, created_at)) = YEAR(CURRENT_DATE())
                    """)
                else:
                    cursor.execute(f"""
                        SELECT COALESCE(SUM({amount_col}), 0) as total, COUNT(*) as cnt
                        FROM sales_orders
                        WHERE order_status = 'approved'
                        AND created_by_user_id IN ({team_ids_str})
                        AND MONTH(COALESCE(payment_date, created_at)) = MONTH(CURRENT_DATE())
                        AND YEAR(COALESCE(payment_date, created_at)) = YEAR(CURRENT_DATE())
                    """)
                team_m_row = cursor.fetchone()
                team_month_payment = float(team_m_row["total"] or 0)

                if has_global_access:
                    cursor.execute(f"""
                        SELECT COALESCE(SUM({amount_col}), 0) as total, COUNT(*) as cnt
                        FROM sales_orders
                        WHERE order_status = 'approved'
                        AND DATE(COALESCE(payment_date, created_at)) = CURRENT_DATE()
                    """)
                else:
                    cursor.execute(f"""
                        SELECT COALESCE(SUM({amount_col}), 0) as total, COUNT(*) as cnt
                        FROM sales_orders
                        WHERE order_status = 'approved'
                        AND created_by_user_id IN ({team_ids_str})
                        AND DATE(COALESCE(payment_date, created_at)) = CURRENT_DATE()
                    """)
                team_t_row = cursor.fetchone()
                team_today_sale = float(team_t_row["total"] or 0)

                cursor.execute(f"SELECT COALESCE(SUM(target), 0) as total_target FROM users WHERE id IN ({team_ids_str}) AND status = 1")
                team_target_sum = float(cursor.fetchone()["total_target"] or 0)
                team_t1_goal = int(team_target_sum) if team_target_sum > 0 else 1000000
                team_t1_pct = round((team_month_payment / team_t1_goal) * 100, 1) if team_t1_goal > 0 else 0

                # 3. Activity Counts
                if has_global_access:
                    cursor.execute("SELECT COUNT(*) as cnt FROM leads WHERE DATE(created_at) = CURRENT_DATE()")
                else:
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM leads WHERE DATE(created_at) = CURRENT_DATE() AND (current_owner_user_id IN ({team_ids_str}) OR created_by IN ({team_ids_str}))")
                today_leads_fetched = cursor.fetchone()["cnt"] or 0

                if has_global_access:
                    cursor.execute("SELECT COUNT(*) as cnt FROM leads WHERE DATE(updated_at) = CURRENT_DATE()")
                else:
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM leads WHERE DATE(updated_at) = CURRENT_DATE() AND (current_owner_user_id IN ({team_ids_str}) OR created_by IN ({team_ids_str}))")
                today_actions_taken = cursor.fetchone()["cnt"] or 0

                # 4. Calling Talktime
                today_call_time = "00:00:00"
                try:
                    from utils.calling_db import get_call_summary_report
                    call_rep = get_call_summary_report(date_preset="today")
                    today_call_time = call_rep.get("kpis", {}).get("total_talktime_fmt", "00:00:00")
                except Exception as e:
                    pass

                # 5. Dynamic Designation-Wise Top 5 Sales Charts from system_settings (dashboard_chart_designations)
                cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'dashboard_chart_designations' LIMIT 1")
                desig_setting_row = cursor.fetchone()
                raw_desig_setting = str(desig_setting_row.get("setting_value", "") if desig_setting_row else "").strip()

                configured_desig_items = [x.strip() for x in raw_desig_setting.split(",") if x.strip()]
                if not configured_desig_items:
                    cursor.execute("SELECT id, designation_name FROM designations LIMIT 4")
                    configured_desig_items = [str(r["id"]) for r in cursor.fetchall()]

                desig_charts_list = []
                for item in configured_desig_items:
                    d_row = None
                    if str(item).isdigit():
                        cursor.execute("SELECT id, designation_name FROM designations WHERE id = %s LIMIT 1", (int(item),))
                        d_row = cursor.fetchone()
                    if not d_row:
                        cursor.execute("SELECT id, designation_name FROM designations WHERE designation_name = %s LIMIT 1", (item,))
                        d_row = cursor.fetchone()

                    if d_row:
                        d_id = d_row["id"]
                        d_name = d_row["designation_name"]

                        cursor.execute(f"""
                            SELECT u.id, u.full_name, u.username,
                                   COALESCE(SUM(so.{amount_col}), 0) as total_sales
                            FROM users u
                            LEFT JOIN sales_orders so ON so.created_by_user_id = u.id 
                                                      AND so.order_status = 'approved'
                                                      AND MONTH(COALESCE(so.payment_date, so.created_at)) = MONTH(CURRENT_DATE())
                                                      AND YEAR(COALESCE(so.payment_date, so.created_at)) = YEAR(CURRENT_DATE())
                            WHERE u.designation_id = %s AND u.status = 1
                            GROUP BY u.id, u.full_name, u.username
                            ORDER BY total_sales DESC, u.full_name ASC
                            LIMIT 5
                        """, (d_id,))
                        top_users = cursor.fetchall()

                        user_names = [u["full_name"] or u["username"] for u in top_users]
                        user_sales = [float(u["total_sales"] or 0) for u in top_users]

                        desig_charts_list.append({
                            "chart_id": f"chart_desig_{d_id}",
                            "designation_name": d_name,
                            "user_names": user_names,
                            "user_sales": user_sales
                        })

                return jsonify({
                    "success": True,
                    "my_today_sale": my_today_sale,
                    "my_today_sale_fmt": f"{my_today_sale:,.2f}",
                    "my_month_payment": my_month_payment,
                    "my_month_payment_fmt": f"{my_month_payment:,.2f}",
                    "my_t1_goal": my_t1_goal,
                    "my_t1_goal_fmt": f"{my_t1_goal:,.2f}",
                    "my_t1_pct": my_t1_pct,

                    "team_today_sale": team_today_sale,
                    "team_today_sale_fmt": f"{team_today_sale:,.2f}",
                    "team_month_payment": team_month_payment,
                    "team_month_payment_fmt": f"{team_month_payment:,.2f}",
                    "team_t1_goal": team_t1_goal,
                    "team_t1_goal_fmt": f"{team_t1_goal:,.2f}",
                    "team_t1_pct": team_t1_pct,

                    "today_leads_fetched": today_leads_fetched,
                    "today_actions_taken": today_actions_taken,
                    "today_call_time": today_call_time,

                    "charts": {
                        "designation_charts": desig_charts_list
                    }
                })
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            connection.close()

    @app.route("/api/dashboard/modal-orders", methods=["GET", "POST"])
    def api_dashboard_modal_orders():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        order_type = request.values.get("type", "my_today")
        page = int(request.values.get("page", 1))
        page_size = int(request.values.get("page_size", 10))
        search_q = request.values.get("search", "").strip()

        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection error"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, is_admin FROM users WHERE user_uuid = %s LIMIT 1", (logged_user_uuid,))
                u_row = cursor.fetchone() or {}
                user_id = u_row.get("id")
                is_admin = int(u_row.get("is_admin") or 0) == 1
                has_global_access = is_admin or has_permission("global_access_scope", "global_data_access")

                cursor.execute("SELECT setting_key, setting_value FROM system_settings WHERE setting_key = 'sales_display_with_gst' LIMIT 1")
                setting_row = cursor.fetchone()
                sales_with_gst = (str(setting_row.get("setting_value", "1") if setting_row else "1").strip() == "1")
                amount_col = "gross_amount" if sales_with_gst else "net_amount"

                if has_global_access:
                    cursor.execute("SELECT id FROM users WHERE status = 1")
                    team_user_ids = [r["id"] for r in cursor.fetchall()]
                else:
                    team_user_ids = get_user_team_ids(cursor, user_id)

                team_ids_str = ",".join(map(str, team_user_ids)) if team_user_ids else "0"

                where_clauses = ["so.order_status = 'approved'"]
                params = []

                if order_type == "my_today":
                    where_clauses.append("so.created_by_user_id = %s")
                    params.append(user_id)
                    where_clauses.append("DATE(COALESCE(so.payment_date, so.created_at)) = CURRENT_DATE()")
                elif order_type == "my_month":
                    where_clauses.append("so.created_by_user_id = %s")
                    params.append(user_id)
                    where_clauses.append("MONTH(COALESCE(so.payment_date, so.created_at)) = MONTH(CURRENT_DATE())")
                    where_clauses.append("YEAR(COALESCE(so.payment_date, so.created_at)) = YEAR(CURRENT_DATE())")
                elif order_type == "team_today":
                    if not has_global_access:
                        where_clauses.append(f"so.created_by_user_id IN ({team_ids_str})")
                    where_clauses.append("DATE(COALESCE(so.payment_date, so.created_at)) = CURRENT_DATE()")
                elif order_type == "team_month":
                    if not has_global_access:
                        where_clauses.append(f"so.created_by_user_id IN ({team_ids_str})")
                    where_clauses.append("MONTH(COALESCE(so.payment_date, so.created_at)) = MONTH(CURRENT_DATE())")
                    where_clauses.append("YEAR(COALESCE(so.payment_date, so.created_at)) = YEAR(CURRENT_DATE())")

                if search_q:
                    where_clauses.append("(so.product_name LIKE %s OR so.plan_name LIKE %s OR so.order_number LIKE %s OR u.full_name LIKE %s)")
                    s_param = f"%{search_q}%"
                    params.extend([s_param, s_param, s_param, s_param])

                where_sql = " AND ".join(where_clauses)

                count_sql = f"SELECT COUNT(*) as total FROM sales_orders so LEFT JOIN users u ON u.id = so.created_by_user_id WHERE {where_sql}"
                cursor.execute(count_sql, params)
                total_records = cursor.fetchone()["total"] or 0

                total_pages = max(1, (total_records + page_size - 1) // page_size)
                page = max(1, min(page, total_pages))
                offset = (page - 1) * page_size

                data_sql = f"""
                    SELECT so.id, so.order_number, 
                           COALESCE(NULLIF(so.invoice_name, ''), l.name, 'N/A') as client_name,
                           COALESCE(CONCAT('LD-', l.id), so.order_number) as lead_code,
                           so.product_name, so.plan_name,
                           COALESCE(so.service_start_date, DATE(so.created_at)) as start_date_val,
                           COALESCE(so.service_expiry_date, DATE_ADD(DATE(so.created_at), INTERVAL 1 YEAR)) as end_date_val,
                           COALESCE(so.payment_date, DATE(so.created_at)) as invoice_date_val,
                           so.{amount_col} as amount, u.full_name as created_by_name
                    FROM sales_orders so
                    LEFT JOIN leads l ON l.id = so.lead_id
                    LEFT JOIN users u ON u.id = so.created_by_user_id
                    WHERE {where_sql}
                    ORDER BY so.created_at DESC
                    LIMIT %s OFFSET %s
                """
                data_params = list(params) + [page_size, offset]
                cursor.execute(data_sql, data_params)
                rows = cursor.fetchall()

                items = []
                for r in rows:
                    amt = float(r["amount"] or 0)
                    s_date = str(r["start_date_val"] or "N/A")
                    e_date = str(r["end_date_val"] or "N/A")
                    inv_date = str(r["invoice_date_val"] or "N/A")
                    items.append({
                        "id": r["id"],
                        "lead_code": r["lead_code"] or "N/A",
                        "client_name": r["client_name"] or "N/A",
                        "product_name": r["product_name"] or "N/A",
                        "plan_name": r["plan_name"] or "N/A",
                        "start_date": s_date,
                        "end_date": e_date,
                        "invoice_date": inv_date,
                        "amount_fmt": f"{amt:,.2f}",
                        "created_by": r["created_by_name"] or "System"
                    })

                return jsonify({
                    "success": True,
                    "items": items,
                    "total_records": total_records,
                    "total_pages": total_pages,
                    "current_page": page,
                    "page_size": page_size,
                    "order_type": order_type
                })
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

    @app.route("/api/dashboard/activity-breakdown", methods=["GET", "POST"])
    def api_dashboard_activity_breakdown():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        page = int(request.values.get("page", 1))
        page_size = int(request.values.get("page_size", 10))
        search_q = request.values.get("search", "").strip()

        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection error"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, is_admin FROM users WHERE user_uuid = %s LIMIT 1", (logged_user_uuid,))
                u_row = cursor.fetchone() or {}
                user_id = u_row.get("id")
                is_admin = int(u_row.get("is_admin") or 0) == 1
                has_global_access = is_admin or has_permission("global_access_scope", "global_data_access")

                if has_global_access:
                    cursor.execute("SELECT id FROM users WHERE status = 1")
                    team_user_ids = [r["id"] for r in cursor.fetchall()]
                else:
                    team_user_ids = get_user_team_ids(cursor, user_id)

                team_ids_str = ",".join(map(str, team_user_ids)) if team_user_ids else "0"

                where_clauses = [f"u.id IN ({team_ids_str})", "u.status = 1"]
                params = []

                if search_q:
                    where_clauses.append("(u.full_name LIKE %s OR u.username LIKE %s)")
                    s_param = f"%{search_q}%"
                    params.extend([s_param, s_param])

                where_sql = " AND ".join(where_clauses)

                count_sql = f"SELECT COUNT(*) as total FROM users u WHERE {where_sql}"
                cursor.execute(count_sql, params)
                total_records = cursor.fetchone()["total"] or 0

                total_pages = max(1, (total_records + page_size - 1) // page_size)
                page = max(1, min(page, total_pages))
                offset = (page - 1) * page_size

                query_sql = f"""
                    SELECT u.id, u.full_name, u.username, d.designation_name,
                           (SELECT COUNT(*) FROM leads WHERE DATE(created_at) = CURRENT_DATE() AND (current_owner_user_id = u.id OR created_by = u.id)) as fetched_cnt,
                           (SELECT COUNT(*) FROM leads WHERE DATE(updated_at) = CURRENT_DATE() AND (current_owner_user_id = u.id OR created_by = u.id)) as action_cnt,
                           (SELECT COUNT(*) FROM lead_call_history WHERE DATE(called_at) = CURRENT_DATE() AND user_id = u.id) as total_calls,
                           (SELECT COUNT(*) FROM lead_call_history WHERE DATE(called_at) = CURRENT_DATE() AND user_id = u.id AND (call_status = 'ANSWERED' OR duration > 0)) as answered_calls,
                           (SELECT COALESCE(SUM(duration), 0) FROM lead_call_history WHERE DATE(called_at) = CURRENT_DATE() AND user_id = u.id) as talktime_sec
                    FROM users u
                    LEFT JOIN designations d ON d.id = u.designation_id
                    WHERE {where_sql}
                    ORDER BY action_cnt DESC, total_calls DESC, u.full_name ASC
                    LIMIT %s OFFSET %s
                """
                query_params = list(params) + [page_size, offset]
                cursor.execute(query_sql, query_params)
                rows = cursor.fetchall()

                items = []
                for r in rows:
                    sec = int(r["talktime_sec"] or 0)
                    hrs = sec // 3600
                    mins = (sec % 3600) // 60
                    secs = sec % 60
                    talk_fmt = f"{hrs:02d}:{mins:02d}:{secs:02d}"

                    items.append({
                        "user_name": r["full_name"] or r["username"],
                        "designation": r["designation_name"] or "N/A",
                        "fetched_cnt": r["fetched_cnt"] or 0,
                        "action_cnt": r["action_cnt"] or 0,
                        "total_calls": r["total_calls"] or 0,
                        "answered_calls": r["answered_calls"] or 0,
                        "talktime_fmt": talk_fmt
                    })

                return jsonify({
                    "success": True,
                    "items": items,
                    "total_records": total_records,
                    "total_pages": total_pages,
                    "current_page": page,
                    "page_size": page_size
                })
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()
