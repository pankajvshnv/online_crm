import secrets
from datetime import datetime
from config import get_db_connection
from flask import session, request


def create_user_session(user_id, user_uuid, username, ip_address=None, user_agent=None):
    """
    Creates a new active session record in the user_sessions table and stores
    the unique session_token in Flask session.
    """
    session_token = f"sess_{secrets.token_hex(24)}"

    if not ip_address:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        else:
            ip_address = request.headers.get("X-Real-IP", request.remote_addr or "")

    if not user_agent:
        user_agent = str(request.headers.get("User-Agent") or "")[:255]

    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO user_sessions (
                        session_token, user_id, user_uuid, username, ip_address, user_agent, is_active, created_at, expires_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, 1, NOW(), DATE_ADD(NOW(), INTERVAL 30 DAY))
                """, (session_token, user_id, user_uuid, username, ip_address, user_agent))
                conn.commit()
        except Exception as e:
            print("[SESSION] Error creating user_sessions entry:", e)
        finally:
            conn.close()

    session["session_token"] = session_token
    session["user_uuid"] = user_uuid
    return session_token


def terminate_user_session(session_token=None):
    """
    Marks the session as inactive (is_active = 0) in user_sessions table and clears Flask session.
    """
    token = session_token or session.get("session_token")
    if token:
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE user_sessions
                        SET is_active = 0
                        WHERE session_token = %s
                    """, (token,))
                    conn.commit()
            except Exception as e:
                print("[SESSION] Error terminating user session:", e)
            finally:
                conn.close()

    session.clear()


def validate_user_session(session_token, user_uuid):
    """
    Validates if session_token is active for the given user_uuid.
    Returns session dict if valid, None if invalid or expired.
    """
    if not session_token or not user_uuid:
        return None

    conn = get_db_connection()
    if not conn:
        return None

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, session_token, user_id, user_uuid, username, ip_address, is_active, created_at, last_activity
                FROM user_sessions
                WHERE session_token = %s AND user_uuid = %s AND is_active = 1
                LIMIT 1
            """, (session_token, user_uuid))
            sess = cursor.fetchone()
            if sess:
                return sess
    except Exception as e:
        print("[SESSION] Error validating user session:", e)
    finally:
        conn.close()

    return None
