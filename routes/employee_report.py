import calendar
from datetime import datetime, date, timedelta
from functools import wraps
from flask import render_template, session, jsonify, request, flash, redirect, url_for

from config import get_db_connection
from utils.permissions import has_permission


def require_employee_report_permission(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_info = session.get("user", {})
        role_name = str(user_info.get("role_name") or "").lower()
        is_admin = (
            user_info.get("is_admin") == 1
            or role_name in ["admin", "super admin", "superadmin"]
            or user_info.get("id") in [1, 20]
        )
        if is_admin:
            return f(*args, **kwargs)

        if not (
            has_permission("reports", "employee_report")
            or has_permission("reports", "view")
            or has_permission("reports", "user_report")
        ):
            if request.path.startswith("/api/") or request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "message": "Access Denied: You do not have permission for Employee Report."}), 403
            flash("Access Denied: You do not have permission to access Employee Report.", "danger")
            return redirect(url_for("dashboard"))

        return f(*args, **kwargs)
    return decorated_function


def get_employee_report_summary_and_users(conn):
    with conn.cursor() as cursor:
        # Get all users
        cursor.execute("""
            SELECT 
                u.id AS user_id,
                u.user_uuid,
                u.full_name,
                u.username,
                COALESCE(u.mobile, '') AS mobile,
                COALESCE(u.status, 1) AS status,
                COALESCE(d.designation_name, r.role_name, 'Staff Member') AS designation_name,
                COALESCE(r.role_name, 'Staff Member') AS role_name,
                DATE_FORMAT(u.created_at, '%%d %%b %%Y') AS member_since
            FROM users u
            LEFT JOIN roles r ON r.id = u.role_id
            LEFT JOIN designations d ON d.id = u.designation_id
            ORDER BY u.status DESC, u.full_name ASC
        """)
        users = cursor.fetchall() or []

        # Today's activity aggregation per user
        cursor.execute("""
            SELECT 
                ua.user_id,
                MIN(CASE WHEN LOWER(ua.action_type) = 'user login' THEN ua.created_at ELSE NULL END) AS first_login_today,
                MIN(ua.created_at) AS first_act_today,
                MAX(ua.created_at) AS last_act_today,
                COUNT(*) AS total_activities_today,
                SUBSTRING_INDEX(GROUP_CONCAT(COALESCE(ua.ip_address, '') ORDER BY ua.created_at DESC SEPARATOR ','), ',', 1) AS last_ip
            FROM user_activities ua
            WHERE DATE(ua.created_at) = CURDATE()
            GROUP BY ua.user_id
        """)
        today_stats_rows = cursor.fetchall() or []
        today_stats = {r["user_id"]: r for r in today_stats_rows}

        # Current month attendance days per user
        now = datetime.now()
        cursor.execute("""
            SELECT 
                ua.user_id,
                COUNT(DISTINCT DATE(ua.created_at)) AS present_days_month
            FROM user_activities ua
            WHERE YEAR(ua.created_at) = %s AND MONTH(ua.created_at) = %s
            GROUP BY ua.user_id
        """, (now.year, now.month))
        month_stats_rows = cursor.fetchall() or []
        month_stats = {r["user_id"]: r["present_days_month"] for r in month_stats_rows}

        # Activity date ranges (earliest entry to latest entry) per user
        cursor.execute("""
            SELECT 
                ua.user_id,
                MIN(ua.created_at) AS min_date,
                MAX(ua.created_at) AS max_date
            FROM user_activities ua
            WHERE ua.created_at IS NOT NULL
            GROUP BY ua.user_id
        """)
        user_range_rows = cursor.fetchall() or []
        user_ranges = {r["user_id"]: r for r in user_range_rows}

        # Distinct active months per user
        cursor.execute("""
            SELECT DISTINCT
                ua.user_id,
                DATE_FORMAT(ua.created_at, '%%Y-%%m') AS ym
            FROM user_activities ua
            WHERE ua.created_at IS NOT NULL
        """)
        active_ym_rows = cursor.fetchall() or []
        user_active_yms = {}
        for r in active_ym_rows:
            uid = r["user_id"]
            if uid not in user_active_yms:
                user_active_yms[uid] = set()
            user_active_yms[uid].add(r["ym"])

        total_present_today = 0
        result_users = []
        distinct_roles = sorted(list(set(u["role_name"] for u in users if u.get("role_name"))))

        for u in users:
            uid = u["user_id"]
            t_stat = today_stats.get(uid, {})
            first_login = t_stat.get("first_login_today") or t_stat.get("first_act_today")
            total_act = int(t_stat.get("total_activities_today") or 0)
            last_ip = t_stat.get("last_ip") or ""

            in_time_fmt = None
            is_logged_in = False
            is_late = False

            if first_login:
                is_logged_in = True
                total_present_today += 1
                in_time_fmt = first_login.strftime("%I:%M %p")
                if first_login.hour > 10 or (first_login.hour == 10 and first_login.minute > 15):
                    is_late = True

            u_name = u.get("full_name") or u.get("username") or f"User #{uid}"
            parts = [p for p in u_name.strip().split() if p]
            if len(parts) >= 2:
                initials = (parts[0][0] + parts[1][0]).upper()
            elif len(parts) == 1 and len(parts[0]) >= 2:
                initials = parts[0][:2].upper()
            elif len(parts) == 1:
                initials = parts[0][0].upper()
            else:
                initials = "EM"

            # Build list of months from earliest entry to latest entry
            range_info = user_ranges.get(uid)
            user_months = []
            if range_info and range_info.get("min_date") and range_info.get("max_date"):
                min_d = range_info["min_date"]
                max_d = range_info["max_date"]
                active_set = user_active_yms.get(uid, set())

                start_y = min_d.year
                start_m = min_d.month
                end_y = max_d.year
                end_m = max_d.month

                curr_y, curr_m = start_y, start_m
                while (curr_y < end_y) or (curr_y == end_y and curr_m <= end_m):
                    ym_key = f"{curr_y:04d}-{curr_m:02d}"
                    m_date = date(curr_y, curr_m, 1)
                    user_months.append({
                        "year": curr_y,
                        "month": curr_m,
                        "label": m_date.strftime("%b-%y"),  # e.g. Jun-25, Dec-25
                        "full_label": m_date.strftime("%B %Y"),
                        "has_activity": ym_key in active_set,
                        "is_current": (curr_y == now.year and curr_m == now.month)
                    })
                    if curr_m == 12:
                        curr_y += 1
                        curr_m = 1
                    else:
                        curr_m += 1

            result_users.append({
                "user_id": uid,
                "user_uuid": u.get("user_uuid") or "",
                "full_name": u_name,
                "initials": initials,
                "username": u.get("username") or "",
                "mobile": u.get("mobile") or "",
                "designation": u.get("designation_name") or u.get("role_name") or "Staff Member",
                "role_name": u.get("role_name") or "Staff Member",
                "status": int(u["status"]) if u.get("status") is not None else 1,
                "member_since": u.get("member_since") or "",
                "is_logged_in": is_logged_in,
                "in_time": in_time_fmt,
                "is_late": is_late,
                "today_activity_count": total_act,
                "last_ip": last_ip,
                "present_days_month": month_stats.get(uid, 0),
                "months": user_months,
            })

        total_employees = len(result_users)
        total_active = sum(1 for u in result_users if u.get("status") == 1)
        total_inactive = total_employees - total_active
        total_absent_today = max(0, total_employees - total_present_today)
        summary = {
            "total_employees": total_employees,
            "total_active": total_active,
            "total_inactive": total_inactive,
            "total_present_today": total_present_today,
            "total_absent_today": total_absent_today,
            "attendance_pct_today": round((total_present_today / total_employees * 100), 1) if total_employees > 0 else 0,
        }

        distinct_designations = sorted(list(set(u["designation"] for u in result_users if u.get("designation"))))

        return result_users, summary, distinct_designations


def employee_report_routes(app):

    # 1. Main Page Route
    @app.route("/reports/employees", endpoint="employee_report")
    @app.route("/reports/employee-report", endpoint="employee_report_alias")
    @require_employee_report_permission
    def employee_report():
        now = datetime.now()
        return render_template(
            "reports/employee_report.html",
            today_str=now.strftime("%d %b %Y"),
            current_year=now.year,
            current_month=now.month,
            current_month_name=now.strftime("%B %Y"),
            active_group="reports",
            active_page="employee_report",
            page_title="Employee Report",
        )

    # 2. API: Fetch All Users / Employees with Today's Login and Activity
    @app.route("/api/reports/employee-report/users")
    @require_employee_report_permission
    def api_employee_report_users():
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        try:
            users_list, summary, distinct_designations = get_employee_report_summary_and_users(conn)
            return jsonify({
                "success": True,
                "users": users_list,
                "summary": summary,
                "designations": distinct_designations
            })
        except Exception as e:
            print("Error in api_employee_report_users:", e)
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

    # 3. API: Fetch Monthly Attendance & Office Arrival for a Selected Employee
    @app.route("/api/reports/employee-report/monthly-attendance")
    @require_employee_report_permission
    def api_employee_monthly_attendance():
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"success": False, "message": "user_id is required."}), 400

        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({"success": False, "message": "Invalid user_id."}), 400

        now = datetime.now()
        year = int(request.args.get("year") or now.year)
        month = int(request.args.get("month") or now.month)

        if month < 1 or month > 12:
            month = now.month

        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        try:
            with conn.cursor() as cursor:
                # Get employee info
                cursor.execute("""
                    SELECT 
                        u.id AS user_id, 
                        u.full_name, 
                        u.username, 
                        COALESCE(u.mobile, '') AS mobile, 
                        COALESCE(r.role_name, 'Staff Member') AS role_name
                    FROM users u
                    LEFT JOIN roles r ON r.id = u.role_id
                    WHERE u.id = %s
                    LIMIT 1
                """, (user_id,))
                user_row = cursor.fetchone()
                if not user_row:
                    return jsonify({"success": False, "message": "Employee not found."}), 404

                # Fetch all activity records for this user in the specified month
                cursor.execute("""
                    SELECT 
                        DATE(ua.created_at) AS act_date,
                        MIN(CASE WHEN LOWER(ua.action_type) = 'user login' THEN ua.created_at ELSE NULL END) AS first_login,
                        MIN(ua.created_at) AS first_act,
                        MAX(ua.created_at) AS last_act,
                        COUNT(*) AS act_count
                    FROM user_activities ua
                    WHERE ua.user_id = %s
                      AND YEAR(ua.created_at) = %s
                      AND MONTH(ua.created_at) = %s
                    GROUP BY DATE(ua.created_at)
                """, (user_id, year, month))
                act_rows = cursor.fetchall() or []
                act_map = {r["act_date"]: r for r in act_rows}

                # Days in month
                num_days = calendar.monthrange(year, month)[1]
                month_name = calendar.month_name[month]

                days_data = []
                today_date = date.today()

                total_sundays = 0
                present_days = 0
                absent_days = 0
                late_days = 0
                working_days_total = 0
                working_days_elapsed = 0

                arrival_minutes_list = []

                for d in range(1, num_days + 1):
                    cur_date = date(year, month, d)
                    weekday_num = cur_date.weekday() # 0 = Monday, 6 = Sunday
                    weekday_short = cur_date.strftime("%a")
                    is_sunday = (weekday_num == 6)
                    is_future = (cur_date > today_date)
                    is_today = (cur_date == today_date)

                    act_info = act_map.get(cur_date)

                    first_login = None
                    last_act = None
                    act_count = 0

                    if act_info:
                        first_login = act_info.get("first_login") or act_info.get("first_act")
                        last_act = act_info.get("last_act")
                        act_count = int(act_info.get("act_count") or 0)

                    in_time_fmt = first_login.strftime("%I:%M %p") if first_login else None
                    out_time_fmt = last_act.strftime("%I:%M %p") if last_act else None

                    is_late = False
                    if first_login:
                        if first_login.hour > 10 or (first_login.hour == 10 and first_login.minute > 15):
                            is_late = True
                        arrival_minutes_list.append(first_login.hour * 60 + first_login.minute)

                    status = "Upcoming"
                    if is_sunday:
                        total_sundays += 1
                        if first_login or act_count > 0:
                            status = "Sunday (Worked)"
                        else:
                            status = "Sunday (Off)"
                    else:
                        working_days_total += 1
                        if not is_future:
                            working_days_elapsed += 1
                            if first_login or act_count > 0:
                                status = "Present"
                                present_days += 1
                                if is_late:
                                    late_days += 1
                            else:
                                status = "Absent"
                                absent_days += 1

                    days_data.append({
                        "day": d,
                        "date": cur_date.strftime("%Y-%m-%d"),
                        "date_display": cur_date.strftime("%d %b"),
                        "weekday": weekday_short,
                        "is_sunday": is_sunday,
                        "is_future": is_future,
                        "is_today": is_today,
                        "in_time": in_time_fmt,
                        "out_time": out_time_fmt,
                        "is_late": is_late,
                        "activity_count": act_count,
                        "status": status,
                    })

                # Calculate average in-time
                avg_in_time_str = "N/A"
                if arrival_minutes_list:
                    avg_minutes = int(sum(arrival_minutes_list) / len(arrival_minutes_list))
                    avg_hour = avg_minutes // 60
                    avg_min = avg_minutes % 60
                    dummy_dt = datetime(2026, 1, 1, avg_hour, avg_min)
                    avg_in_time_str = dummy_dt.strftime("%I:%M %p")

                attendance_rate = 0.0
                if working_days_elapsed > 0:
                    attendance_rate = round((present_days / working_days_elapsed) * 100, 1)

                return jsonify({
                    "success": True,
                    "user": {
                        "user_id": user_row["user_id"],
                        "full_name": user_row["full_name"] or user_row["username"],
                        "username": user_row["username"],
                        "role_name": user_row["role_name"],
                    },
                    "period": {
                        "year": year,
                        "month": month,
                        "month_name": month_name,
                        "label": f"{month_name} {year}",
                    },
                    "days": days_data,
                    "summary": {
                        "total_days": num_days,
                        "working_days_total": working_days_total,
                        "working_days_elapsed": working_days_elapsed,
                        "present_days": present_days,
                        "absent_days": absent_days,
                        "on_time_days": max(0, present_days - late_days),
                        "total_sundays": total_sundays,
                        "late_days": late_days,
                        "avg_in_time": avg_in_time_str,
                        "attendance_rate": attendance_rate,
                    },
                    "stats": {
                        "work_days": working_days_total,
                        "present_days": present_days,
                        "absent_days": absent_days,
                        "on_time_days": max(0, present_days - late_days),
                        "total_sundays": total_sundays,
                        "late_days": late_days,
                        "avg_in_time": avg_in_time_str,
                    }
                })
        except Exception as e:
            print("Error in api_employee_monthly_attendance:", e)
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

    # 4. API: Fetch Detailed Full Day Activities for an Employee with Filters
    @app.route("/api/reports/employee-report/activities")
    @require_employee_report_permission
    def api_employee_activities():
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"success": False, "message": "user_id is required."}), 400

        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({"success": False, "message": "Invalid user_id."}), 400

        target_date = (request.args.get("date") or "").strip()
        action_type = (request.args.get("action_type") or "all").strip()
        search_query = (request.args.get("search") or "").strip()

        page = max(1, int(request.args.get("page") or 1))
        per_page = min(100, max(10, int(request.args.get("per_page") or 50)))
        offset = (page - 1) * per_page

        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed."}), 500

        try:
            with conn.cursor() as cursor:
                # Verify user exists
                cursor.execute("SELECT id, full_name, username FROM users WHERE id = %s LIMIT 1", (user_id,))
                user_row = cursor.fetchone()
                if not user_row:
                    return jsonify({"success": False, "message": "Employee not found."}), 404

                where_clauses = ["ua.user_id = %s"]
                params = [user_id]

                if target_date:
                    where_clauses.append("DATE(ua.created_at) = %s")
                    params.append(target_date)

                if action_type and action_type != "all":
                    where_clauses.append("ua.action_type = %s")
                    params.append(action_type)

                if search_query:
                    where_clauses.append("(ua.description LIKE %s OR ua.ip_address LIKE %s OR ua.action_type LIKE %s)")
                    like_val = f"%{search_query}%"
                    params.extend([like_val, like_val, like_val])

                where_sql = " AND ".join(where_clauses)

                # Total count
                cursor.execute(f"SELECT COUNT(*) AS total FROM user_activities ua WHERE {where_sql}", params)
                total_count = int((cursor.fetchone() or {}).get("total") or 0)

                # Fetch activities
                cursor.execute(f"""
                    SELECT 
                        ua.id,
                        ua.user_activity_uuid,
                        ua.user_id,
                        ua.lead_id,
                        ua.action_type,
                        ua.description,
                        COALESCE(ua.ip_address, 'N/A') AS ip_address,
                        ua.created_at,
                        DATE_FORMAT(ua.created_at, '%%h:%%i:%%s %%p') AS time_fmt,
                        DATE_FORMAT(ua.created_at, '%%d %%b %%Y') AS date_fmt,
                        l.client_code,
                        l.lead_name
                    FROM user_activities ua
                    LEFT JOIN leads l ON l.id = ua.lead_id
                    WHERE {where_sql}
                    ORDER BY ua.created_at DESC
                    LIMIT %s OFFSET %s
                """, params + [per_page, offset])
                activities = cursor.fetchall() or []

                return jsonify({
                    "success": True,
                    "user": {
                        "user_id": user_row["id"],
                        "full_name": user_row["full_name"] or user_row["username"],
                        "username": user_row["username"],
                    },
                    "activities": activities,
                    "pagination": {
                        "total": total_count,
                        "page": page,
                        "per_page": per_page,
                        "total_pages": (total_count + per_page - 1) // per_page if total_count > 0 else 1,
                    }
                })
        except Exception as e:
            print("Error in api_employee_activities:", e)
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

    # 5. API: Fetch Distinct Action Types for Filters
    @app.route("/api/reports/employee-report/action-types")
    @require_employee_report_permission
    def api_employee_action_types():
        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "types": []}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT action_type 
                    FROM user_activities 
                    WHERE action_type IS NOT NULL AND action_type != ''
                    ORDER BY action_type ASC
                """)
                rows = cursor.fetchall() or []
                types = [r["action_type"] for r in rows if r.get("action_type")]
                return jsonify({"success": True, "types": types})
        except Exception as e:
            print("Error in api_employee_action_types:", e)
            return jsonify({"success": False, "types": []}), 500
        finally:
            conn.close()
