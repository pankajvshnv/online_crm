import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import render_template, request, session, redirect, url_for, flash, jsonify
from config import get_db_connection
from utils.permissions import require_permission, calculate_presence_status, update_user_last_active


ALLOWED_CHAT_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "csv", "txt",
    "jpg", "jpeg", "png", "webp", "gif"
}
MAX_CHAT_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def is_allowed_chat_file(filename):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_CHAT_EXTENSIONS


def chat_routes(app):

    @app.route("/chat", endpoint="chat_home")
    @require_permission("chat", "view")
    def chat_home():
        # Standalone /chat page removed - Chat is integrated in the top header drawer
        return redirect(url_for("dashboard"))

    @app.route("/chat/api/users", methods=["GET", "POST"], endpoint="chat_api_users")
    @require_permission("chat", "view")
    def chat_api_users():
        user_info = session.get("user") or {}
        current_user_id = user_info.get("id")
        if not current_user_id:
            return jsonify({"success": False, "message": "Unauthenticated"}), 401

        update_user_last_active()
        search_query = request.args.get("search", "") or (request.get_json(silent=True) or {}).get("search", "")
        search_query = str(search_query).strip()

        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection error"}), 500

        users_list = []
        total_unread_count = 0
        try:
            with conn.cursor() as cursor:
                where_clause = " WHERE u.status = 1 AND u.id != %s"
                params = [
                    current_user_id,
                    current_user_id, current_user_id,
                    current_user_id, current_user_id,
                    current_user_id, current_user_id,
                    current_user_id
                ]

                if search_query:
                    where_clause += " AND (u.full_name LIKE %s OR u.username LIKE %s)"
                    search_like = f"%{search_query}%"
                    params.extend([search_like, search_like])

                sql = f"""
                    SELECT 
                        u.id,
                        u.user_uuid,
                        u.full_name,
                        u.last_active_at,
                        (
                            SELECT COUNT(*) 
                            FROM chat_messages m_unread 
                            WHERE m_unread.sender_user_id = u.id 
                              AND m_unread.receiver_user_id = %s 
                              AND m_unread.is_read = 0
                        ) AS unread_count,
                        (
                            SELECT m_last.created_at
                            FROM chat_messages m_last
                            WHERE (m_last.sender_user_id = %s AND m_last.receiver_user_id = u.id)
                               OR (m_last.sender_user_id = u.id AND m_last.receiver_user_id = %s)
                            ORDER BY m_last.id DESC LIMIT 1
                        ) AS last_msg_created_at,
                        (
                            SELECT m_last.message_text
                            FROM chat_messages m_last
                            WHERE (m_last.sender_user_id = %s AND m_last.receiver_user_id = u.id)
                               OR (m_last.sender_user_id = u.id AND m_last.receiver_user_id = %s)
                            ORDER BY m_last.id DESC LIMIT 1
                        ) AS last_msg_text,
                        (
                            SELECT m_last.sender_user_id
                            FROM chat_messages m_last
                            WHERE (m_last.sender_user_id = %s AND m_last.receiver_user_id = u.id)
                               OR (m_last.sender_user_id = u.id AND m_last.receiver_user_id = %s)
                            ORDER BY m_last.id DESC LIMIT 1
                        ) AS last_msg_sender_id
                    FROM users u
                    {where_clause}
                """
                cursor.execute(sql, params)
                rows = cursor.fetchall() or []

                now = datetime.now()
                for r in rows:
                    presence = calculate_presence_status(r.get("last_active_at"))
                    unread_count = r.get("unread_count") or 0
                    total_unread_count += unread_count

                    last_msg_text = ""
                    last_msg_time = ""
                    c_at = r.get("last_msg_created_at")

                    if r.get("last_msg_text"):
                        prefix = "You: " if r.get("last_msg_sender_id") == current_user_id else ""
                        last_msg_text = prefix + (r.get("last_msg_text") or "")
                        if isinstance(c_at, datetime):
                            if c_at.date() == now.date():
                                last_msg_time = c_at.strftime("%I:%M %p")
                            elif (now.date() - c_at.date()).days == 1:
                                last_msg_time = "Yesterday"
                            else:
                                last_msg_time = c_at.strftime("%d %b")
                        elif c_at:
                            last_msg_time = str(c_at)[11:16]

                    users_list.append({
                        "uuid": r["user_uuid"],
                        "full_name": r["full_name"],
                        "presence": presence,
                        "unread_count": unread_count,
                        "last_msg_text": last_msg_text,
                        "last_msg_time": last_msg_time,
                        "_sort_dt": c_at
                    })

                # Sort:
                # 1. Users with active conversation first (most recent message at the very top)
                # 2. Users without messages sorted by presence: Online (1) -> Idle (2) -> Offline (3)
                # 3. Alphabetical by full_name
                def get_sort_key(u):
                    dt = u.get("_sort_dt")
                    has_chat = 1 if dt is not None else 0
                    epoch = dt.timestamp() if isinstance(dt, datetime) else 0
                    presence_order = u["presence"].get("order", 3)
                    name = (u.get("full_name") or "").lower()
                    return (0 if has_chat else 1, -epoch if has_chat else presence_order, name)

                users_list.sort(key=get_sort_key)

                # Remove internal sort keys
                for u in users_list:
                    u.pop("_sort_dt", None)

        except Exception as e:
            print("Error in chat_api_users:", e)
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "users": users_list,
            "total_unread_count": total_unread_count
        }), 200

    @app.route("/chat/api/messages", methods=["GET", "POST"], endpoint="chat_api_messages")
    @require_permission("chat", "view")
    def chat_api_messages():
        user_info = session.get("user") or {}
        current_user_id = user_info.get("id")
        if not current_user_id:
            return jsonify({"success": False, "message": "Unauthenticated"}), 401

        payload = request.get_json(silent=True) or request.form or request.args or {}
        receiver_key = payload.get("receiver_uuid") or payload.get("user_uuid") or payload.get("receiver_id")
        before_key = payload.get("before_uuid") or payload.get("before_id")
        limit = payload.get("limit", 50)

        if not receiver_key:
            return jsonify({"success": False, "message": "Receiver is required"}), 400

        try:
            limit = min(max(int(limit), 10), 100)
        except (ValueError, TypeError):
            limit = 50

        update_user_last_active()

        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection error"}), 500

        messages_list = []
        receiver_info = {}
        has_more = False

        try:
            with conn.cursor() as cursor:
                # Fetch receiver details by UUID or ID
                cursor.execute("""
                    SELECT u.id, u.user_uuid, u.full_name, u.last_active_at
                    FROM users u
                    WHERE (u.user_uuid = %s OR u.id = %s) LIMIT 1
                """, (receiver_key, receiver_key if str(receiver_key).isdigit() else -1))
                rec_row = cursor.fetchone()
                if not rec_row:
                    return jsonify({"success": False, "message": "Receiver not found"}), 404

                receiver_id = rec_row["id"]
                receiver_uuid = rec_row["user_uuid"]

                receiver_info = {
                    "uuid": receiver_uuid,
                    "full_name": rec_row["full_name"],
                    "presence": calculate_presence_status(rec_row.get("last_active_at"))
                }

                # Resolve before_id from before_uuid if provided
                before_id = None
                if before_key:
                    cursor.execute("""
                        SELECT id FROM chat_messages 
                        WHERE chat_uuid = %s OR id = %s LIMIT 1
                    """, (before_key, before_key if str(before_key).isdigit() else -1))
                    before_row = cursor.fetchone()
                    if before_row:
                        before_id = before_row["id"]

                # Mark incoming unread messages as read (only if viewing latest)
                if not before_id:
                    cursor.execute("""
                        UPDATE chat_messages
                        SET is_read = 1
                        WHERE sender_user_id = %s AND receiver_user_id = %s AND is_read = 0
                    """, (receiver_id, current_user_id))
                    conn.commit()

                # Fetch conversation messages (max 50 rows descending, then reverse)
                if before_id:
                    sql = """
                        SELECT 
                            m.id,
                            m.chat_uuid,
                            m.sender_user_id,
                            m.receiver_user_id,
                            m.message_text,
                            m.attachment_path,
                            m.is_read,
                            m.created_at,
                            u.full_name AS sender_name
                        FROM chat_messages m
                        JOIN users u ON u.id = m.sender_user_id
                        WHERE ((m.sender_user_id = %s AND m.receiver_user_id = %s)
                           OR (m.sender_user_id = %s AND m.receiver_user_id = %s))
                          AND m.id < %s
                        ORDER BY m.id DESC
                        LIMIT %s
                    """
                    cursor.execute(sql, (current_user_id, receiver_id, receiver_id, current_user_id, before_id, limit))
                else:
                    sql = """
                        SELECT 
                            m.id,
                            m.chat_uuid,
                            m.sender_user_id,
                            m.receiver_user_id,
                            m.message_text,
                            m.attachment_path,
                            m.is_read,
                            m.created_at,
                            u.full_name AS sender_name
                        FROM chat_messages m
                        JOIN users u ON u.id = m.sender_user_id
                        WHERE (m.sender_user_id = %s AND m.receiver_user_id = %s)
                           OR (m.sender_user_id = %s AND m.receiver_user_id = %s)
                        ORDER BY m.id DESC
                        LIMIT %s
                    """
                    cursor.execute(sql, (current_user_id, receiver_id, receiver_id, current_user_id, limit))

                rows = cursor.fetchall() or []
                has_more = (len(rows) == limit)

                # Reverse to chronological order (oldest to newest in this batch)
                rows = list(reversed(rows))

                for r in rows:
                    c_at = r.get("created_at")
                    time_fmt = ""
                    if isinstance(c_at, datetime):
                        time_fmt = c_at.strftime("%I:%M %p")
                    elif c_at:
                        time_fmt = str(c_at)[11:16]

                    messages_list.append({
                        "uuid": r["chat_uuid"],
                        "is_self": r["sender_user_id"] == current_user_id,
                        "sender_name": r["sender_name"],
                        "message_text": r["message_text"],
                        "attachment_path": r["attachment_path"],
                        "attachment_name": os.path.basename(r["attachment_path"]) if r["attachment_path"] else "",
                        "is_read": int(r.get("is_read") or 0),
                        "time_fmt": time_fmt
                    })

        except Exception as e:
            print("Error in chat_api_messages:", e)
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()

        oldest_uuid = messages_list[0]["uuid"] if messages_list else None
        newest_uuid = messages_list[-1]["uuid"] if messages_list else None

        return jsonify({
            "success": True,
            "receiver": receiver_info,
            "messages": messages_list,
            "has_more": has_more,
            "oldest_uuid": oldest_uuid,
            "newest_uuid": newest_uuid,
            "count": len(messages_list)
        }), 200

    @app.route("/chat/api/send", methods=["POST"], endpoint="chat_api_send")
    @require_permission("chat", "view")
    def chat_api_send():
        user_info = session.get("user") or {}
        current_user_id = user_info.get("id")
        if not current_user_id:
            return jsonify({"success": False, "message": "Unauthenticated"}), 401

        receiver_key = request.form.get("receiver_uuid") or request.form.get("user_uuid") or request.form.get("receiver_id")
        message_text = str(request.form.get("message_text") or "").strip()
        attachment_file = request.files.get("attachment")

        if not receiver_key:
            return jsonify({"success": False, "message": "Receiver is required"}), 400

        if not message_text and not attachment_file:
            return jsonify({"success": False, "message": "Cannot send empty message"}), 400

        attachment_path = None
        if attachment_file and attachment_file.filename:
            fname = attachment_file.filename
            if not is_allowed_chat_file(fname):
                return jsonify({
                    "success": False,
                    "message": "Invalid file type. Only documents (PDF, Word, Excel, CSV, TXT) and images are allowed."
                }), 400

            # Check file size (5MB limit)
            attachment_file.seek(0, os.SEEK_END)
            file_size = attachment_file.tell()
            attachment_file.seek(0)
            if file_size > MAX_CHAT_FILE_SIZE:
                return jsonify({
                    "success": False,
                    "message": "File size exceeds 5MB limit. Please select a smaller file."
                }), 400

            upload_dir = os.path.join(app.root_path, "static", "uploads", "chat")
            os.makedirs(upload_dir, exist_ok=True)
            safe_fname = secure_filename(fname)
            unique_fname = f"{uuid.uuid4().hex[:8]}_{safe_fname}"
            full_path = os.path.join(upload_dir, unique_fname)
            attachment_file.save(full_path)
            attachment_path = f"/static/uploads/chat/{unique_fname}"

        update_user_last_active()

        conn = get_db_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection error"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, user_uuid FROM users 
                    WHERE (user_uuid = %s OR id = %s) LIMIT 1
                """, (receiver_key, receiver_key if str(receiver_key).isdigit() else -1))
                rec_row = cursor.fetchone()
                if not rec_row:
                    return jsonify({"success": False, "message": "Receiver not found"}), 404

                receiver_id = rec_row["id"]
                chat_uuid = f"MSG_{uuid.uuid4().hex[:12].upper()}"

                cursor.execute("""
                    INSERT INTO chat_messages (
                        chat_uuid, sender_user_id, receiver_user_id, message_text, attachment_path, is_read, created_at
                    ) VALUES (%s, %s, %s, %s, %s, 0, NOW())
                """, (chat_uuid, current_user_id, receiver_id, message_text or "Attachment", attachment_path))
                conn.commit()

            return jsonify({
                "success": True,
                "message": "Message sent successfully",
                "message_uuid": chat_uuid
            }), 200

        except Exception as e:
            print("Error in chat_api_send:", e)
            return jsonify({"success": False, "message": str(e)}), 500
        finally:
            conn.close()
