import logging
import re
import urllib.parse
import urllib3
import requests
from flask import render_template, request, jsonify, session, redirect, url_for, Response, flash
from config import get_db_connection
from utils.calling_db import (
    get_call_summary_report,
    get_call_history_report,
    fetch_crm_extension_agent_map,
)
from utils.permissions import has_permission, get_user_team_users

urllib3.disable_warnings()
logger = logging.getLogger("calling_history")


def get_user_calling_scope(cursor, user_uuid):
    """
    Resolves permitted users and allowed extensions based on role hierarchy:
    - Admin or Global Access: returns (None, all_active_agents) [None = no restriction]
    - Manager / Team Lead: returns (team_extension_list, team_agents_list)
    - Self / Telecaller: returns (self_extension_list, self_agent_list)
    """
    cursor.execute(
        "SELECT id, user_uuid, full_name, is_admin, role_id, extension_id FROM users WHERE user_uuid = %s LIMIT 1",
        (user_uuid,),
    )
    user = cursor.fetchone()
    if not user:
        return [], []

    is_admin = int(user.get("is_admin") or 0) == 1
    has_global = has_permission("global_access_scope", "global_data_access") or has_permission("call_summary", "view_all")

    if is_admin or has_global:
        # Full unrestricted access to all extensions
        cursor.execute("""
            SELECT u.id, u.user_uuid, u.full_name, e.extension_number
            FROM users u
            JOIN extensions e ON e.id = u.extension_id
            WHERE u.status = 1 AND e.status = 1 AND e.extension_number IS NOT NULL
            ORDER BY u.full_name ASC
        """)
        agents = cursor.fetchall() or []
        return None, agents

    # Hierarchical scope: Team Users (self + recursive reportees)
    team_users = get_user_team_users(cursor, user["id"])
    team_user_ids = [u["id"] for u in team_users] if team_users else [user["id"]]

    if not team_user_ids:
        team_user_ids = [user["id"]]

    id_ph = ", ".join(["%s"] * len(team_user_ids))
    cursor.execute(f"""
        SELECT u.id, u.user_uuid, u.full_name, e.extension_number
        FROM users u
        JOIN extensions e ON e.id = u.extension_id
        WHERE u.id IN ({id_ph}) AND u.status = 1 AND e.status = 1 AND e.extension_number IS NOT NULL
        ORDER BY u.full_name ASC
    """, team_user_ids)
    team_agents = cursor.fetchall() or []

    allowed_exts = [str(a["extension_number"]).strip() for a in team_agents if a.get("extension_number")]
    return allowed_exts, team_agents


def calling_history_routes(app):

    # ==========================================
    # 1. CALL SUMMARY MODULE
    # ==========================================
    @app.route("/calldesk/summary", methods=["GET"])
    @app.route("/calls/summary", methods=["GET"], endpoint="call_summary")
    def call_summary_page():
        flash("The Call Summary module has been removed.", "info")
        return redirect(url_for("dashboard"))

        conn = get_db_connection()
        logged_user_extension = None
        try:
            with conn.cursor() as cursor:
                allowed_exts, agents = get_user_calling_scope(cursor, logged_user_uuid)
                is_admin_or_manager = (allowed_exts is None) or len(agents) > 1

                cursor.execute("""
                    SELECT e.extension_number
                    FROM users u
                    JOIN extensions e ON e.id = u.extension_id
                    WHERE u.user_uuid = %s AND u.status = 1 AND e.status = 1
                    LIMIT 1
                """, (logged_user_uuid,))
                ext_row = cursor.fetchone()
                if ext_row and ext_row.get("extension_number"):
                    logged_user_extension = str(ext_row["extension_number"]).strip()
        finally:
            conn.close()

        return render_template(
            "calls/call_summary.html",
            agents=agents,
            logged_user_extension=logged_user_extension,
            is_admin_or_manager=is_admin_or_manager,
            active_group="calls",
            active_page="call_summary",
            page_title="Call Summary",
            page_heading="Call Summary & Analytics",
        )

    @app.route("/api/calls/summary", methods=["POST"])
    def api_call_summary():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Authentication required."}), 401

        payload = request.get_json(silent=True) or {}
        date_preset = (payload.get("date_preset") or "today").strip().lower()
        start_date = (payload.get("start_date") or "").strip()
        end_date = (payload.get("end_date") or "").strip()
        extension = (payload.get("extension") or "").strip()

        # Enforce user hierarchy
        conn = get_db_connection()
        allowed_exts = None
        try:
            with conn.cursor() as cursor:
                allowed_exts, _ = get_user_calling_scope(cursor, logged_user_uuid)
        finally:
            conn.close()

        # If user picked a specific extension, verify they are allowed to see it
        if extension and extension.lower() != "all":
            if allowed_exts is not None and extension not in allowed_exts:
                return jsonify({
                    "success": False,
                    "message": "You are not authorized to view this extension's calling data.",
                    "kpis": {},
                    "agent_summary": []
                }), 403

        report = get_call_summary_report(
            date_preset=date_preset,
            start_date=start_date or None,
            end_date=end_date or None,
            extension_filter=extension or None,
            allowed_extensions=allowed_exts
        )

        return jsonify(report)

    # ==========================================
    # 2. CALL HISTORY MODULE
    # ==========================================
    @app.route("/calldesk/history", methods=["GET"])
    @app.route("/calls/history", methods=["GET"], endpoint="call_history")
    def call_history_page():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        conn = get_db_connection()
        logged_user_extension = None
        try:
            with conn.cursor() as cursor:
                allowed_exts, agents = get_user_calling_scope(cursor, logged_user_uuid)
                is_admin_or_manager = (allowed_exts is None) or len(agents) > 1

                cursor.execute("""
                    SELECT e.extension_number
                    FROM users u
                    JOIN extensions e ON e.id = u.extension_id
                    WHERE u.user_uuid = %s AND u.status = 1 AND e.status = 1
                    LIMIT 1
                """, (logged_user_uuid,))
                ext_row = cursor.fetchone()
                if ext_row and ext_row.get("extension_number"):
                    logged_user_extension = str(ext_row["extension_number"]).strip()
        finally:
            conn.close()

        return render_template(
            "calls/call_history.html",
            agents=agents,
            logged_user_extension=logged_user_extension,
            is_admin_or_manager=is_admin_or_manager,
            active_group="calls",
            active_page="call_history",
            page_title="Call History",
            page_heading="Call History & Detail Records",
        )

    @app.route("/api/calls/history", methods=["POST"])
    def api_call_history():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Authentication required."}), 401

        payload = request.get_json(silent=True) or {}
        date_preset = (payload.get("date_preset") or "today").strip().lower()
        start_date = (payload.get("start_date") or "").strip()
        end_date = (payload.get("end_date") or "").strip()
        extension = (payload.get("extension") or "").strip()
        disposition = (payload.get("disposition") or "").strip()
        direction = (payload.get("direction") or "").strip()
        duration_filter = (payload.get("duration_filter") or "").strip()
        min_duration = payload.get("min_duration")
        max_duration = payload.get("max_duration")
        search_query = (payload.get("search_query") or "").strip()
        page = int(payload.get("page") or 1)
        page_size = int(payload.get("page_size") or 25)

        provider = (payload.get("provider") or "").strip()

        # Enforce user hierarchy and check mobile masking & click to call permissions
        conn = get_db_connection()
        allowed_exts = None
        can_view_full_mobile = True
        can_click_to_call = True
        try:
            with conn.cursor() as cursor:
                allowed_exts, _ = get_user_calling_scope(cursor, logged_user_uuid)
                cursor.execute(
                    "SELECT is_admin, number_show_hide, click_to_call FROM users WHERE user_uuid = %s LIMIT 1",
                    (logged_user_uuid,)
                )
                u_row = cursor.fetchone() or {}
                # number_show_hide == 1 means Hide/Mask number; 0 means Show full number
                can_view_full_mobile = (int(u_row.get("number_show_hide") or 1) == 0)
                can_click_to_call = (int(u_row.get("click_to_call") or 0) == 1)
        finally:
            conn.close()

        # If user picked a specific extension, verify they are allowed to see it
        if extension and extension.lower() != "all":
            if allowed_exts is not None and extension not in allowed_exts:
                return jsonify({
                    "success": False,
                    "message": "You are not authorized to view this extension's call history.",
                    "calls": [],
                    "total_records": 0
                }), 403

        report = get_call_history_report(
            date_preset=date_preset,
            start_date=start_date or None,
            end_date=end_date or None,
            extension_filter=extension or None,
            disposition_filter=disposition or None,
            direction_filter=direction or None,
            duration_filter=duration_filter or None,
            min_duration=min_duration,
            max_duration=max_duration,
            search_query=search_query or None,
            allowed_extensions=allowed_exts,
            can_view_full_mobile=can_view_full_mobile,
            can_click_to_call=can_click_to_call,
            page=page,
            page_size=page_size,
            provider_filter=provider or None,
        )

        return jsonify(report)

    # ==========================================
    # 3. CLOUDCONNECT WEBHOOK / CALLBACK
    # ==========================================
    @app.route("/callback.php", methods=["GET", "POST"])
    @app.route("/api/cloudconnect/webhook", methods=["GET", "POST"])
    def cloudconnect_webhook():
        """
        Receives real-time call event callbacks from CloudConnect PBX.
        Parameters from CloudConnect:
          uuid, extension_number, caller_name, caller_number, call_status, duration, call_rec_path, etc.
        """
        import json
        import datetime
        data = {}
        if request.is_json:
            data.update(request.get_json(silent=True) or {})
        if request.form:
            data.update(request.form.to_dict())
        if request.args:
            data.update(request.args.to_dict())

        logger.info("CloudConnect Webhook callback received: %s", data)

        uuid_val = str(data.get("uuid") or data.get("callid") or data.get("unique_token") or data.get("data") or "").strip()
        if not uuid_val:
            return jsonify({"status": "SUCCESS", "message": "Ignored, missing uuid"}), 200

        ext_num = str(data.get("extension_number") or data.get("extension") or "").strip()
        caller = str(data.get("caller_number") or data.get("caller") or ext_num or "").strip()
        callee = str(data.get("called_number") or data.get("callee") or data.get("phone_number") or "").strip()
        status_val = str(data.get("call_status") or data.get("status") or "").strip()
        duration_val = int(data.get("duration") or data.get("call_sec") or 0)
        billsec_val = int(data.get("billsec") or data.get("answer_sec") or 0)
        rec_url = str(data.get("recording_url") or data.get("call_rec_path") or "").strip()

        if "answer" in status_val.lower():
            disp = "ANSWERED"
        elif "busy" in status_val.lower():
            disp = "BUSY"
        elif "fail" in status_val.lower():
            disp = "FAILED"
        else:
            disp = "NO ANSWER"

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO crm_cdr (
                        provider, uniqueid, calldate, src, dst,
                        duration, billsec, disposition, recordingfile,
                        call_direction, extra_info
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        duration = VALUES(duration),
                        billsec = VALUES(billsec),
                        disposition = VALUES(disposition),
                        recordingfile = COALESCE(NULLIF(VALUES(recordingfile), ''), recordingfile),
                        extra_info = VALUES(extra_info)
                """, (
                    "cloudconnect",
                    uuid_val,
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    caller,
                    callee,
                    duration_val,
                    billsec_val,
                    disp,
                    rec_url,
                    "outbound",
                    json.dumps(data),
                ))
            conn.commit()
        except Exception as exc:
            logger.error("Error saving CloudConnect webhook to crm_cdr: %s", exc)
        finally:
            conn.close()

        return jsonify({"status": "SUCCESS", "message": "Callback processed"}), 200

    @app.route("/api/calls/recording-stream/<path:filename>", methods=["GET"])
    def api_call_recording_stream(filename):
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Clean filename to avoid path traversal
        clean_name = filename.split("/")[-1].strip()
        if not clean_name:
            return jsonify({"error": "Invalid filename"}), 400

        # Get active telephony server API config from DB
        conn = get_db_connection()
        server_config = None
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM calling_apis WHERE status = 1 ORDER BY id ASC LIMIT 1")
                server_config = cursor.fetchone()
        finally:
            conn.close()

        server_host = (server_config.get("server_host") if server_config else "") or "pbx.elitefinserv.in"
        server_user = (server_config.get("server_username") if server_config else "") or "admin"
        server_pass = (server_config.get("server_password") if server_config else "") or "vijay@123"

        # Extract uniqueid from filename if present
        match = re.search(r'(\d+\.\d+)\.(wav|gsm|mp3|WAV|GSM|MP3)', clean_name)
        uniqueid = match.group(1) if match else ""

        encoded_filename = urllib.parse.quote(clean_name)

        sess = requests.Session()
        sess.verify = False

        # Authenticate session with Issabel Telephony server
        for u in ["admin", server_user, "root"]:
            try:
                sess.post(
                    f"https://{server_host}/index.php",
                    data={"input_user": u, "input_pass": server_pass, "submit_login": "Login"},
                    timeout=4
                )
                if "issabelSession" in sess.cookies.get_dict():
                    break
            except Exception:
                pass

        download_url = f"https://{server_host}/index.php?menu=monitoring&action=download&id={uniqueid}&namefile={encoded_filename}&rawmode=yes"

        try:
            rec_res = sess.get(download_url, stream=True, timeout=10)

            if rec_res.status_code == 200 and "text/html" not in rec_res.headers.get("content-type", ""):
                is_download = request.args.get("download") == "1"
                disposition = "attachment" if is_download else "inline"
                
                headers = {
                    "Content-Disposition": f'{disposition}; filename="{clean_name}"',
                    "Content-Type": rec_res.headers.get("content-type", "audio/wav"),
                    "Accept-Ranges": "bytes"
                }
                if rec_res.headers.get("content-length"):
                    headers["Content-Length"] = rec_res.headers.get("content-length")

                return Response(rec_res.iter_content(chunk_size=8192), status=200, headers=headers)
        except Exception as e:
            logger.error(f"Error fetching recording from telephony server: {e}")

        return jsonify({"error": "Recording file not found or inaccessible on telephony server"}), 404
