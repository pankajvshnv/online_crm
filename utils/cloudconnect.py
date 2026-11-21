import datetime
import hashlib
import json
import logging
import re
import requests
import urllib3
from config import get_db_connection

urllib3.disable_warnings()
logger = logging.getLogger("cloudconnect")

DEFAULT_CLICK2CALL_URL = "https://crm2.cloud-connect.in/ccpl_api/v1.4/api/info/click2call"
DEFAULT_BASE_URL = "https://crm2.cloud-connect.in"


def normalize_phone_10_digits(raw_num):
    """Normalizes phone number to 10 digits."""
    if not raw_num:
        return ""
    digits = re.sub(r"\D", "", str(raw_num).strip())
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    elif len(digits) > 10 and digits.startswith("0"):
        digits = digits[-10:]
    elif len(digits) > 10:
        digits = digits[-10:]
    return digits


def initiate_cloudconnect_call(
    token_id,
    extension_number,
    extension_password,
    phone_number,
    api_link=None,
    timeout=6,
):
    """
    Triggers CloudConnect Click-to-Call Outbound Dialing API.
    Docs:
      URL: https://crm2.cloud-connect.in/ccpl_api/v1.4/api/info/click2call
      Method: POST (Content-Type: application/json)
      Params: token_id, extension_number, extension_password (MD5), phone_number
    """
    clean_phone = normalize_phone_10_digits(phone_number)
    if not clean_phone or len(clean_phone) != 10:
        return {
            "success": False,
            "message": "Invalid 10-digit mobile number.",
            "status_code": 400,
            "response": None,
        }

    ext_num_str = str(extension_number or "").strip()
    if not ext_num_str:
        return {
            "success": False,
            "message": "Extension number is required.",
            "status_code": 400,
            "response": None,
        }

    raw_pwd = str(extension_password or "").strip()
    if not raw_pwd:
        return {
            "success": False,
            "message": "Extension password is required for CloudConnect.",
            "status_code": 400,
            "response": None,
        }

    # MD5 hash of extension web password as per CloudConnect documentation
    md5_password = hashlib.md5(raw_pwd.encode("utf-8")).hexdigest()

    endpoint = (api_link or "").strip() or DEFAULT_CLICK2CALL_URL

    payload = {
        "token_id": str(token_id or "").strip(),
        "extension_number": ext_num_str,
        "extension_password": md5_password,
        "phone_number": clean_phone,
    }

    logger.info(
        "CloudConnect Click2Call Outbound Request -> Ext: %s, Destination: %s, Endpoint: %s",
        ext_num_str,
        clean_phone,
        endpoint,
    )

    try:
        res = requests.post(
            endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
            verify=False,
        )
        status_code = res.status_code
        resp_json = None
        try:
            resp_json = res.json()
        except Exception:
            resp_json = {"raw": res.text[:2000]}

        is_success = False
        msg = "Call triggered"
        unique_token = ""
        call_data_id = ""

        if isinstance(resp_json, dict):
            status_val = str(resp_json.get("status") or "").upper()
            code_val = str(resp_json.get("code") or "")
            msg = resp_json.get("message") or msg
            unique_token = str(resp_json.get("unique_token") or "")
            call_data_id = str(resp_json.get("data") or "")

            if status_val == "SUCCESS" or code_val in ["200", "201"] or status_code == 200:
                is_success = True
            else:
                is_success = False

        return {
            "success": is_success,
            "message": msg,
            "status_code": status_code,
            "data": call_data_id,
            "unique_token": unique_token,
            "raw_response": res.text[:2000],
            "response_json": resp_json,
        }

    except Exception as exc:
        logger.error("CloudConnect call request exception: %s", exc)
        return {
            "success": False,
            "message": f"CloudConnect connection error: {str(exc)}",
            "status_code": 0,
            "data": "",
            "unique_token": "",
            "raw_response": str(exc),
            "response_json": {},
        }


def fetch_cloudconnect_call_logs(
    token_id,
    start_date=None,
    end_date=None,
    base_url=None,
    user_type="Tenant",
    number=None,
    unique_token=None,
    timeout=10,
):
    """
    Fetches call log details from CloudConnect API:
    POST https://crm2.cloud-connect.in/ccpl_api/v1.4/api/info/{startDate}/{endDate}/{userType}/callLog
    Date format: YYYY-MM-DD-HH:MM
    """
    now = datetime.datetime.now()
    if not start_date:
        start_str = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d-00:00")
    else:
        # Normalize start_date
        if len(start_date) == 10:
            start_str = f"{start_date}-00:00"
        else:
            start_str = start_date.replace(" ", "-")

    if not end_date:
        end_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d-23:59")
    else:
        if len(end_date) == 10:
            end_str = f"{end_date}-23:59"
        else:
            end_str = end_date.replace(" ", "-")

    base = (base_url or "").strip().rstrip("/") or DEFAULT_BASE_URL
    url = f"{base}/ccpl_api/v1.4/api/info/{start_str}/{end_str}/{user_type}/callLog"

    payload = {
        "token_id": str(token_id or "").strip(),
    }
    if number:
        payload["number"] = str(number).strip()
    if unique_token:
        payload["unique_token"] = str(unique_token).strip()

    logger.info("Fetching CloudConnect Call Logs from URL: %s", url)

    try:
        res = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
            verify=False,
        )
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict) and data.get("status") == "SUCCESS":
                return data.get("data") or []
        else:
            logger.warning("CloudConnect CallLog API returned status %s: %s", res.status_code, res.text[:500])
    except Exception as exc:
        logger.error("Error fetching CloudConnect call logs: %s", exc)

    return []


def sync_cloudconnect_cdr_to_db(calling_api_row=None, start_date=None, end_date=None):
    """
    Fetches call logs from CloudConnect and upserts them into `crm_cdr`.
    """
    conn = get_db_connection()
    api_config = calling_api_row
    try:
        with conn.cursor() as cur:
            if not api_config:
                cur.execute("""
                    SELECT * FROM calling_apis
                    WHERE provider_type = 'cloudconnect' AND status = 1
                    ORDER BY id ASC LIMIT 1
                """)
                api_config = cur.fetchone()

        if not api_config:
            return 0

        token_id = api_config.get("token_id")
        if not token_id:
            logger.warning("No token_id found for CloudConnect calling API.")
            return 0

        logs = fetch_cloudconnect_call_logs(
            token_id=token_id,
            start_date=start_date,
            end_date=end_date,
            base_url=api_config.get("server_host") or DEFAULT_BASE_URL,
        )

        if not logs or not isinstance(logs, list):
            return 0

        synced_count = 0
        with conn.cursor() as cur:
            for item in logs:
                callid = str(item.get("callid") or item.get("unique_token") or item.get("data") or "").strip()
                if not callid:
                    continue

                start_date_val = item.get("start_date") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                caller = str(item.get("caller") or "").strip()
                callee = str(item.get("callee") or "").strip()
                direction = str(item.get("call_direction") or "OUTBOUND").lower()

                call_sec = int(item.get("call_sec") or 0)
                answer_sec = int(item.get("answer_sec") or 0)
                call_status = str(item.get("call_status") or "").strip()

                if "answer" in call_status.lower():
                    disp = "ANSWERED"
                elif "busy" in call_status.lower():
                    disp = "BUSY"
                elif "fail" in call_status.lower():
                    disp = "FAILED"
                else:
                    disp = "NO ANSWER"

                rec_path = item.get("call_rec_path") or ""
                extra = json.dumps(item)

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
                        recordingfile = VALUES(recordingfile),
                        extra_info = VALUES(extra_info)
                """, (
                    "cloudconnect",
                    callid,
                    start_date_val,
                    caller,
                    callee,
                    call_sec,
                    answer_sec,
                    disp,
                    rec_path,
                    direction,
                    extra,
                ))
                synced_count += 1

            conn.commit()
            return synced_count

    except Exception as exc:
        logger.error("Error in sync_cloudconnect_cdr_to_db: %s", exc)
        return 0
    finally:
        conn.close()


def sync_issabel_cdr_to_db(server_config=None, days_back=30, limit=1000):
    """
    Pulls recent CDR records from remote Asterisk/Issabel PBX into local `crm_cdr` table.
    """
    from utils.calling_db import get_remote_calling_connection

    remote_conn, err = get_remote_calling_connection(server_config)
    if err or not remote_conn:
        logger.info("Issabel remote connection skipped/unavailable: %s", err)
        return 0

    crm_conn = get_db_connection()
    synced_count = 0
    try:
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
        with remote_conn.cursor() as r_cur:
            r_cur.execute("""
                SELECT calldate, clid, src, dst, dcontext, channel, dstchannel,
                       duration, billsec, disposition, uniqueid, userfield, recordingfile
                FROM cdr
                WHERE calldate >= %s
                ORDER BY calldate DESC
                LIMIT %s
            """, (cutoff, limit))
            remote_rows = r_cur.fetchall() or []

        if not remote_rows:
            return 0

        with crm_conn.cursor() as c_cur:
            for r in remote_rows:
                uniq = str(r.get("uniqueid") or "").strip()
                if not uniq:
                    continue

                src = str(r.get("src") or "").strip()
                dst = str(r.get("dst") or "").strip()
                direction = "outbound" if len(src) <= 6 else "inbound"

                c_cur.execute("""
                    INSERT INTO crm_cdr (
                        provider, uniqueid, calldate, src, dst, clid,
                        channel, dstchannel, dcontext, duration, billsec,
                        disposition, recordingfile, call_direction
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        duration = VALUES(duration),
                        billsec = VALUES(billsec),
                        disposition = VALUES(disposition),
                        recordingfile = VALUES(recordingfile)
                """, (
                    "issabel",
                    uniq,
                    r.get("calldate"),
                    src,
                    dst,
                    r.get("clid") or "",
                    r.get("channel") or "",
                    r.get("dstchannel") or "",
                    r.get("dcontext") or "",
                    int(r.get("duration") or 0),
                    int(r.get("billsec") or 0),
                    str(r.get("disposition") or "NO ANSWER"),
                    r.get("recordingfile") or "",
                    direction,
                ))
                synced_count += 1

            crm_conn.commit()

        return synced_count
    except Exception as exc:
        logger.error("Error syncing Issabel CDR to local DB: %s", exc)
        return 0
    finally:
        remote_conn.close()
        crm_conn.close()
