import logging
import re
import secrets

import requests
import urllib3

from config import get_db_connection


urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)

call_logger = logging.getLogger("click_to_call")


# Normalize the destination mobile number.
def normalize_call_number(mobile_number):
    mobile_number = re.sub(
        r"\D",
        "",
        str(mobile_number or ""),
    )

    if (
        len(mobile_number) > 10
        and mobile_number.startswith("91")
    ):
        mobile_number = mobile_number[-10:]

    if len(mobile_number) != 10:
        raise ValueError(
            "A valid 10-digit mobile number is required."
        )

    return mobile_number


# Fetch the logged user's calling configuration.
def get_user_calling_config(user_uuid):
    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    u.id AS user_id,
                    u.user_uuid,
                    u.full_name,
                    u.click_to_call,
                    u.extension_id,

                    e.extension_number,
                    e.extension_password,
                    e.calling_api_id,

                    c.api_name,
                    c.api_link,
                    c.provider_type,
                    c.token_id,
                    c.default_did,
                    c.source_variable,
                    c.destination_variable

                FROM users u

                INNER JOIN extensions e
                    ON e.id = u.extension_id
                   AND e.status = 1

                INNER JOIN calling_apis c
                    ON c.id = e.calling_api_id
                   AND c.status = 1

                WHERE u.user_uuid = %s
                  AND u.status = 1

                LIMIT 1
            """, (user_uuid,))

            calling_config = cursor.fetchone()

    finally:
        conn.close()

    if not calling_config:
        raise ValueError(
            "Calling extension or calling API is not configured."
        )

    if int(
        calling_config.get("click_to_call") or 0
    ) != 1:
        raise ValueError(
            "Click to call is disabled for this user."
        )

    if not calling_config.get("extension_number"):
        raise ValueError(
            "Extension number is missing."
        )

    provider_type = (calling_config.get("provider_type") or "issabel").lower()
    if provider_type == "cloudconnect":
        if not calling_config.get("api_link"):
            calling_config["api_link"] = "https://crm2.cloud-connect.in/ccpl_api/v1.4/api/info/click2call"
        if not calling_config.get("extension_password"):
            raise ValueError(
                "Extension password is not configured for CloudConnect. Please update extension settings."
            )
        if not calling_config.get("token_id"):
            raise ValueError(
                "CloudConnect token_id is missing. Please update Calling API settings."
            )
    else:
        if not calling_config.get("api_link"):
            raise ValueError(
                "Calling API link is missing."
            )

        if not calling_config.get("source_variable"):
            raise ValueError(
                "Calling API source variable is missing."
            )

        if not calling_config.get("destination_variable"):
            raise ValueError(
                "Calling API destination variable is missing."
            )

    return calling_config


# Save the call history and mark the lead as called.
def save_call_history(
    user_uuid,
    lead_uuid,
    calling_config,
    destination_number,
    response=None,
    api_status_code=None,
    api_response=None,
    final_api_url=None,
):
    call_history_uuid = (
        f"CALL{secrets.token_hex(6).upper()}"
    )

    status_code = api_status_code if api_status_code is not None else (response.status_code if response else 200)
    resp_text = api_response if api_response is not None else (response.text[:2000] if response else "")
    final_url = final_api_url if final_api_url is not None else (response.url if response else "")

    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    l.id AS lead_id,
                    u.id AS user_id

                FROM leads l

                INNER JOIN users u
                    ON u.user_uuid = %s

                WHERE l.lead_uuid = %s

                LIMIT 1
            """, (
                user_uuid,
                lead_uuid,
            ))

            mapping = cursor.fetchone()

            if not mapping:
                raise ValueError(
                    "Lead or user mapping was not found."
                )

            cursor.execute("""
                UPDATE leads
                SET
                    call_status = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                mapping["lead_id"],
            ))

            cursor.execute("""
                INSERT INTO lead_call_history (
                    call_history_uuid,
                    lead_id,
                    user_id,
                    extension_id,
                    calling_api_id,
                    extension_number,
                    mobile_number,
                    call_direction,
                    call_status,
                    api_status_code,
                    api_response,
                    final_api_url
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
                    %s
                )
            """, (
                call_history_uuid,
                mapping["lead_id"],
                mapping["user_id"],
                calling_config.get("extension_id"),
                calling_config.get("calling_api_id"),
                str(
                    calling_config.get(
                        "extension_number"
                    ) or ""
                ),
                destination_number,
                "outgoing",
                "initiated",
                status_code,
                resp_text,
                final_url,
            ))

            # Record in unified crm_cdr table
            try:
                prov = str(calling_config.get("provider_type") or "issabel").lower()
                cursor.execute("""
                    INSERT INTO crm_cdr (
                        provider, uniqueid, calldate, src, dst,
                        duration, billsec, disposition, call_direction, extra_info
                    )
                    VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, 0, 0, 'INITIATED', 'outbound', %s)
                    ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP
                """, (
                    prov,
                    call_history_uuid,
                    str(calling_config.get("extension_number") or ""),
                    destination_number,
                    resp_text[:500] if resp_text else "Initiated via CRM",
                ))
            except Exception as cdr_err:
                call_logger.warning("Error saving to crm_cdr in save_call_history: %s", cdr_err)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return call_history_uuid


# Trigger the mapped calling API.
def trigger_click_to_call(
    user_uuid,
    lead_uuid,
    destination_number,
    timeout=5,
):
    calling_config = get_user_calling_config(
        user_uuid
    )

    extension_number = str(
        calling_config["extension_number"]
    ).strip()

    provider_type = str(calling_config.get("provider_type") or "issabel").lower()

    # ==========================================
    # 1. CloudConnect Provider Branch
    # ==========================================
    if provider_type == "cloudconnect":
        from utils.cloudconnect import initiate_cloudconnect_call
        token_id = str(calling_config.get("token_id") or "").strip()
        ext_password = str(calling_config.get("extension_password") or "").strip()
        api_link = str(calling_config.get("api_link") or "").strip()

        call_logger.info(
            "CLOUDCONNECT CALL REQUEST | user=%s | lead=%s | extension=%s | destination=%s",
            user_uuid,
            lead_uuid,
            extension_number,
            destination_number,
        )

        cc_res = initiate_cloudconnect_call(
            token_id=token_id,
            extension_number=extension_number,
            extension_password=ext_password,
            phone_number=destination_number,
            api_link=api_link,
            timeout=timeout,
        )

        api_status_code = cc_res.get("status_code") or (200 if cc_res.get("success") else 400)
        api_response_text = cc_res.get("raw_response") or cc_res.get("message") or ""
        final_url = api_link or "https://crm2.cloud-connect.in/ccpl_api/v1.4/api/info/click2call"
        unique_token = cc_res.get("unique_token") or cc_res.get("data") or ""

        call_history_uuid = save_call_history(
            user_uuid=user_uuid,
            lead_uuid=lead_uuid,
            calling_config=calling_config,
            destination_number=destination_number,
            api_status_code=api_status_code,
            api_response=api_response_text,
            final_api_url=final_url,
        )

        # Upsert into unified crm_cdr with unique_token
        if unique_token:
            try:
                conn_cc = get_db_connection()
                with conn_cc.cursor() as cur_cc:
                    cur_cc.execute("""
                        INSERT INTO crm_cdr (
                            provider, uniqueid, calldate, src, dst, duration, billsec,
                            disposition, call_direction, extra_info
                        )
                        VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, 0, 0, 'INITIATED', 'outbound', %s)
                        ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP
                    """, (
                        "cloudconnect",
                        unique_token,
                        extension_number,
                        destination_number,
                        api_response_text[:500],
                    ))
                conn_cc.commit()
                conn_cc.close()
            except Exception as e:
                call_logger.warning("Error saving CC crm_cdr: %s", e)

        return {
            "success": cc_res.get("success", False),
            "call_history_uuid": call_history_uuid,
            "unique_token": unique_token,
            "message": cc_res.get("message") or "Call initiated to extension",
        }

    # ==========================================
    # 2. Asterisk / Issabel Provider Branch
    # ==========================================
    api_link = str(
        calling_config["api_link"]
    ).strip()

    source_variable = str(
        calling_config["source_variable"]
    ).strip()

    destination_variable = str(
        calling_config["destination_variable"]
    ).strip()

    api_params = {
        source_variable: extension_number,
        destination_variable: destination_number,
    }

    sep = "&" if "?" in api_link else "?"
    final_url = f"{api_link}{sep}{source_variable}={extension_number}&{destination_variable}={destination_number}"

    call_logger.info(
        (
            "CALL REQUEST | "
            "user=%s | "
            "lead=%s | "
            "extension=%s | "
            "destination=%s | "
            "final_url=%s"
        ),
        user_uuid,
        lead_uuid,
        extension_number,
        destination_number,
        final_url,
    )

    api_status_code = 200
    api_response_text = "API triggered"
    is_client_trigger = False

    # Check if host is a local/private network IP (e.g. 192.168.x.x, 10.x.x.x, 172.16-31.x.x, 127.0.0.1, localhost)
    is_private_ip = bool(
        re.search(
            r"//(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|127\.0\.0\.1|localhost)",
            api_link,
        )
    )
    effective_timeout = 2.0 if is_private_ip else timeout

    try:
        response = requests.get(
            api_link,
            params=api_params,
            timeout=effective_timeout,
            verify=False,
        )
        api_status_code = response.status_code
        api_response_text = response.text[:2000]
        if api_status_code not in [200, 201, 202, 204]:
            is_client_trigger = True

    except Exception as error:
        call_logger.warning(
            "Server-side call to %s failed: %s. Relying on client trigger.",
            final_url,
            error,
        )
        api_status_code = 0
        api_response_text = f"Connection attempt note: {str(error)}"
        is_client_trigger = True

    call_history_uuid = save_call_history(
        user_uuid=user_uuid,
        lead_uuid=lead_uuid,
        calling_config=calling_config,
        destination_number=destination_number,
        api_status_code=api_status_code,
        api_response=api_response_text,
        final_api_url=final_url,
    )

    server_hit_status = "SUCCESS" if api_status_code in [200, 201, 202, 204] else "FAILED"

    return {
        "success": True,
        "call_history_uuid": call_history_uuid,
        "message": "Initiating call...",
        "target_url": final_url,
        "client_call_url": final_url if is_client_trigger else None,
        "server_hit_status": server_hit_status,
        "server_status_code": api_status_code,
        "server_response": api_response_text,
        "is_private_ip": is_private_ip,
    }


def trigger_call_supervision(
    supervisor_uuid,
    agent_user_uuid=None,
    agent_extension=None,
    mode="listen",
    timeout=5,
):
    """
    Triggers live telephony call supervision (Listen / Whisper / Barge) via Asterisk / Calling API.
    """
    supervisor_config = get_user_calling_config(supervisor_uuid)
    sup_ext = str(supervisor_config.get("extension_number") or "").strip()

    conn = get_db_connection()
    target_ext = ""
    agent_name = ""
    try:
        with conn.cursor() as cursor:
            if agent_user_uuid:
                cursor.execute("""
                    SELECT u.id, u.full_name, e.extension_number
                    FROM users u
                    LEFT JOIN extensions e ON e.id = u.extension_id
                    WHERE u.user_uuid = %s LIMIT 1
                """, (agent_user_uuid,))
                agent_row = cursor.fetchone()
                if not agent_row or not agent_row.get("extension_number"):
                    raise ValueError("This team member does not have an active extension number assigned.")
                target_ext = str(agent_row["extension_number"]).strip()
                agent_name = agent_row.get("full_name") or target_ext
            elif agent_extension:
                target_ext = str(agent_extension).strip()
                agent_name = f"Extension {target_ext}"
            else:
                raise ValueError("Target extension is required.")
    finally:
        conn.close()

    api_link = str(supervisor_config.get("api_link") or "").strip()
    source_var = str(supervisor_config.get("source_variable") or "from").strip()
    dest_var = str(supervisor_config.get("destination_variable") or "to").strip()

    mode_prefix_map = {
        "listen": "*562",
        "whisper": "*564",
        "barge": "*566",
        "conference": "*566",
        "merge": "*566",
    }
    mode_action_map = {
        "listen": "listen",
        "whisper": "whisper",
        "barge": "barge",
        "conference": "barge",
        "merge": "barge",
    }
    action_type = mode_action_map.get(str(mode).lower(), "listen")
    prefix = mode_prefix_map.get(action_type, "*562")
    dial_destination = f"{prefix}{target_ext}"

    api_params = {
        source_var: sup_ext,
        dest_var: dial_destination,
    }

    sep = "&" if "?" in api_link else "?"
    final_url = f"{api_link}{sep}{source_var}={sup_ext}&{dest_var}={dial_destination}"

    call_logger.info(
        "SUPERVISION REQUEST | supervisor=%s | target=%s | dial_dest=%s | mode=%s | final_url=%s",
        sup_ext, target_ext, dial_destination, action_type, final_url
    )

    api_status_code = 200
    api_response_text = "Supervision triggered"

    try:
        response = requests.get(
            api_link,
            params=api_params,
            timeout=timeout,
            verify=False,
        )
        api_status_code = response.status_code
        api_response_text = response.text[:2000]
    except Exception as error:
        call_logger.warning("Supervision request error to %s: %s", final_url, error)
        api_status_code = 0
        api_response_text = str(error)

    mode_label = "Listening to" if action_type == "listen" else ("Whispering to" if action_type == "whisper" else "Joined Call with")
    return {
        "success": True,
        "message": f"{mode_label} {agent_name} (Dialing {dial_destination}). Your extension ({sup_ext}) is connecting...",
        "supervisor_extension": sup_ext,
        "agent_extension": target_ext,
        "dial_destination": dial_destination,
        "mode": action_type,
        "api_response": api_response_text,
    }