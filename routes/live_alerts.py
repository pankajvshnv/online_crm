import os
import sys
import datetime
from datetime import date
import re
from flask import jsonify, session, request

from config import get_db_connection
from utils.permissions import update_user_last_active, has_permission
from routes.settings_helpers import fetch_owner_filter_options


def fetch_sidebar_live_counts(cursor, logged_user_uuid, user_id):
    today_followups = 0
    today_free_trials = 0
    unread_emails = 0
    unread_chat = 0
    recent_research = 0

    if not logged_user_uuid or not cursor:
        return today_followups, today_free_trials, unread_emails, unread_chat, recent_research

    try:
        user_info = session.get("user") or {}
        is_admin = bool(user_info.get("is_admin")) or str(user_info.get("role_name", "")).lower() == "admin"
        has_global_permission = has_permission('global_access_scope', 'global_data_access')
        
        is_global = is_admin or has_global_permission

        allowed_ids = None
        if not is_global:
            owner_context = fetch_owner_filter_options(cursor, logged_user_uuid)
            allowed_ids = owner_context.get("allowed_user_ids")

        # 1. Today Followups Count (Leads whose latest follow-up for TODAY is pending)
        owner_filter_sql = ""
        params_f = []
        if allowed_ids:
            ph = ", ".join(["%s"] * len(allowed_ids))
            owner_filter_sql = f" AND (l.current_owner_user_id IN ({ph}) OR l.created_by IN ({ph}))"
            params_f.extend(allowed_ids)
            params_f.extend(allowed_ids)

        sql_f = f"""
            SELECT COUNT(*) AS cnt
            FROM (
                SELECT f.lead_id
                FROM followups f
                INNER JOIN (
                    SELECT lead_id, MAX(id) AS max_id
                    FROM followups
                    WHERE DATE(followup_date) = CURRENT_DATE()
                    GROUP BY lead_id
                ) latest_today ON f.id = latest_today.max_id
                JOIN leads l ON l.id = f.lead_id
                WHERE LOWER(COALESCE(f.followup_status, 'pending')) != 'completed'
                {owner_filter_sql}
            ) active_today_leads
        """
        cursor.execute(sql_f, params_f)
        f_row = cursor.fetchone()
        if f_row:
            today_followups = f_row["cnt"]

        # 2. Today Free Trials Count (DATE(ft.start_date) = CURRENT_DATE())
        sql_ft = """
            SELECT COUNT(DISTINCT ft.id) AS cnt
            FROM free_trials ft
            JOIN leads l ON l.id = ft.lead_id
            WHERE DATE(ft.start_date) = CURRENT_DATE()
        """
        params_ft = []
        if allowed_ids:
            ph = ", ".join(["%s"] * len(allowed_ids))
            sql_ft += f" AND (l.current_owner_user_id IN ({ph}) OR l.created_by IN ({ph}))"
            params_ft.extend(allowed_ids)
            params_ft.extend(allowed_ids)
        cursor.execute(sql_ft, params_ft)
        ft_row = cursor.fetchone()
        if ft_row:
            today_free_trials = ft_row["cnt"]

        # 3. Unread Emails Count (for current user only)
        try:
            cursor.execute("""
                SELECT COUNT(*) AS cnt
                FROM emails
                WHERE folder = 'inbox' AND is_read = 0 AND is_deleted = 0 AND (user_id = %s OR user_id IS NULL)
            """, (user_id,))
            em_row = cursor.fetchone()
            if em_row:
                unread_emails = int(em_row["cnt"] or 0)
        except Exception:
            unread_emails = 0

        # 4. Unread Chat Messages Count (for current user only)
        try:
            cursor.execute("""
                SELECT COUNT(*) AS cnt
                FROM chat_messages
                WHERE receiver_user_id = %s AND is_read = 0
            """, (user_id,))
            chat_row = cursor.fetchone()
            if chat_row:
                unread_chat = int(chat_row["cnt"] or 0)
        except Exception:
            unread_chat = 0

        # 5. Recent Research Recommendations Count (Within last 1 minute)
        try:
            cursor.execute("""
                SELECT COUNT(*) AS cnt 
                FROM recommendation 
                WHERE recommendation_time >= DATE_SUB(NOW(), INTERVAL 1 MINUTE)
            """)
            r_cnt_row = cursor.fetchone()
            if r_cnt_row:
                recent_research = int(r_cnt_row["cnt"] or 0)
        except Exception:
            recent_research = 0

    except Exception as e:
        print("Error fetching sidebar counts:", e)

    return today_followups, today_free_trials, unread_emails, unread_chat, recent_research


def live_alerts_routes(app):

    @app.route("/api/presence/ping", methods=["POST", "GET"])
    def presence_ping():
        user_uuid = session.get("user_uuid")
        if user_uuid:
            update_user_last_active()
            return jsonify({"success": True, "message": "Presence updated"}), 200
        return jsonify({"success": False, "message": "Unauthenticated"}), 401

    @app.route("/api/sidebar/live-stats", methods=["GET"])
    def sidebar_live_stats():
        user_info = session.get("user") or {}
        user_id = user_info.get("id")
        user_uuid = session.get("user_uuid")
        if not user_id or not user_uuid:
            return jsonify({"success": False}), 401

        update_user_last_active(user_id)

        today_followups = 0
        today_free_trials = 0
        unread_emails = 0
        unread_chat = 0
        max_research_id = 0
        today_research_count = 0
        live_status = "online"
        due_reminders = []
        birthday_alerts = []
        so_approved_alerts = []
        target_achieved_alerts = []
        joining_day_alerts = []
        work_anniversary_alerts = []

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    today_followups, today_free_trials, unread_emails, unread_chat, _ = fetch_sidebar_live_counts(cursor, user_uuid, user_id)

                    cursor.execute("SELECT live_status FROM users WHERE id = %s", (user_id,))
                    u_row = cursor.fetchone()
                    if u_row:
                        live_status = u_row.get("live_status") or "online"

                    cursor.execute("SELECT MAX(id) AS max_id FROM recommendation")
                    max_row = cursor.fetchone()
                    if max_row and max_row.get("max_id"):
                        max_research_id = int(max_row["max_id"])

                    cursor.execute("SELECT COUNT(*) AS cnt FROM recommendation WHERE DATE(recommendation_time) = CURRENT_DATE()")
                    t_row = cursor.fetchone()
                    if t_row and t_row.get("cnt"):
                        today_research_count = int(t_row["cnt"])

                    # Check for due follow-up reminders for logged-in user
                    due_reminders = []
                    now_dt = datetime.datetime.now()

                    owner_context = fetch_owner_filter_options(cursor, user_uuid)
                    allowed_ids = owner_context.get("allowed_user_ids") or [user_id]
                    ph = ", ".join(["%s"] * len(allowed_ids))

                    sql_rem = f"""
                        SELECT 
                            f.id AS followup_id,
                            f.followup_date,
                            l.id AS lead_id,
                            l.lead_uuid,
                            COALESCE(l.name, 'Lead') AS lead_name
                        FROM followups f
                        JOIN leads l ON l.id = f.lead_id
                        WHERE DATE(f.followup_date) = CURRENT_DATE()
                          AND LOWER(COALESCE(f.followup_status, 'pending')) NOT IN ('completed', 'rescheduled')
                          AND (l.current_owner_user_id IN ({ph}) OR l.created_by IN ({ph}) OR f.created_by_user_id IN ({ph}))
                        ORDER BY f.followup_date ASC
                    """
                    rem_params = list(allowed_ids) + [str(x) for x in allowed_ids] + list(allowed_ids)
                    cursor.execute(sql_rem, rem_params)
                    rem_rows = cursor.fetchall() or []

                    for r in rem_rows:
                        f_date = r.get("followup_date")
                        if not f_date or not isinstance(f_date, (datetime.datetime, date)):
                            continue
                        diff_mins = (f_date - now_dt).total_seconds() / 60.0

                        alert_type = None
                        if 0.0 <= diff_mins <= 2.0:
                            alert_type = "2min"
                        elif 9.0 <= diff_mins <= 11.0:
                            alert_type = "10min"

                        if alert_type:
                            due_reminders.append({
                                "followup_id": r["followup_id"],
                                "lead_uuid": r["lead_uuid"],
                                "client_code": str(r["lead_id"]),
                                "lead_name": r["lead_name"],
                                "followup_time_fmt": f_date.strftime("%I:%M %p"),
                                "alert_type": alert_type
                            })

                    # Check for Employee Birthday Alerts
                    birthday_alerts = []
                    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'enable_birthday_alert'")
                    bday_setting_row = cursor.fetchone()
                    is_bday_enabled = (bday_setting_row.get("setting_value", "1") if bday_setting_row else "1") == "1"

                    if is_bday_enabled:
                        today_m_d = datetime.date.today().strftime("%m-%d")
                        today_d_m_slash = datetime.date.today().strftime("%d/%m")
                        today_d_m_dash = datetime.date.today().strftime("%d-%m")

                        cursor.execute("""
                            SELECT 
                                u.id AS user_id,
                                u.full_name,
                                u.date_of_birth,
                                COALESCE(d.designation_name, 'Team Member') AS designation_name
                            FROM users u
                            LEFT JOIN designations d ON d.id = u.designation_id
                            WHERE u.status = 1
                              AND u.date_of_birth IS NOT NULL
                              AND u.date_of_birth != ''
                        """)
                        all_active_users = cursor.fetchall() or []
                        for bu in all_active_users:
                            dob_str = str(bu.get("date_of_birth") or "").strip()
                            is_match = False
                            if dob_str.endswith("-" + today_m_d) or dob_str.startswith(today_d_m_slash + "/") or dob_str.startswith(today_d_m_dash + "-"):
                                is_match = True
                            elif len(dob_str) >= 10 and dob_str[4] == "-" and dob_str[7] == "-":
                                if dob_str[5:10] == today_m_d:
                                    is_match = True

                            if is_match:
                                birthday_alerts.append({
                                    "user_id": bu["user_id"],
                                    "full_name": bu["full_name"],
                                    "designation": bu["designation_name"]
                                })

                    # 2. SO Approved & Payment Alert (Approved within last 10 minutes for active logged-in users)
                    so_approved_alerts = []
                    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'enable_so_approved_alert'")
                    so_setting_row = cursor.fetchone()
                    if (so_setting_row.get("setting_value", "1") if so_setting_row else "1") == "1":
                        cursor.execute("""
                            SELECT 
                                so.id AS order_id,
                                so.order_number,
                                so.order_amount,
                                COALESCE(NULLIF(TRIM(so.invoice_name), ''), NULLIF(TRIM(l.name), ''), 'Valued Client') AS client_name,
                                COALESCE(u.full_name, 'Sales Rep') AS agent_name,
                                COALESCE(u_app.full_name, u.full_name, 'Admin') AS approved_by_name
                            FROM sales_orders so
                            LEFT JOIN leads l ON l.id = so.lead_id
                            LEFT JOIN users u ON u.id = so.created_by_user_id
                            LEFT JOIN users u_app ON u_app.id = so.approved_by_user_id
                            WHERE so.order_status = 'approved'
                              AND (
                                  (so.approved_at IS NOT NULL AND so.approved_at >= NOW() - INTERVAL 1 MINUTE)
                                  OR 
                                  (so.updated_at >= NOW() - INTERVAL 1 MINUTE)
                                  OR 
                                  (so.created_at >= NOW() - INTERVAL 1 MINUTE)
                              )
                            ORDER BY so.id DESC
                        """)
                        so_rows = cursor.fetchall() or []
                        for r in so_rows:
                            so_approved_alerts.append({
                                "order_id": r["order_id"],
                                "order_number": r["order_number"],
                                "client_name": r["client_name"],
                                "agent_name": r["agent_name"],
                                "approved_by_name": r["approved_by_name"],
                                "amount_fmt": f"₹{float(r['order_amount'] or 0):,.2f}"
                            })

                    # 3. Target Achieved Congratulation Alert
                    target_achieved_alerts = []
                    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'enable_target_achieved_alert'")
                    tgt_setting_row = cursor.fetchone()
                    if (tgt_setting_row.get("setting_value", "1") if tgt_setting_row else "1") == "1":
                        cursor.execute("""
                            SELECT 
                                u.id AS user_id,
                                u.full_name,
                                u.target,
                                COALESCE(SUM(so.order_amount), 0) AS total_sales
                            FROM users u
                            JOIN sales_orders so ON so.created_by_user_id = u.id
                            WHERE u.status = 1
                              AND u.target > 0
                              AND so.order_status = 'approved'
                              AND YEAR(so.created_at) = YEAR(CURRENT_DATE())
                              AND MONTH(so.created_at) = MONTH(CURRENT_DATE())
                            GROUP BY u.id, u.full_name, u.target
                            HAVING total_sales >= u.target
                        """)
                        tgt_rows = cursor.fetchall() or []
                        for r in tgt_rows:
                            target_achieved_alerts.append({
                                "user_id": r["user_id"],
                                "full_name": r["full_name"],
                                "target_fmt": f"₹{float(r['target']):,.0f}",
                                "achieved_fmt": f"₹{float(r['total_sales']):,.0f}"
                            })

                    # 4. New Employee Joining Alert
                    joining_day_alerts = []
                    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'enable_joining_day_alert'")
                    join_setting_row = cursor.fetchone()
                    if (join_setting_row.get("setting_value", "1") if join_setting_row else "1") == "1":
                        cursor.execute("""
                            SELECT 
                                u.id AS user_id,
                                u.full_name,
                                u.date_of_joining,
                                COALESCE(d.designation_name, 'Team Member') AS designation_name
                            FROM users u
                            LEFT JOIN designations d ON d.id = u.designation_id
                            WHERE u.status = 1
                              AND u.date_of_joining IS NOT NULL
                        """)
                        all_join_users = cursor.fetchall() or []
                        for r in all_join_users:
                            doj_str = str(r.get("date_of_joining") or "").strip()
                            today_iso = datetime.date.today().strftime("%Y-%m-%d")
                            today_dmy_slash = datetime.date.today().strftime("%d/%m/%Y")
                            today_dmy_dash = datetime.date.today().strftime("%d-%m-%Y")
                            if doj_str in (today_iso, today_dmy_slash, today_dmy_dash) or doj_str.startswith(today_iso):
                                joining_day_alerts.append({
                                    "user_id": r["user_id"],
                                    "full_name": r["full_name"],
                                    "designation": r["designation_name"]
                                })

                    # 5. Work Anniversary Alert
                    work_anniversary_alerts = []
                    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'enable_work_anniversary_alert'")
                    anniv_setting_row = cursor.fetchone()
                    if (anniv_setting_row.get("setting_value", "1") if anniv_setting_row else "1") == "1":
                        cursor.execute("""
                            SELECT 
                                u.id AS user_id,
                                u.full_name,
                                u.date_of_joining,
                                COALESCE(d.designation_name, 'Team Member') AS designation_name
                            FROM users u
                            LEFT JOIN designations d ON d.id = u.designation_id
                            WHERE u.status = 1
                              AND u.date_of_joining IS NOT NULL
                        """)
                        all_anniv_users = cursor.fetchall() or []
                        today_m_d = datetime.date.today().strftime("%m-%d")
                        curr_year = datetime.date.today().year

                        for r in all_anniv_users:
                            doj_raw = str(r.get("date_of_joining") or "").strip()
                            join_year = None
                            join_md = None

                            match_iso = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})", doj_raw)
                            if match_iso:
                                y, m, d = match_iso.groups()
                                join_year = int(y)
                                join_md = f"{int(m):02d}-{int(d):02d}"
                            else:
                                match_dmy = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})", doj_raw)
                                if match_dmy:
                                    d, m, y = match_dmy.groups()
                                    join_year = int(y)
                                    join_md = f"{int(m):02d}-{int(d):02d}"

                            if join_md and join_md == today_m_d and join_year and join_year < curr_year:
                                years_diff = curr_year - join_year
                                work_anniversary_alerts.append({
                                    "user_id": r["user_id"],
                                    "full_name": r["full_name"],
                                    "designation": r["designation_name"],
                                    "years": years_diff
                                })

            except Exception as err:
                print("DEBUG ALERT ERROR:", err)
            finally:
                conn.close()

        return jsonify({
            "success": True,
            "today_followups": today_followups,
            "today_free_trials": today_free_trials,
            "unread_emails": unread_emails,
            "chat_unread_count": unread_chat,
            "max_research_id": max_research_id,
            "today_research_count": today_research_count,
            "live_status": live_status,
            "due_reminders": due_reminders,
            "birthday_alerts": birthday_alerts,
            "so_approved_alerts": so_approved_alerts,
            "target_achieved_alerts": target_achieved_alerts,
            "joining_day_alerts": joining_day_alerts,
            "work_anniversary_alerts": work_anniversary_alerts
        }), 200
