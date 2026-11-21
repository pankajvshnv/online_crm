import datetime
import logging
import threading
import time
import pymysql
from config import get_db_connection

logger = logging.getLogger("calling_db")

_LAST_SYNC_TIME = 0
_SYNC_LOCK = threading.Lock()


def trigger_background_cdr_sync(start_date=None, end_date=None, force=False):
    """
    Spawns a background thread to sync latest call logs from CloudConnect
    and remote Issabel PBX into local crm_cdr without blocking UI threads.
    """
    global _LAST_SYNC_TIME
    now = time.time()
    if not force and (now - _LAST_SYNC_TIME) < 15:
        return

    def _sync_worker():
        global _LAST_SYNC_TIME
        with _SYNC_LOCK:
            _LAST_SYNC_TIME = time.time()
            try:
                from utils.cloudconnect import sync_cloudconnect_cdr_to_db, sync_issabel_cdr_to_db
                sync_cloudconnect_cdr_to_db(start_date=start_date, end_date=end_date)
                sync_issabel_cdr_to_db(days_back=7, limit=300)
            except Exception as exc:
                logger.warning(f"Background CDR sync notice: {exc}")

    t = threading.Thread(target=_sync_worker, daemon=True)
    t.start()



def format_seconds_to_hms(total_seconds):
    """Formats integer seconds into HH:MM:SS or MM:SS."""
    if not total_seconds or total_seconds <= 0:
        return "00:00"
    total_seconds = int(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def get_remote_calling_connection(server_config=None):
    """
    Establishes connection to the active remote Issabel/Asterisk PBX MySQL database.
    """
    if not server_config:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM calling_apis WHERE status = 1 ORDER BY id ASC LIMIT 1")
                server_config = cursor.fetchone()
        finally:
            conn.close()

    if not server_config:
        return None, "No active calling server API configured in CRM."

    host = server_config.get("server_host")
    user = server_config.get("server_username")
    password = server_config.get("server_password")
    db_name = server_config.get("server_db_name") or "asteriskcdrdb"

    if not host or not user:
        return None, "Calling server host or credentials missing."

    try:
        remote_conn = pymysql.connect(
            host=host,
            user=user,
            password=password or "",
            database=db_name,
            connect_timeout=4,
            read_timeout=6,
            cursorclass=pymysql.cursors.DictCursor
        )
        return remote_conn, None
    except pymysql.err.OperationalError as e:
        logger.error(f"Calling PBX database connection error: {e}")
        return None, f"Unable to connect to Calling Server ({host}): {e.args[1] if len(e.args) > 1 else str(e)}"
    except Exception as e:
        logger.error(f"Calling PBX error: {e}")
        return None, f"Calling Server Error: {str(e)}"


def fetch_crm_extension_agent_map():
    """
    Fetches all CRM users and extensions to build an in-memory dictionary
    mapping extension_number (str) -> { user_id, user_uuid, full_name, role_name }
    """
    ext_map = {}
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    u.id AS user_id,
                    u.user_uuid,
                    u.full_name,
                    d.designation_name,
                    r.role_name,
                    e.extension_number,
                    e.id AS extension_id
                FROM users u
                JOIN extensions e ON e.id = u.extension_id
                LEFT JOIN designations d ON d.id = u.designation_id
                LEFT JOIN roles r ON r.id = u.role_id
                WHERE u.status = 1 AND e.status = 1 AND e.extension_number IS NOT NULL
            """)
            rows = cursor.fetchall() or []
            for r in rows:
                ext_str = str(r["extension_number"]).strip()
                if ext_str:
                    ext_map[ext_str] = {
                        "user_id": r["user_id"],
                        "user_uuid": r["user_uuid"],
                        "full_name": r["full_name"],
                        "designation_name": r.get("designation_name") or "Agent",
                        "role_name": r.get("role_name") or "Agent",
                        "extension_number": ext_str,
                    }
    except Exception as e:
        logger.error(f"Error fetching CRM extension map: {e}")
    finally:
        conn.close()

    return ext_map


def build_cdr_date_filter(date_preset="today", start_date=None, end_date=None):
    """
    Builds SQL WHERE clause and parameters for CDR `calldate`.
    """
    today = datetime.date.today()
    where_sql = ""
    params = []

    if date_preset == "today":
        where_sql = "calldate >= %s AND calldate < %s"
        params = [f"{today.strftime('%Y-%m-%d')} 00:00:00", f"{(today + datetime.timedelta(days=1)).strftime('%Y-%m-%d')} 00:00:00"]
    elif date_preset == "yesterday":
        yest = today - datetime.timedelta(days=1)
        where_sql = "calldate >= %s AND calldate < %s"
        params = [f"{yest.strftime('%Y-%m-%d')} 00:00:00", f"{today.strftime('%Y-%m-%d')} 00:00:00"]
    elif date_preset == "this_week":
        start_of_week = today - datetime.timedelta(days=today.weekday())
        where_sql = "calldate >= %s AND calldate < %s"
        params = [f"{start_of_week.strftime('%Y-%m-%d')} 00:00:00", f"{(today + datetime.timedelta(days=1)).strftime('%Y-%m-%d')} 00:00:00"]
    elif date_preset == "this_month":
        start_of_month = today.replace(day=1)
        where_sql = "calldate >= %s AND calldate < %s"
        params = [f"{start_of_month.strftime('%Y-%m-%d')} 00:00:00", f"{(today + datetime.timedelta(days=1)).strftime('%Y-%m-%d')} 00:00:00"]
    elif date_preset == "custom":
        if start_date and end_date:
            where_sql = "calldate >= %s AND calldate <= %s"
            params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
        elif start_date:
            where_sql = "calldate >= %s"
            params = [f"{start_date} 00:00:00"]
        elif end_date:
            where_sql = "calldate <= %s"
            params = [f"{end_date} 23:59:59"]
        else:
            where_sql = "calldate >= %s"
            params = [f"{today.strftime('%Y-%m-%d')} 00:00:00"]
    elif date_preset == "all":
        where_sql = ""
        params = []
    else:
        where_sql = "calldate >= %s"
        params = [f"{today.strftime('%Y-%m-%d')} 00:00:00"]

    return where_sql, params


def get_call_summary_report(date_preset="today", start_date=None, end_date=None, extension_filter=None, allowed_extensions=None):
    """
    Queries local CRM CDR (crm_cdr) for aggregated summary metrics and agent-wise breakdown.
    Includes Inbound vs Outbound metrics, Talk Time (billsec), Ring Time (duration - billsec), and total duration.
    Synchronizes from configured providers in the background.
    """
    trigger_background_cdr_sync(start_date, end_date)

    conn = get_db_connection()
    if not conn:
        return {
            "success": False,
            "message": "CRM Database connection unavailable.",
            "kpis": {},
            "agent_summary": [],
            "hourly_traffic": []
        }

    date_sql, date_params = build_cdr_date_filter(date_preset, start_date, end_date)
    where_clauses = [date_sql] if date_sql else []
    query_params = list(date_params)

    # Specific extension filter from dropdown
    if extension_filter and str(extension_filter).strip() and str(extension_filter).lower() != "all":
        where_clauses.append("(src = %s OR dst = %s)")
        query_params.extend([str(extension_filter).strip(), str(extension_filter).strip()])
    elif allowed_extensions is not None:
        # User is not admin; restrict to their allowed team extension list
        if not allowed_extensions:
            # User has no extensions permitted
            where_clauses.append("1 = 0")
        else:
            ext_ph = ", ".join(["%s"] * len(allowed_extensions))
            where_clauses.append(f"(src IN ({ext_ph}) OR dst IN ({ext_ph}))")
            query_params.extend(allowed_extensions)
            query_params.extend(allowed_extensions)

    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    kpi_result = {}
    agent_summary = []
    hourly_traffic = []

    try:
        with conn.cursor() as cursor:
            # 1. Overall KPIs (Detailed with Inbound/Outbound, Talktime, Ringtime)
            kpi_query = f"""
                SELECT 
                    COUNT(*) AS total_calls,
                    COALESCE(SUM(CASE WHEN disposition = 'ANSWERED' THEN 1 ELSE 0 END), 0) AS answered_calls,
                    COALESCE(SUM(CASE WHEN disposition = 'NO ANSWER' THEN 1 ELSE 0 END), 0) AS no_answer_calls,
                    COALESCE(SUM(CASE WHEN disposition = 'BUSY' THEN 1 ELSE 0 END), 0) AS busy_calls,
                    COALESCE(SUM(CASE WHEN disposition = 'FAILED' THEN 1 ELSE 0 END), 0) AS failed_calls,
                    
                    -- Outbound breakdown (src length <= 6)
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 THEN 1 ELSE 0 END), 0) AS out_total,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 AND disposition = 'ANSWERED' THEN 1 ELSE 0 END), 0) AS out_answered,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 AND disposition != 'ANSWERED' THEN 1 ELSE 0 END), 0) AS out_missed,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 THEN billsec ELSE 0 END), 0) AS out_talktime,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 THEN (duration - billsec) ELSE 0 END), 0) AS out_ringtime,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 THEN duration ELSE 0 END), 0) AS out_duration,

                    -- Inbound breakdown (src length > 6 or dst length <= 6)
                    COALESCE(SUM(CASE WHEN LENGTH(src) > 6 AND LENGTH(dst) <= 6 THEN 1 ELSE 0 END), 0) AS in_total,
                    COALESCE(SUM(CASE WHEN LENGTH(src) > 6 AND LENGTH(dst) <= 6 AND disposition = 'ANSWERED' THEN 1 ELSE 0 END), 0) AS in_answered,
                    COALESCE(SUM(CASE WHEN LENGTH(src) > 6 AND LENGTH(dst) <= 6 AND disposition != 'ANSWERED' THEN 1 ELSE 0 END), 0) AS in_missed,
                    COALESCE(SUM(CASE WHEN LENGTH(src) > 6 AND LENGTH(dst) <= 6 THEN billsec ELSE 0 END), 0) AS in_talktime,
                    COALESCE(SUM(CASE WHEN LENGTH(src) > 6 AND LENGTH(dst) <= 6 THEN (duration - billsec) ELSE 0 END), 0) AS in_ringtime,
                    COALESCE(SUM(CASE WHEN LENGTH(src) > 6 AND LENGTH(dst) <= 6 THEN duration ELSE 0 END), 0) AS in_duration,

                    -- Totals
                    COALESCE(SUM(duration), 0) AS total_duration,
                    COALESCE(SUM(billsec), 0) AS total_billsec,
                    COALESCE(SUM(duration - billsec), 0) AS total_ringsec
                FROM crm_cdr
                {where_str}
            """
            cursor.execute(kpi_query, query_params)
            k_row = cursor.fetchone() or {}

            tot_calls = int(k_row.get("total_calls") or 0)
            ans_calls = int(k_row.get("answered_calls") or 0)
            no_ans = int(k_row.get("no_answer_calls") or 0)
            busy = int(k_row.get("busy_calls") or 0)
            failed = int(k_row.get("failed_calls") or 0)
            tot_dur = int(k_row.get("total_duration") or 0)
            tot_talk = int(k_row.get("total_billsec") or 0)
            tot_ring = int(k_row.get("total_ringsec") or 0)

            ans_rate = round((ans_calls / tot_calls * 100), 1) if tot_calls > 0 else 0.0
            avg_talk = round(tot_talk / ans_calls) if ans_calls > 0 else 0
            avg_ring = round(tot_ring / tot_calls) if tot_calls > 0 else 0

            # Outbound stats
            out_tot = int(k_row.get("out_total") or 0)
            out_ans = int(k_row.get("out_answered") or 0)
            out_miss = int(k_row.get("out_missed") or 0)
            out_talk = int(k_row.get("out_talktime") or 0)
            out_ring = int(k_row.get("out_ringtime") or 0)
            out_dur = int(k_row.get("out_duration") or 0)

            # Inbound stats
            in_tot = int(k_row.get("in_total") or 0)
            in_ans = int(k_row.get("in_answered") or 0)
            in_miss = int(k_row.get("in_missed") or 0)
            in_talk = int(k_row.get("in_talktime") or 0)
            in_ring = int(k_row.get("in_ringtime") or 0)
            in_dur = int(k_row.get("in_duration") or 0)

            kpi_result = {
                "total_calls": tot_calls,
                "answered_calls": ans_calls,
                "no_answer_calls": no_ans,
                "busy_calls": busy,
                "failed_calls": failed,
                "missed_total": no_ans + busy + failed,
                "answer_rate": f"{ans_rate}%",
                "answer_rate_num": ans_rate,
                
                # Outbound
                "outbound_total": out_tot,
                "outbound_answered": out_ans,
                "outbound_missed": out_miss,
                "outbound_talktime_sec": out_talk,
                "outbound_talktime_fmt": format_seconds_to_hms(out_talk),
                "outbound_ringtime_sec": out_ring,
                "outbound_ringtime_fmt": format_seconds_to_hms(out_ring),
                "outbound_duration_sec": out_dur,
                "outbound_duration_fmt": format_seconds_to_hms(out_dur),

                # Inbound
                "inbound_total": in_tot,
                "inbound_answered": in_ans,
                "inbound_missed": in_miss,
                "inbound_talktime_sec": in_talk,
                "inbound_talktime_fmt": format_seconds_to_hms(in_talk),
                "inbound_ringtime_sec": in_ring,
                "inbound_ringtime_fmt": format_seconds_to_hms(in_ring),
                "inbound_duration_sec": in_dur,
                "inbound_duration_fmt": format_seconds_to_hms(in_dur),

                # Overall Time
                "total_duration_sec": tot_dur,
                "total_duration_fmt": format_seconds_to_hms(tot_dur),
                "total_talktime_sec": tot_talk,
                "total_talktime_fmt": format_seconds_to_hms(tot_talk),
                "total_ringtime_sec": tot_ring,
                "total_ringtime_fmt": format_seconds_to_hms(tot_ring),
                "avg_talktime_sec": avg_talk,
                "avg_talktime_fmt": format_seconds_to_hms(avg_talk),
                "avg_ringtime_sec": avg_ring,
                "avg_ringtime_fmt": format_seconds_to_hms(avg_ring),
            }

            # 2. Extension / Agent breakdown (Filter internal extensions with length <= 6)
            ext_where = list(where_clauses)
            ext_where.append("LENGTH(src) <= 6")
            ext_where_str = f"WHERE {' AND '.join(ext_where)}"

            ext_query = f"""
                SELECT 
                    src AS extension,
                    COUNT(*) AS total_calls,
                    
                    -- Outbound metrics
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 THEN 1 ELSE 0 END), 0) AS out_total,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 AND disposition = 'ANSWERED' THEN 1 ELSE 0 END), 0) AS out_answered,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 AND disposition != 'ANSWERED' THEN 1 ELSE 0 END), 0) AS out_missed,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 THEN billsec ELSE 0 END), 0) AS out_talktime,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 THEN (duration - billsec) ELSE 0 END), 0) AS out_ringtime,

                    -- Overall metrics
                    COALESCE(SUM(CASE WHEN disposition = 'ANSWERED' THEN 1 ELSE 0 END), 0) AS answered,
                    COALESCE(SUM(CASE WHEN disposition != 'ANSWERED' THEN 1 ELSE 0 END), 0) AS missed,
                    COALESCE(SUM(CASE WHEN disposition = 'BUSY' THEN 1 ELSE 0 END), 0) AS busy,
                    COALESCE(SUM(CASE WHEN disposition = 'NO ANSWER' THEN 1 ELSE 0 END), 0) AS no_answer,
                    COALESCE(SUM(billsec), 0) AS total_talktime,
                    COALESCE(SUM(duration - billsec), 0) AS total_ringtime,
                    COALESCE(SUM(duration), 0) AS total_duration
                FROM crm_cdr
                {ext_where_str}
                GROUP BY src
                ORDER BY total_calls DESC
            """
            cursor.execute(ext_query, query_params)
            ext_rows = cursor.fetchall() or []

            # Also fetch Inbound calls per extension for mapping
            inbound_ext_map = {}
            in_where = list(where_clauses)
            in_where.append("LENGTH(dst) <= 6 AND LENGTH(src) > 6")
            in_where_str = f"WHERE {' AND '.join(in_where)}"
            
            in_query = f"""
                SELECT 
                    dst AS extension,
                    COUNT(*) AS in_total,
                    COALESCE(SUM(CASE WHEN disposition = 'ANSWERED' THEN 1 ELSE 0 END), 0) AS in_answered,
                    COALESCE(SUM(CASE WHEN disposition != 'ANSWERED' THEN 1 ELSE 0 END), 0) AS in_missed,
                    COALESCE(SUM(billsec), 0) AS in_talktime,
                    COALESCE(SUM(duration - billsec), 0) AS in_ringtime
                FROM crm_cdr
                {in_where_str}
                GROUP BY dst
            """
            cursor.execute(in_query, query_params)
            in_rows = cursor.fetchall() or []
            for ir in in_rows:
                ext_k = str(ir["extension"]).strip()
                inbound_ext_map[ext_k] = {
                    "in_total": int(ir.get("in_total") or 0),
                    "in_answered": int(ir.get("in_answered") or 0),
                    "in_missed": int(ir.get("in_missed") or 0),
                    "in_talktime": int(ir.get("in_talktime") or 0),
                    "in_ringtime": int(ir.get("in_ringtime") or 0),
                }

            crm_ext_map = fetch_crm_extension_agent_map()

            for idx, er in enumerate(ext_rows, 1):
                ext_key = str(er["extension"]).strip()
                agent_info = crm_ext_map.get(ext_key, {})
                agent_name = agent_info.get("full_name") or f"Extension {ext_key}"
                role_name = agent_info.get("role_name") or "Unmapped Extension"
                is_mapped = bool(agent_info.get("full_name"))

                e_total = int(er.get("total_calls") or 0)
                e_ans = int(er.get("answered") or 0)
                e_missed = int(er.get("missed") or 0)
                e_talk = int(er.get("total_talktime") or 0)
                e_ring = int(er.get("total_ringtime") or 0)
                e_dur = int(er.get("total_duration") or 0)

                # Outbound per ext
                e_out_tot = int(er.get("out_total") or 0)
                e_out_ans = int(er.get("out_answered") or 0)
                e_out_miss = int(er.get("out_missed") or 0)
                e_out_talk = int(er.get("out_talktime") or 0)
                e_out_ring = int(er.get("out_ringtime") or 0)

                # Inbound per ext
                in_info = inbound_ext_map.get(ext_key, {})
                e_in_tot = in_info.get("in_total", 0)
                e_in_ans = in_info.get("in_answered", 0)
                e_in_miss = in_info.get("in_missed", 0)
                e_in_talk = in_info.get("in_talktime", 0)
                e_in_ring = in_info.get("in_ringtime", 0)

                e_rate = round((e_ans / e_total * 100), 1) if e_total > 0 else 0.0
                e_avg_talk = round(e_talk / e_ans) if e_ans > 0 else 0
                e_avg_ring = round(e_ring / e_total) if e_total > 0 else 0

                agent_summary.append({
                    "rank": idx,
                    "extension": ext_key,
                    "agent_name": agent_name,
                    "designation_name": agent_info.get("designation_name") or ("Designation N/A" if is_mapped else "Unmapped Extension"),
                    "role_name": role_name,
                    "is_mapped": is_mapped,
                    "user_uuid": agent_info.get("user_uuid") or "",
                    
                    # Totals
                    "total_calls": e_total,
                    "answered": e_ans,
                    "missed": e_missed,
                    "answer_rate": f"{e_rate}%",
                    "answer_rate_num": e_rate,
                    
                    # Outbound
                    "outbound_total": e_out_tot,
                    "outbound_answered": e_out_ans,
                    "outbound_missed": e_out_miss,
                    "outbound_talktime_sec": e_out_talk,
                    "outbound_talktime_fmt": format_seconds_to_hms(e_out_talk),
                    "outbound_ringtime_fmt": format_seconds_to_hms(e_out_ring),
                    "outbound_duration_sec": e_out_talk + e_out_ring,
                    "outbound_duration_fmt": format_seconds_to_hms(e_out_talk + e_out_ring),

                    # Inbound
                    "inbound_total": e_in_tot,
                    "inbound_answered": e_in_ans,
                    "inbound_missed": e_in_miss,
                    "inbound_talktime_sec": e_in_talk,
                    "inbound_talktime_fmt": format_seconds_to_hms(e_in_talk),
                    "inbound_ringtime_fmt": format_seconds_to_hms(e_in_ring),
                    "inbound_duration_sec": e_in_talk + e_in_ring,
                    "inbound_duration_fmt": format_seconds_to_hms(e_in_talk + e_in_ring),

                    # Talktime vs Ringtime
                    "total_talktime_sec": e_talk,
                    "total_talktime_fmt": format_seconds_to_hms(e_talk),
                    "total_ringtime_sec": e_ring,
                    "total_ringtime_fmt": format_seconds_to_hms(e_ring),
                    "total_duration_sec": e_dur,
                    "total_duration_fmt": format_seconds_to_hms(e_dur),
                    "avg_talktime_sec": e_avg_talk,
                    "avg_talktime_fmt": format_seconds_to_hms(e_avg_talk),
                    "avg_ringtime_sec": e_avg_ring,
                    "avg_ringtime_fmt": format_seconds_to_hms(e_avg_ring),
                })

    finally:
        conn.close()

    return {
        "success": True,
        "date_preset": date_preset,
        "kpis": kpi_result,
        "agent_summary": agent_summary,
        "hourly_traffic": hourly_traffic
    }


def normalize_phone_number(raw_num):
    """Normalizes phone number to 10 digits."""
    if not raw_num:
        return ""
    import re
    digits = re.sub(r"\D", "", str(raw_num).strip())
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    elif len(digits) > 10 and digits.startswith("0"):
        digits = digits[-10:]
    elif len(digits) == 10:
        return digits
    elif len(digits) > 10:
        return digits[-10:]
    return digits


def get_call_history_report(
    date_preset="today",
    start_date=None,
    end_date=None,
    extension_filter=None,
    disposition_filter=None,
    direction_filter=None,
    duration_filter=None,
    min_duration=None,
    max_duration=None,
    search_query=None,
    allowed_extensions=None,
    can_view_full_mobile=True,
    can_click_to_call=True,
    page=1,
    page_size=25,
    provider_filter=None,
):
    """
    Fetches paginated, enriched call history records from local crm_cdr.
    Enriches each record live with CRM Lead Name, Lead Status, Agent Name, Designation,
    number masking, click-to-call active flag, and duration filtering.
    Synchronizes from configured providers in the background.
    """
    import re
    trigger_background_cdr_sync(start_date, end_date)

    conn = get_db_connection()
    if not conn:
        return {
            "success": False,
            "message": "CRM Database connection unavailable.",
            "calls": [],
            "total_records": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }

    date_sql, date_params = build_cdr_date_filter(date_preset, start_date, end_date)
    where_clauses = [date_sql] if date_sql else []
    query_params = list(date_params)

    # Provider filter
    if provider_filter and str(provider_filter).strip().lower() not in ["all", ""]:
        where_clauses.append("provider = %s")
        query_params.append(str(provider_filter).strip().lower())

    # 1. Extension filter
    if extension_filter and str(extension_filter).strip() and str(extension_filter).lower() != "all":
        where_clauses.append("(src = %s OR dst = %s)")
        query_params.extend([str(extension_filter).strip(), str(extension_filter).strip()])
    elif allowed_extensions is not None:
        if not allowed_extensions:
            where_clauses.append("1 = 0")
        else:
            ext_ph = ", ".join(["%s"] * len(allowed_extensions))
            where_clauses.append(f"(src IN ({ext_ph}) OR dst IN ({ext_ph}))")
            query_params.extend(allowed_extensions)
            query_params.extend(allowed_extensions)

    # 2. Disposition filter
    if disposition_filter and str(disposition_filter).strip() and str(disposition_filter).lower() != "all":
        where_clauses.append("disposition = %s")
        query_params.append(str(disposition_filter).strip().upper())

    # 3. Direction filter
    if direction_filter and str(direction_filter).strip().lower() == "outgoing":
        where_clauses.append("LENGTH(src) <= 6")
    elif direction_filter and str(direction_filter).strip().lower() == "inbound":
        where_clauses.append("(LENGTH(src) > 6 AND LENGTH(dst) <= 6)")

    # 4. Duration Filter
    if duration_filter:
        df = str(duration_filter).strip().lower()
        if df == "gt0":
            where_clauses.append("billsec > 0")
        elif df == "gt30":
            where_clauses.append("billsec >= 30")
        elif df == "gt60":
            where_clauses.append("billsec >= 60")
        elif df == "gt120":
            where_clauses.append("billsec >= 120")
        elif df == "gt300":
            where_clauses.append("billsec >= 300")
        elif df == "eq0":
            where_clauses.append("billsec = 0")
        elif df == "custom":
            if min_duration is not None and max_duration is not None:
                where_clauses.append("billsec >= %s AND billsec <= %s")
                query_params.extend([int(min_duration), int(max_duration)])
            elif min_duration is not None:
                where_clauses.append("billsec >= %s")
                query_params.append(int(min_duration))
            elif max_duration is not None:
                where_clauses.append("billsec <= %s")
                query_params.append(int(max_duration))

    # 5. Search query filter (matches phone, extension, Lead Code, or Lead Name)
    if search_query and str(search_query).strip():
        sq = str(search_query).strip()
        sq_digits = re.sub(r"\D", "", sq)
        
        matched_mobiles = []
        try:
            with conn.cursor() as cur:
                if sq_digits:
                    cur.execute(
                        "SELECT mobile_number FROM leads WHERE id = %s OR mobile_number LIKE %s LIMIT 30",
                        (int(sq_digits), f"%{sq_digits}%")
                    )
                else:
                    cur.execute(
                        "SELECT mobile_number FROM leads WHERE name LIKE %s LIMIT 30",
                        (f"%{sq}%",)
                    )
                for m_row in cur.fetchall() or []:
                    norm_m = normalize_phone_number(m_row.get("mobile_number"))
                    if norm_m and norm_m not in matched_mobiles:
                        matched_mobiles.append(norm_m)
        except Exception:
            pass

        search_or = ["src LIKE %s", "dst LIKE %s", "clid LIKE %s"]
        query_params.extend([f"%{sq}%", f"%{sq}%", f"%{sq}%"])

        if sq_digits and sq_digits != sq:
            search_or.append("src LIKE %s")
            search_or.append("dst LIKE %s")
            query_params.extend([f"%{sq_digits}%", f"%{sq_digits}%"])

        for mm in matched_mobiles:
            search_or.append("src LIKE %s")
            search_or.append("dst LIKE %s")
            query_params.extend([f"%{mm}%", f"%{mm}%"])

        where_clauses.append(f"({' OR '.join(search_or)})")

    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    page = max(1, int(page or 1))
    page_size = max(1, min(500, int(page_size or 25)))
    offset = (page - 1) * page_size

    total_records = 0
    calls_list = []

    try:
        with conn.cursor() as cursor:
            count_query = f"""
                SELECT 
                    COUNT(*) as total_count,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 THEN 1 ELSE 0 END), 0) AS outbound_count,
                    COALESCE(SUM(CASE WHEN LENGTH(src) > 6 AND LENGTH(dst) <= 6 THEN 1 ELSE 0 END), 0) AS inbound_count,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 THEN billsec ELSE 0 END), 0) AS outbound_talktime,
                    COALESCE(SUM(CASE WHEN LENGTH(src) > 6 AND LENGTH(dst) <= 6 THEN billsec ELSE 0 END), 0) AS inbound_talktime,
                    COALESCE(SUM(CASE WHEN LENGTH(src) <= 6 THEN duration ELSE 0 END), 0) AS outbound_duration,
                    COALESCE(SUM(CASE WHEN LENGTH(src) > 6 AND LENGTH(dst) <= 6 THEN duration ELSE 0 END), 0) AS inbound_duration,
                    COALESCE(SUM(duration), 0) AS total_duration,
                    COALESCE(SUM(billsec), 0) AS total_talktime
                FROM crm_cdr {where_str}
            """
            cursor.execute(count_query, query_params)
            cnt_row = cursor.fetchone() or {}
            total_records = int(cnt_row.get("total_count") or 0)

            kpis_summary = {
                "total_records": total_records,
                "outbound_count": int(cnt_row.get("outbound_count") or 0),
                "inbound_count": int(cnt_row.get("inbound_count") or 0),
                "outbound_talktime_fmt": format_seconds_to_hms(int(cnt_row.get("outbound_talktime") or 0)),
                "inbound_talktime_fmt": format_seconds_to_hms(int(cnt_row.get("inbound_talktime") or 0)),
                "outbound_duration_fmt": format_seconds_to_hms(int(cnt_row.get("outbound_duration") or 0)),
                "inbound_duration_fmt": format_seconds_to_hms(int(cnt_row.get("inbound_duration") or 0)),
                "total_duration_fmt": format_seconds_to_hms(int(cnt_row.get("total_duration") or 0)),
                "total_talktime_fmt": format_seconds_to_hms(int(cnt_row.get("total_talktime") or 0)),
            }

            data_query = f"""
                SELECT id, provider, calldate, clid, src, dst, dcontext, channel, dstchannel, 
                       duration, billsec, disposition, uniqueid, recordingfile, call_direction, extra_info
                FROM crm_cdr
                {where_str}
                ORDER BY calldate DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(data_query, query_params + [page_size, offset])
            raw_rows = cursor.fetchall() or []

            # In-Memory Enrichment
            crm_ext_map = fetch_crm_extension_agent_map()

            # Collect phones to batch query leads
            phone_candidates = set()
            for r in raw_rows:
                src_str = str(r["src"] or "").strip()
                dst_str = str(r["dst"] or "").strip()
                
                norm_src = normalize_phone_number(src_str)
                norm_dst = normalize_phone_number(dst_str)
                
                if len(norm_src) == 10:
                    phone_candidates.add(norm_src)
                if len(norm_dst) == 10:
                    phone_candidates.add(norm_dst)

            # Query CRM Leads map
            leads_phone_map = {}
            if phone_candidates:
                crm_conn = get_db_connection()
                try:
                    with crm_conn.cursor() as crm_cur:
                        ph_placeholders = ", ".join(["%s"] * len(phone_candidates))
                        crm_cur.execute(f"""
                            SELECT l.id, l.lead_uuid, l.name, l.mobile_number, l.lead_status, l.call_status, ls.status_name
                            FROM leads l
                            LEFT JOIN lead_statuses ls ON l.lead_status = ls.id
                            WHERE l.mobile_number IN ({ph_placeholders})
                        """, list(phone_candidates))
                        l_rows = crm_cur.fetchall() or []
                        for lr in l_rows:
                            mb = normalize_phone_number(lr["mobile_number"])
                            if mb:
                                leads_phone_map[mb] = {
                                    "lead_id": lr["id"],
                                    "lead_code": str(lr["id"]),
                                    "client_code": str(lr["id"]),
                                    "lead_uuid": lr["lead_uuid"],
                                    "lead_name": lr["name"],
                                    "lead_status": lr.get("status_name") or str(lr.get("lead_status") or "New Lead"),
                                    "call_status": int(lr.get("call_status") or 0),
                                }
                finally:
                    crm_conn.close()

            for idx, r in enumerate(raw_rows, 1):
                src_val = str(r["src"] or "").strip()
                dst_val = str(r["dst"] or "").strip()
                
                is_outbound = len(src_val) <= 6
                direction = "outgoing" if is_outbound else "inbound"
                
                ext_key = src_val if is_outbound else dst_val
                raw_phone = dst_val if is_outbound else src_val
                norm_phone = normalize_phone_number(raw_phone)
                phone_val = norm_phone or raw_phone

                # Masking logic matching central CRM helper
                if can_view_full_mobile:
                    display_phone = phone_val
                else:
                    if len(phone_val) <= 4:
                        display_phone = phone_val
                    else:
                        display_phone = "*" * (len(phone_val) - 4) + phone_val[-4:]

                # Agent details
                agent_info = crm_ext_map.get(ext_key, {})
                agent_name = agent_info.get("full_name") or f"Extension {ext_key}"
                designation_name = agent_info.get("designation_name") or ("Designation N/A" if agent_info.get("full_name") else "Unmapped Extension")
                is_mapped = bool(agent_info.get("full_name"))

                # Lead details
                lead_info = leads_phone_map.get(norm_phone, {})

                # Timings
                dur = int(r.get("duration") or 0)
                talk = int(r.get("billsec") or 0)
                ring = max(0, dur - talk)

                # Date formatting
                c_date = r.get("calldate")
                date_fmt = c_date.strftime("%d/%m/%Y %I:%M %p") if isinstance(c_date, (datetime.datetime, datetime.date)) else str(c_date)

                rec_file_raw = (r.get("recordingfile") or "").strip()
                has_rec = bool(rec_file_raw and rec_file_raw.lower() != "none")
                rec_filename = rec_file_raw.split("/")[-1] if has_rec else ""

                if has_rec:
                    if rec_file_raw.startswith("http://") or rec_file_raw.startswith("https://"):
                        rec_url = rec_file_raw
                    else:
                        rec_url = f"/api/calls/recording-stream/{rec_filename}"
                else:
                    rec_url = ""

                calls_list.append({
                    "row_num": offset + idx,
                    "id": r.get("id"),
                    "provider": r.get("provider") or "issabel",
                    "uniqueid": r.get("uniqueid") or "",
                    "calldate": str(c_date),
                    "calldate_fmt": date_fmt,
                    "direction": direction,
                    "extension": ext_key,
                    "phone_number": phone_val if can_view_full_mobile else display_phone,
                    "display_phone": display_phone,
                    "raw_phone": raw_phone if can_view_full_mobile else display_phone,
                    "can_click_to_call": can_click_to_call,
                    "agent_name": agent_name,
                    "designation_name": designation_name,
                    "is_mapped": is_mapped,
                    "user_uuid": agent_info.get("user_uuid") or "",
                    "lead_id": lead_info.get("lead_id"),
                    "lead_code": lead_info.get("lead_code") or (str(lead_info.get("lead_id")) if lead_info.get("lead_id") else ""),
                    "client_code": lead_info.get("client_code") or (str(lead_info.get("lead_id")) if lead_info.get("lead_id") else ""),
                    "lead_uuid": lead_info.get("lead_uuid") or "",
                    "lead_name": lead_info.get("lead_name") or "",
                    "lead_status": lead_info.get("lead_status") or "",
                    "call_status": int(lead_info.get("call_status") or 0),
                    "is_lead_match": bool(lead_info.get("lead_id")),
                    "disposition": str(r.get("disposition") or "UNKNOWN").upper(),
                    "duration_sec": dur,
                    "duration_fmt": format_seconds_to_hms(dur),
                    "talktime_sec": talk,
                    "talktime_fmt": format_seconds_to_hms(talk),
                    "ringtime_sec": ring,
                    "ringtime_fmt": format_seconds_to_hms(ring),
                    "has_recording": has_rec,
                    "recording_file": rec_filename,
                    "recording_url": rec_url,
                })

    finally:
        conn.close()

    total_pages = (total_records + page_size - 1) // page_size if total_records > 0 else 1

    return {
        "success": True,
        "calls": calls_list,
        "kpis": kpis_summary,
        "total_records": total_records,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
