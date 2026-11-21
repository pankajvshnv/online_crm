import datetime
import html
import logging
import os
import re
import secrets
import uuid

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from config import get_db_connection
from utils.permissions import require_permission, has_permission

email_logger = logging.getLogger("email_module")

MAX_EMAIL_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_EMAIL_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "csv", "txt", "jpg", "jpeg", "png", "webp", "gif"
}


def is_allowed_email_file(filename):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EMAIL_EXTENSIONS


def generate_email_uuid():
    return f"EML{secrets.token_hex(6).upper()}"


def format_display_recipients(name_str):
    """
    Formats multiple recipients for list display:
    e.g. 'Vijay Vaishnav and 20 more' if > 1 person.
    """
    if not name_str:
        return ""
    parts = [p.strip() for p in str(name_str).split(",") if p.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} and {len(parts) - 1} more"


def fetch_internal_users(cursor):
    """
    Fetches active CRM internal users for To, CC, and BCC recipient selection.
    """
    cursor.execute("""
        SELECT 
            u.id,
            u.user_uuid,
            u.full_name,
            u.username,
            COALESCE(d.designation_name, 'Member') AS designation_name
        FROM users u
        LEFT JOIN designations d ON d.id = u.designation_id
        WHERE u.status = 1
        ORDER BY u.full_name ASC
    """)
    return cursor.fetchall() or []


def fetch_recent_recipients(cursor, user_id, internal_users):
    """
    Fetches 5 recent unique internal user objects for the logged-in user.
    """
    user_by_username = {u["username"].lower(): u for u in internal_users}
    user_by_name = {u["full_name"].lower(): u for u in internal_users}

    recents = []
    seen_usernames = set()

    if user_id:
        cursor.execute("""
            SELECT recipient_email, recipient_name
            FROM emails
            WHERE user_id = %s AND folder = 'sent'
            ORDER BY id DESC
            LIMIT 20
        """, (user_id,))
        rows = cursor.fetchall() or []
        for r in rows:
            emails_str = r.get("recipient_email") or ""
            names_str = r.get("recipient_name") or ""
            tokens = [t.strip() for t in emails_str.split(",") if t.strip()] + [t.strip() for t in names_str.split(",") if t.strip()]
            for t in tokens:
                matched_user = user_by_username.get(t.lower()) or user_by_name.get(t.lower())
                if matched_user and matched_user["id"] != user_id:
                    uname = matched_user["username"].lower()
                    if uname not in seen_usernames:
                        recents.append(matched_user)
                        seen_usernames.add(uname)
                if len(recents) >= 5:
                    break
            if len(recents) >= 5:
                break

    # If fewer than 5 recents, fill with active internal users (excluding self)
    if len(recents) < 5:
        for u in internal_users:
            if u["id"] != user_id:
                uname = u["username"].lower()
                if uname not in seen_usernames:
                    recents.append(u)
                    seen_usernames.add(uname)
            if len(recents) >= 5:
                break

    return recents[:5]


def email_routes(app):

    @app.route("/email", methods=["GET"], endpoint="email_home")
    @app.route("/email/<folder_name>", methods=["GET"], endpoint="email_folder_page")
    def email_home(folder_name=None):
        flash("The Email module has been removed.", "info")
        return redirect(url_for("dashboard"))

        user_info = session.get("user") or {}
        user_id = user_info.get("id")

        raw_folder = (folder_name or request.args.get("folder") or "inbox").lower().strip()
        if raw_folder == "starred":
            raw_folder = "important"

        valid_folders = ["inbox", "important", "sent", "drafts", "trash", "compose"]
        if raw_folder not in valid_folders:
            raw_folder = "inbox"

        current_folder = raw_folder
        if current_folder == "compose" and not has_permission("email", "send"):
            flash("You do not have permission to compose emails.", "warning")
            return redirect(url_for("email_home", folder_name="inbox"))
        search_query = (request.args.get("q") or "").strip()
        search_scope = (request.args.get("scope") or "folder").lower().strip()
        page = max(1, int(request.args.get("page") or 1))
        per_page = max(5, min(100, int(request.args.get("per_page") or 10)))

        conn = get_db_connection()
        emails = []
        folder_counts = {
            "inbox": 0,
            "unread_inbox": 0,
            "important": 0,
            "sent": 0,
            "drafts": 0,
            "trash": 0,
        }
        total_emails = 0
        total_pages = 1
        internal_users = []
        recent_recipients = []

        try:
            with conn.cursor() as cursor:
                # 1. Fetch Internal Users and Recents
                internal_users = fetch_internal_users(cursor)
                recent_recipients = fetch_recent_recipients(cursor, user_id, internal_users)

                # 2. Fetch Live Folder Count Stats
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN folder = 'inbox' AND is_deleted = 0 THEN 1 ELSE 0 END) AS inbox_cnt,
                        SUM(CASE WHEN folder = 'inbox' AND is_read = 0 AND is_deleted = 0 THEN 1 ELSE 0 END) AS unread_inbox_cnt,
                        SUM(CASE WHEN is_starred = 1 AND is_deleted = 0 AND folder != 'trash' THEN 1 ELSE 0 END) AS important_cnt,
                        SUM(CASE WHEN folder = 'sent' AND is_deleted = 0 THEN 1 ELSE 0 END) AS sent_cnt,
                        SUM(CASE WHEN folder = 'sent' AND is_read = 0 AND is_deleted = 0 THEN 1 ELSE 0 END) AS unread_sent_cnt,
                        SUM(CASE WHEN folder = 'drafts' AND is_deleted = 0 THEN 1 ELSE 0 END) AS drafts_cnt,
                        SUM(CASE WHEN folder = 'trash' OR is_deleted = 1 THEN 1 ELSE 0 END) AS trash_cnt
                    FROM emails
                    WHERE (user_id = %s OR user_id IS NULL)
                """, (user_id,))
                stats_row = cursor.fetchone() or {}
                folder_counts["inbox"] = int(stats_row.get("inbox_cnt") or 0)
                folder_counts["unread_inbox"] = int(stats_row.get("unread_inbox_cnt") or 0)
                folder_counts["important"] = int(stats_row.get("important_cnt") or 0)
                folder_counts["sent"] = int(stats_row.get("sent_cnt") or 0)
                folder_counts["unread_sent"] = int(stats_row.get("unread_sent_cnt") or 0)
                folder_counts["drafts"] = int(stats_row.get("drafts_cnt") or 0)
                folder_counts["trash"] = int(stats_row.get("trash_cnt") or 0)

                # 3. Build Filter Query for active folder / search scope
                where_clauses = ["(user_id = %s OR user_id IS NULL)"]
                params = [user_id]

                if search_scope == "all" or current_folder == "all":
                    where_clauses.append("is_deleted = 0")
                elif current_folder == "important":
                    where_clauses.append("is_starred = 1 AND is_deleted = 0 AND folder != 'trash'")
                elif current_folder == "trash":
                    where_clauses.append("(folder = 'trash' OR is_deleted = 1)")
                elif current_folder != "compose":
                    where_clauses.append("folder = %s AND is_deleted = 0")
                    params.append(current_folder)

                if search_query:
                    search_words = [w.strip() for w in search_query.split() if w.strip()]
                    if search_words:
                        word_clauses = []
                        for w in search_words:
                            term = f"%{w}%"
                            word_clauses.append("""
                                (sender_name LIKE %s OR sender_email LIKE %s 
                                 OR recipient_name LIKE %s OR recipient_email LIKE %s 
                                 OR cc_email LIKE %s OR subject LIKE %s 
                                 OR body_plain LIKE %s OR body_html LIKE %s)
                            """)
                            params.extend([term] * 8)
                        where_clauses.append("(" + " AND ".join(word_clauses) + ")")

                if current_folder != "compose":
                    where_sql = " AND ".join(where_clauses)

                    cursor.execute(f"SELECT COUNT(*) AS cnt FROM emails WHERE {where_sql}", params)
                    total_emails = cursor.fetchone()["cnt"] or 0
                    total_pages = max(1, (total_emails + per_page - 1) // per_page)
                    if page > total_pages:
                        page = total_pages

                    offset = (page - 1) * per_page

                    cursor.execute(f"""
                        SELECT 
                            id,
                            email_uuid,
                            user_id,
                            sender_email,
                            sender_name,
                            recipient_email,
                            recipient_name,
                            cc_email,
                            subject,
                            body_html,
                            body_plain,
                            folder,
                            is_starred,
                            is_read,
                            created_at
                        FROM emails
                        WHERE {where_sql}
                        ORDER BY id DESC
                        LIMIT %s OFFSET %s
                    """, params + [per_page, offset])
                    raw_emails = cursor.fetchall() or []

                    for e in raw_emails:
                        created = e.get("created_at")
                        if isinstance(created, datetime.datetime):
                            now = datetime.datetime.now()
                            if created.date() == now.date():
                                time_str = created.strftime("%I:%M %p")
                            elif created.year == now.year:
                                time_str = created.strftime("%d %b")
                            else:
                                time_str = created.strftime("%d %b %Y")
                        else:
                            time_str = str(created or "")

                        preview = e.get("body_plain") or re.sub("<[^<]+?>", "", e.get("body_html") or "")
                        if len(preview) > 130:
                            preview = preview[:127] + "..."

                        emails.append({
                            "id": e["id"],
                            "email_uuid": e["email_uuid"],
                            "sender_email": e["sender_email"],
                            "sender_name": e["sender_name"] or e["sender_email"],
                            "recipient_email": e["recipient_email"],
                            "recipient_name": e["recipient_name"] or e["recipient_email"],
                            "recipient_name_formatted": format_display_recipients(e["recipient_name"] or e["recipient_email"]),
                            "subject": e["subject"],
                            "preview": preview,
                            "folder": e["folder"],
                            "is_starred": int(e.get("is_starred") or 0),
                            "is_read": int(e.get("is_read") or 0),
                            "time_str": time_str,
                            "created_at": str(created or ""),
                        })

        finally:
            conn.close()

        start_item = ((page - 1) * per_page) + 1 if total_emails > 0 else 0
        end_item = min(page * per_page, total_emails)

        return render_template(
            "email/email_home.html",
            emails=emails,
            current_folder=current_folder,
            folder_counts=folder_counts,
            search_query=search_query,
            page=page,
            total_pages=total_pages,
            total_emails=total_emails,
            per_page=per_page,
            start_item=start_item,
            end_item=end_item,
            internal_users=internal_users,
            recent_recipients=recent_recipients,
            active_group="email",
            active_page="email_home",
            page_title="Email",
        )

    @app.route("/api/email/list", methods=["GET", "POST"], endpoint="api_list_emails")
    @require_permission("email", "view")
    def api_list_emails():
        if not session.get("user_uuid"):
            return jsonify({"success": False, "message": "Login required"}), 401

        user_info = session.get("user") or {}
        user_id = user_info.get("id")

        payload = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict() or {}

        raw_folder = (payload.get("folder") or request.args.get("folder") or "inbox").lower().strip()
        if raw_folder == "starred":
            raw_folder = "important"

        valid_folders = ["inbox", "important", "sent", "drafts", "trash", "compose", "all"]
        if raw_folder not in valid_folders:
            raw_folder = "inbox"

        current_folder = raw_folder
        search_query = (payload.get("q") or request.args.get("q") or "").strip()
        search_scope = (payload.get("scope") or request.args.get("scope") or ("all" if search_query else "folder")).lower().strip()
        page = max(1, int(payload.get("page") or request.args.get("page") or 1))
        per_page = max(5, min(100, int(payload.get("per_page") or request.args.get("per_page") or 10)))

        conn = get_db_connection()
        emails = []
        folder_counts = {
            "inbox": 0,
            "unread_inbox": 0,
            "important": 0,
            "sent": 0,
            "drafts": 0,
            "trash": 0,
        }
        total_emails = 0
        total_pages = 1

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN folder = 'inbox' AND is_deleted = 0 THEN 1 ELSE 0 END) AS inbox_cnt,
                        SUM(CASE WHEN folder = 'inbox' AND is_read = 0 AND is_deleted = 0 THEN 1 ELSE 0 END) AS unread_inbox_cnt,
                        SUM(CASE WHEN is_starred = 1 AND is_deleted = 0 AND folder != 'trash' THEN 1 ELSE 0 END) AS important_cnt,
                        SUM(CASE WHEN folder = 'sent' AND is_deleted = 0 THEN 1 ELSE 0 END) AS sent_cnt,
                        SUM(CASE WHEN folder = 'sent' AND is_read = 0 AND is_deleted = 0 THEN 1 ELSE 0 END) AS unread_sent_cnt,
                        SUM(CASE WHEN folder = 'drafts' AND is_deleted = 0 THEN 1 ELSE 0 END) AS drafts_cnt,
                        SUM(CASE WHEN folder = 'trash' OR is_deleted = 1 THEN 1 ELSE 0 END) AS trash_cnt
                    FROM emails
                    WHERE (user_id = %s OR user_id IS NULL)
                """, (user_id,))
                stats_row = cursor.fetchone() or {}
                folder_counts["inbox"] = int(stats_row.get("inbox_cnt") or 0)
                folder_counts["unread_inbox"] = int(stats_row.get("unread_inbox_cnt") or 0)
                folder_counts["important"] = int(stats_row.get("important_cnt") or 0)
                folder_counts["sent"] = int(stats_row.get("sent_cnt") or 0)
                folder_counts["unread_sent"] = int(stats_row.get("unread_sent_cnt") or 0)
                folder_counts["drafts"] = int(stats_row.get("drafts_cnt") or 0)
                folder_counts["trash"] = int(stats_row.get("trash_cnt") or 0)

                where_clauses = ["(user_id = %s OR user_id IS NULL)"]
                params = [user_id]

                if search_scope == "all" or current_folder == "all":
                    where_clauses.append("is_deleted = 0")
                elif current_folder == "important":
                    where_clauses.append("is_starred = 1 AND is_deleted = 0 AND folder != 'trash'")
                elif current_folder == "trash":
                    where_clauses.append("(folder = 'trash' OR is_deleted = 1)")
                else:
                    where_clauses.append("folder = %s AND is_deleted = 0")
                    params.append(current_folder)

                if search_query:
                    search_words = [w.strip() for w in search_query.split() if w.strip()]
                    if search_words:
                        word_clauses = []
                        for w in search_words:
                            term = f"%{w}%"
                            word_clauses.append("""
                                (sender_name LIKE %s OR sender_email LIKE %s 
                                 OR recipient_name LIKE %s OR recipient_email LIKE %s 
                                 OR cc_email LIKE %s OR subject LIKE %s 
                                 OR body_plain LIKE %s OR body_html LIKE %s)
                            """)
                            params.extend([term] * 8)
                        where_clauses.append("(" + " AND ".join(word_clauses) + ")")

                where_sql = " AND ".join(where_clauses)

                cursor.execute(f"SELECT COUNT(*) AS cnt FROM emails WHERE {where_sql}", params)
                total_emails = cursor.fetchone()["cnt"] or 0
                total_pages = max(1, (total_emails + per_page - 1) // per_page)
                if page > total_pages:
                    page = total_pages

                offset = (page - 1) * per_page

                cursor.execute(f"""
                    SELECT 
                        id,
                        email_uuid,
                        user_id,
                        sender_email,
                        sender_name,
                        recipient_email,
                        recipient_name,
                        cc_email,
                        subject,
                        body_html,
                        body_plain,
                        folder,
                        is_starred,
                        is_read,
                        created_at
                    FROM emails
                    WHERE {where_sql}
                    ORDER BY id DESC
                    LIMIT %s OFFSET %s
                """, params + [per_page, offset])
                raw_emails = cursor.fetchall() or []

                for e in raw_emails:
                    created = e.get("created_at")
                    if isinstance(created, datetime.datetime):
                        now = datetime.datetime.now()
                        if created.date() == now.date():
                            time_str = created.strftime("%I:%M %p")
                        elif created.year == now.year:
                            time_str = created.strftime("%d %b")
                        else:
                            time_str = created.strftime("%d %b %Y")
                    else:
                        time_str = str(created or "")

                    preview = e.get("body_plain") or re.sub("<[^<]+?>", "", e.get("body_html") or "")
                    if len(preview) > 130:
                        preview = preview[:127] + "..."

                    emails.append({
                        "id": e["id"],
                        "email_uuid": e["email_uuid"],
                        "sender_email": e["sender_email"],
                        "sender_name": e["sender_name"] or e["sender_email"],
                        "recipient_email": e["recipient_email"],
                        "recipient_name": e["recipient_name"] or e["recipient_email"],
                        "recipient_name_formatted": format_display_recipients(e["recipient_name"] or e["recipient_email"]),
                        "subject": e["subject"],
                        "preview": preview,
                        "folder": e["folder"],
                        "is_starred": int(e.get("is_starred") or 0),
                        "is_read": int(e.get("is_read") or 0),
                        "time_str": time_str,
                        "created_at": str(created or ""),
                    })
        finally:
            conn.close()

        start_item = ((page - 1) * per_page) + 1 if total_emails > 0 else 0
        end_item = min(page * per_page, total_emails)

        return jsonify({
            "success": True,
            "emails": emails,
            "current_folder": current_folder,
            "folder_counts": folder_counts,
            "total_emails": total_emails,
            "page": page,
            "total_pages": total_pages,
            "start_item": start_item,
            "end_item": end_item,
        })

    @app.route("/api/email/live-sync", methods=["POST", "GET"], endpoint="api_live_sync_emails")
    @require_permission("email", "view")
    def api_live_sync_emails():
        if not session.get("user_uuid"):
            return jsonify({"success": False}), 401

        user_info = session.get("user") or {}
        user_id = user_info.get("id")

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN folder = 'inbox' AND is_deleted = 0 THEN 1 ELSE 0 END) AS inbox_cnt,
                        SUM(CASE WHEN folder = 'inbox' AND is_read = 0 AND is_deleted = 0 THEN 1 ELSE 0 END) AS unread_inbox_cnt,
                        SUM(CASE WHEN is_starred = 1 AND is_deleted = 0 AND folder != 'trash' THEN 1 ELSE 0 END) AS important_cnt,
                        SUM(CASE WHEN folder = 'sent' AND is_deleted = 0 THEN 1 ELSE 0 END) AS sent_cnt,
                        SUM(CASE WHEN folder = 'sent' AND is_read = 0 AND is_deleted = 0 THEN 1 ELSE 0 END) AS unread_sent_cnt,
                        SUM(CASE WHEN folder = 'drafts' AND is_deleted = 0 THEN 1 ELSE 0 END) AS drafts_cnt,
                        SUM(CASE WHEN folder = 'trash' OR is_deleted = 1 THEN 1 ELSE 0 END) AS trash_cnt
                    FROM emails
                    WHERE (user_id = %s OR user_id IS NULL)
                """, (user_id,))
                stats_row = cursor.fetchone() or {}
                folder_counts = {
                    "inbox": int(stats_row.get("inbox_cnt") or 0),
                    "unread_inbox": int(stats_row.get("unread_inbox_cnt") or 0),
                    "important": int(stats_row.get("important_cnt") or 0),
                    "sent": int(stats_row.get("sent_cnt") or 0),
                    "unread_sent": int(stats_row.get("unread_sent_cnt") or 0),
                    "drafts": int(stats_row.get("drafts_cnt") or 0),
                    "trash": int(stats_row.get("trash_cnt") or 0),
                }
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "folder_counts": folder_counts,
        })

    @app.route("/api/email/get/<email_uuid>", methods=["GET", "POST"], endpoint="api_get_email")
    @require_permission("email", "view")
    def api_get_email(email_uuid):
        if not session.get("user_uuid"):
            return jsonify({"success": False, "message": "Login required"}), 401

        user_info = session.get("user") or {}
        user_id = user_info.get("id")

        conn = get_db_connection()
        email_data = None
        folder_counts = {}
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        id,
                        email_uuid,
                        user_id,
                        sender_email,
                        sender_name,
                        recipient_email,
                        recipient_name,
                        cc_email,
                        bcc_email,
                        subject,
                        body_html,
                        body_plain,
                        folder,
                        is_starred,
                        is_read,
                        parent_email_id,
                        created_at
                    FROM emails
                    WHERE email_uuid = %s
                    LIMIT 1
                """, (email_uuid,))
                email_data = cursor.fetchone()

                if email_data and email_data["folder"] == 'inbox':
                    if not email_data["is_read"]:
                        cursor.execute("UPDATE emails SET is_read = 1 WHERE id = %s", (email_data["id"],))
                        conn.commit()
                        email_data["is_read"] = 1

                    # When recipient reads inbox email, mark parent sent email as read!
                    if email_data.get("parent_email_id"):
                        cursor.execute("UPDATE emails SET is_read = 1 WHERE id = %s", (email_data["parent_email_id"],))
                        conn.commit()

                # Fetch updated folder counts
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN folder = 'inbox' AND is_deleted = 0 THEN 1 ELSE 0 END) AS inbox_cnt,
                        SUM(CASE WHEN folder = 'inbox' AND is_read = 0 AND is_deleted = 0 THEN 1 ELSE 0 END) AS unread_inbox_cnt,
                        SUM(CASE WHEN is_starred = 1 AND is_deleted = 0 AND folder != 'trash' THEN 1 ELSE 0 END) AS important_cnt,
                        SUM(CASE WHEN folder = 'sent' AND is_deleted = 0 THEN 1 ELSE 0 END) AS sent_cnt,
                        SUM(CASE WHEN folder = 'sent' AND is_read = 0 AND is_deleted = 0 THEN 1 ELSE 0 END) AS unread_sent_cnt,
                        SUM(CASE WHEN folder = 'drafts' AND is_deleted = 0 THEN 1 ELSE 0 END) AS drafts_cnt,
                        SUM(CASE WHEN folder = 'trash' OR is_deleted = 1 THEN 1 ELSE 0 END) AS trash_cnt
                    FROM emails
                    WHERE (user_id = %s OR user_id IS NULL)
                """, (user_id,))
                stats_row = cursor.fetchone() or {}
                folder_counts = {
                    "inbox": int(stats_row.get("inbox_cnt") or 0),
                    "unread_inbox": int(stats_row.get("unread_inbox_cnt") or 0),
                    "important": int(stats_row.get("important_cnt") or 0),
                    "sent": int(stats_row.get("sent_cnt") or 0),
                    "unread_sent": int(stats_row.get("unread_sent_cnt") or 0),
                    "drafts": int(stats_row.get("drafts_cnt") or 0),
                    "trash": int(stats_row.get("trash_cnt") or 0),
                }
                # Fetch attachments
                cursor.execute("""
                    SELECT attachment_uuid, file_name, file_path, file_size, file_type
                    FROM email_attachments
                    WHERE email_id = %s OR email_uuid = %s
                """, (email_data["id"], email_data["email_uuid"]))
                email_attachments = cursor.fetchall() or []
        finally:
            conn.close()

        if not email_data:
            return jsonify({"success": False, "message": "Email not found"}), 404

        created = email_data["created_at"]
        date_formatted = created.strftime("%d %b %Y, %I:%M %p") if isinstance(created, datetime.datetime) else str(created)

        return jsonify({
            "success": True,
            "folder_counts": folder_counts,
            "email": {
                "id": email_data["id"],
                "email_uuid": email_data["email_uuid"],
                "sender_email": email_data["sender_email"],
                "sender_name": email_data["sender_name"] or email_data["sender_email"],
                "recipient_email": email_data["recipient_email"],
                "recipient_name": email_data["recipient_name"] or email_data["recipient_email"],
                "cc_email": email_data["cc_email"] or "",
                "bcc_email": email_data.get("bcc_email") or "",
                "subject": email_data["subject"],
                "body_html": email_data["body_html"] or f"<p>{email_data['body_plain'] or ''}</p>",
                "folder": email_data["folder"],
                "is_starred": int(email_data.get("is_starred") or 0),
                "is_read": int(email_data.get("is_read") or 0),
                "date_formatted": date_formatted,
                "attachments": email_attachments,
            }
        })

    @app.route("/api/email/send", methods=["POST"], endpoint="api_send_email")
    @require_permission("email", "send")
    def api_send_email():
        """
        100% Internal CRM Email Delivery (No external SMTP or network calls).
        Creates 'sent' record for sender and 'inbox' records for all recipients, CC, and BCC.
        Supports multiple file attachments (Max 5MB each).
        """
        user_uuid = session.get("user_uuid")
        if not user_uuid:
            return jsonify({"success": False, "message": "Login required"}), 401

        user_info = session.get("user") or {}
        sender_user_id = user_info.get("id")

        payload = request.get_json(silent=True) or request.form.to_dict() or {}
        to_recipients = payload.get("to_recipients") or payload.get("recipient_email") or ""
        cc_recipients = payload.get("cc_recipients") or payload.get("cc_email") or ""
        bcc_recipients = payload.get("bcc_recipients") or payload.get("bcc_email") or ""
        subject = (payload.get("subject") or "").strip()
        body_html = payload.get("body_html") or payload.get("body") or ""
        body_plain = re.sub("<[^<]+?>", "", body_html or "")

        if not to_recipients or not subject:
            return jsonify({"success": False, "message": "Please select a recipient and enter a subject."}), 400

        # Handle Attachments (Max 5MB each, multiple allowed)
        attachment_files = request.files.getlist("attachments") or request.files.getlist("attachment")
        saved_attachments = []

        for att_file in attachment_files:
            if att_file and att_file.filename:
                fname = att_file.filename
                if not is_allowed_email_file(fname):
                    return jsonify({
                        "success": False,
                        "message": f"Invalid file type for '{fname}'. Only documents (PDF, Word, Excel, CSV, TXT) and images are allowed."
                    }), 400

                att_file.seek(0, os.SEEK_END)
                fsize = att_file.tell()
                att_file.seek(0)
                if fsize > MAX_EMAIL_FILE_SIZE:
                    return jsonify({
                        "success": False,
                        "message": f"File '{fname}' exceeds the 5MB limit. Please select a smaller file."
                    }), 400

                upload_dir = os.path.join(app.root_path, "static", "uploads", "email")
                os.makedirs(upload_dir, exist_ok=True)
                safe_fname = secure_filename(fname)
                unique_fname = f"{uuid.uuid4().hex[:8]}_{safe_fname}"
                full_path = os.path.join(upload_dir, unique_fname)
                att_file.save(full_path)
                file_rel_path = f"/static/uploads/email/{unique_fname}"
                file_ext = fname.rsplit(".", 1)[1].lower() if "." in fname else ""

                saved_attachments.append({
                    "file_name": fname,
                    "file_path": file_rel_path,
                    "file_size": fsize,
                    "file_type": file_ext
                })

        # Parse comma-separated or list of user IDs / usernames
        def parse_recipient_tokens(val):
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
            return [t.strip() for t in str(val).split(",") if t.strip()]

        to_tokens = parse_recipient_tokens(to_recipients)
        cc_tokens = parse_recipient_tokens(cc_recipients)
        bcc_tokens = parse_recipient_tokens(bcc_recipients)

        conn = get_db_connection()
        email_uuid = generate_email_uuid()

        try:
            with conn.cursor() as cursor:
                # 1. Fetch Sender info
                cursor.execute("SELECT id, full_name, username FROM users WHERE user_uuid = %s LIMIT 1", (user_uuid,))
                sender_user = cursor.fetchone() or {"id": sender_user_id, "full_name": "Vijay Vaishnav", "username": "admin"}
                sender_name = sender_user["full_name"]
                sender_email = sender_user["username"]

                # 2. Fetch all internal users to resolve usernames & IDs
                cursor.execute("SELECT id, user_uuid, full_name, username FROM users WHERE status = 1")
                all_users = cursor.fetchall() or []
                user_by_id = {str(u["id"]): u for u in all_users}
                user_by_username = {u["username"].lower(): u for u in all_users}
                user_by_name = {u["full_name"].lower(): u for u in all_users}

                def resolve_user(token):
                    token_str = str(token).strip()
                    if token_str in user_by_id:
                        return user_by_id[token_str]
                    token_lower = token_str.lower()
                    if token_lower in user_by_username:
                        return user_by_username[token_lower]
                    if token_lower in user_by_name:
                        return user_by_name[token_lower]
                    return {"id": None, "full_name": token_str, "username": token_str}

                to_user_objs = [resolve_user(t) for t in to_tokens]
                cc_user_objs = [resolve_user(t) for t in cc_tokens]
                bcc_user_objs = [resolve_user(t) for t in bcc_tokens]

                to_names_str = ", ".join([u["full_name"] for u in to_user_objs])
                to_emails_str = ", ".join([u["username"] for u in to_user_objs])
                cc_names_str = ", ".join([u["full_name"] for u in cc_user_objs]) if cc_user_objs else None
                bcc_names_str = ", ".join([u["full_name"] for u in bcc_user_objs]) if bcc_user_objs else None

                # 3. Create Sent record for Sender (is_read = 0 until recipient reads)
                cursor.execute("""
                    INSERT INTO emails (
                        email_uuid,
                        user_id,
                        sender_email,
                        sender_name,
                        recipient_email,
                        recipient_name,
                        cc_email,
                        bcc_email,
                        subject,
                        body_html,
                        body_plain,
                        folder,
                        is_starred,
                        is_read,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'sent', 0, 0, NOW()
                    )
                """, (
                    email_uuid,
                    sender_user["id"],
                    sender_email,
                    sender_name,
                    to_emails_str,
                    to_names_str,
                    cc_names_str,
                    bcc_names_str,
                    subject,
                    body_html,
                    body_plain,
                ))
                sent_email_id = cursor.lastrowid

                # Save attachments for Sent record
                for att in saved_attachments:
                    att_uuid = f"ATT{uuid.uuid4().hex[:12].upper()}"
                    cursor.execute("""
                        INSERT INTO email_attachments (
                            attachment_uuid, email_id, email_uuid, file_name, file_path, file_size, file_type
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (att_uuid, sent_email_id, email_uuid, att["file_name"], att["file_path"], att["file_size"], att["file_type"]))

                all_inbox_records = []

                # 4. Create Inbox records for each To recipient
                for target_user in to_user_objs:
                    target_id = target_user.get("id")
                    if target_id and target_id != sender_user["id"]:
                        inbox_uuid = generate_email_uuid()
                        cursor.execute("""
                            INSERT INTO emails (
                                email_uuid,
                                user_id,
                                sender_email,
                                sender_name,
                                recipient_email,
                                recipient_name,
                                cc_email,
                                subject,
                                body_html,
                                body_plain,
                                folder,
                                is_starred,
                                is_read,
                                parent_email_id,
                                created_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'inbox', 0, 0, %s, NOW()
                            )
                        """, (
                            inbox_uuid,
                            target_id,
                            sender_email,
                            sender_name,
                            target_user["username"],
                            target_user["full_name"],
                            cc_names_str,
                            subject,
                            body_html,
                            body_plain,
                            sent_email_id,
                        ))
                        all_inbox_records.append((cursor.lastrowid, inbox_uuid))

                # 5. Create Inbox records for each CC recipient
                for cc_user in cc_user_objs:
                    cc_id = cc_user.get("id")
                    if cc_id and cc_id != sender_user["id"]:
                        inbox_uuid = generate_email_uuid()
                        cursor.execute("""
                            INSERT INTO emails (
                                email_uuid,
                                user_id,
                                sender_email,
                                sender_name,
                                recipient_email,
                                recipient_name,
                                cc_email,
                                subject,
                                body_html,
                                body_plain,
                                folder,
                                is_starred,
                                is_read,
                                parent_email_id,
                                created_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'inbox', 0, 0, %s, NOW()
                            )
                        """, (
                            inbox_uuid,
                            cc_id,
                            sender_email,
                            sender_name,
                            cc_user["username"],
                            cc_user["full_name"],
                            cc_names_str,
                            subject,
                            body_html,
                            body_plain,
                            sent_email_id,
                        ))
                        all_inbox_records.append((cursor.lastrowid, inbox_uuid))

                # 6. Create Inbox records for each BCC recipient
                for bcc_user in bcc_user_objs:
                    bcc_id = bcc_user.get("id")
                    if bcc_id and bcc_id != sender_user["id"]:
                        inbox_uuid = generate_email_uuid()
                        cursor.execute("""
                            INSERT INTO emails (
                                email_uuid,
                                user_id,
                                sender_email,
                                sender_name,
                                recipient_email,
                                recipient_name,
                                cc_email,
                                bcc_email,
                                subject,
                                body_html,
                                body_plain,
                                folder,
                                is_starred,
                                is_read,
                                parent_email_id,
                                created_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'inbox', 0, 0, %s, NOW()
                            )
                        """, (
                            inbox_uuid,
                            bcc_id,
                            sender_email,
                            sender_name,
                            bcc_user["username"],
                            bcc_user["full_name"],
                            cc_names_str,
                            bcc_names_str,
                            subject,
                            body_html,
                            body_plain,
                            sent_email_id,
                        ))
                        all_inbox_records.append((cursor.lastrowid, inbox_uuid))

                # Save attachments for each Inbox record
                for in_id, in_uuid in all_inbox_records:
                    for att in saved_attachments:
                        inbox_att_uuid = f"ATT{uuid.uuid4().hex[:12].upper()}"
                        cursor.execute("""
                            INSERT INTO email_attachments (
                                attachment_uuid, email_id, email_uuid, file_name, file_path, file_size, file_type
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (inbox_att_uuid, in_id, in_uuid, att["file_name"], att["file_path"], att["file_size"], att["file_type"]))

                conn.commit()

        finally:
            conn.close()

        return jsonify({
            "success": True,
            "message": "Internal email sent successfully!",
            "email_uuid": email_uuid
        })

    @app.route("/api/email/save-draft", methods=["POST"], endpoint="api_save_draft")
    @require_permission("email", "send")
    def api_save_draft():
        user_uuid = session.get("user_uuid")
        if not user_uuid:
            return jsonify({"success": False, "message": "Login required"}), 401

        user_info = session.get("user") or {}
        user_id = user_info.get("id")

        payload = request.get_json(silent=True) or request.form.to_dict() or {}
        to_recipients = payload.get("to_recipients") or payload.get("recipient_email") or ""
        subject = (payload.get("subject") or "Draft (No Subject)").strip()
        body_html = payload.get("body_html") or payload.get("body") or ""
        body_plain = re.sub("<[^<]+?>", "", body_html or "")

        email_uuid = generate_email_uuid()
        sender_name = user_info.get("full_name") or "User"
        sender_email = user_info.get("username") or "admin"

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO emails (
                        email_uuid,
                        user_id,
                        sender_email,
                        sender_name,
                        recipient_email,
                        recipient_name,
                        subject,
                        body_html,
                        body_plain,
                        folder,
                        is_starred,
                        is_read,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, 'drafts', 0, 1, NOW()
                    )
                """, (
                    email_uuid,
                    user_id,
                    sender_email,
                    sender_name,
                    to_recipients or "Draft",
                    to_recipients or "Draft",
                    subject,
                    body_html,
                    body_plain,
                ))
                conn.commit()
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "message": "Draft saved successfully!",
            "email_uuid": email_uuid
        })

    @app.route("/api/email/reply", methods=["POST"], endpoint="api_reply_email")
    @require_permission("email", "send")
    def api_reply_email():
        user_uuid = session.get("user_uuid")
        if not user_uuid:
            return jsonify({"success": False, "message": "Login required"}), 401

        user_info = session.get("user") or {}
        user_id = user_info.get("id")

        payload = request.get_json(silent=True) or request.form.to_dict() or {}
        parent_uuid = payload.get("parent_email_uuid")
        reply_text = (payload.get("reply_body") or "").strip()

        if not parent_uuid or not reply_text:
            return jsonify({"success": False, "message": "Reply content is required."}), 400

        conn = get_db_connection()
        new_uuid = generate_email_uuid()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM emails WHERE email_uuid = %s LIMIT 1", (parent_uuid,))
                parent = cursor.fetchone()
                if not parent:
                    return jsonify({"success": False, "message": "Parent email not found"}), 404

                cursor.execute("SELECT id, full_name, username FROM users WHERE user_uuid = %s LIMIT 1", (user_uuid,))
                sender_user = cursor.fetchone() or {"id": user_id, "full_name": "User", "username": "admin"}
                sender_name = sender_user["full_name"]
                sender_email = sender_user["username"]

                to_email = parent["sender_email"]
                to_name = parent["sender_name"] or to_email
                subject = parent["subject"]
                if not subject.lower().startswith("re:"):
                    subject = f"Re: {subject}"

                body_html = f"<p>{html.escape(reply_text)}</p><hr><small class='text-muted'>On {parent['created_at']}, {parent['sender_name']} wrote:</small><blockquote class='border-start ps-3 text-muted'>{parent.get('body_html') or parent.get('body_plain')}</blockquote>"

                # Sender Sent Record
                cursor.execute("""
                    INSERT INTO emails (
                        email_uuid,
                        user_id,
                        sender_email,
                        sender_name,
                        recipient_email,
                        recipient_name,
                        subject,
                        body_html,
                        body_plain,
                        folder,
                        is_starred,
                        is_read,
                        parent_email_id,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, 'sent', 0, 0, %s, NOW()
                    )
                """, (
                    new_uuid,
                    sender_user["id"],
                    sender_email,
                    sender_name,
                    to_email,
                    to_name,
                    subject,
                    body_html,
                    reply_text,
                    parent["id"],
                ))
                reply_sent_id = cursor.lastrowid

                # If parent has user_id or resolved user, deliver to their inbox
                cursor.execute("SELECT id FROM users WHERE username = %s OR full_name = %s LIMIT 1", (to_email, to_name))
                target_user = cursor.fetchone()
                if target_user and target_user["id"] != sender_user["id"]:
                    inbox_uuid = generate_email_uuid()
                    cursor.execute("""
                        INSERT INTO emails (
                            email_uuid,
                            user_id,
                            sender_email,
                            sender_name,
                            recipient_email,
                            recipient_name,
                            subject,
                            body_html,
                            body_plain,
                            folder,
                            is_starred,
                            is_read,
                            parent_email_id,
                            created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, 'inbox', 0, 0, %s, NOW()
                        )
                    """, (
                        inbox_uuid,
                        target_user["id"],
                        sender_email,
                        sender_name,
                        to_email,
                        to_name,
                        subject,
                        body_html,
                        reply_text,
                        reply_sent_id,
                    ))

                conn.commit()
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "message": "Reply sent successfully!",
            "email_uuid": new_uuid
        })

    @app.route("/api/email/toggle-star", methods=["POST"], endpoint="api_toggle_star")
    @app.route("/api/email/toggle-important", methods=["POST"], endpoint="api_toggle_important")
    def api_toggle_star():
        if not session.get("user_uuid"):
            return jsonify({"success": False, "message": "Login required"}), 401

        payload = request.get_json(silent=True) or request.form.to_dict() or {}
        email_uuid = payload.get("email_uuid")
        if not email_uuid:
            return jsonify({"success": False, "message": "Email UUID required"}), 400

        conn = get_db_connection()
        new_val = 0
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, is_starred FROM emails WHERE email_uuid = %s LIMIT 1", (email_uuid,))
                email_row = cursor.fetchone()
                if not email_row:
                    return jsonify({"success": False, "message": "Email not found"}), 404

                new_val = 0 if email_row["is_starred"] == 1 else 1
                cursor.execute("UPDATE emails SET is_starred = %s WHERE id = %s", (new_val, email_row["id"]))
                conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "is_starred": new_val, "is_important": new_val})

    @app.route("/api/email/delete", methods=["POST"], endpoint="api_delete_email")
    @require_permission("email", "delete")
    def api_delete_email():
        if not session.get("user_uuid"):
            return jsonify({"success": False, "message": "Login required"}), 401

        payload = request.get_json(silent=True) or request.form.to_dict() or {}
        email_uuid = payload.get("email_uuid")
        if not email_uuid:
            return jsonify({"success": False, "message": "Email UUID required"}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, folder, is_deleted FROM emails WHERE email_uuid = %s LIMIT 1", (email_uuid,))
                email_row = cursor.fetchone()
                if not email_row:
                    return jsonify({"success": False, "message": "Email not found"}), 404

                if email_row["folder"] == "trash" or email_row["is_deleted"] == 1:
                    cursor.execute("DELETE FROM emails WHERE id = %s", (email_row["id"],))
                    msg = "Email permanently deleted."
                else:
                    cursor.execute("UPDATE emails SET folder = 'trash', is_deleted = 1 WHERE id = %s", (email_row["id"],))
                    msg = "Email moved to Trash."
                conn.commit()
        finally:
            conn.close()

        return jsonify({"success": True, "message": msg})

    @app.route("/api/email/upload-image", methods=["POST"], endpoint="api_email_upload_image")
    @require_permission("email", "send")
    def api_email_upload_image():
        if not session.get("user_uuid"):
            return jsonify({"error": "Login required"}), 401

        file = request.files.get("file")
        if not file or file.filename == "":
            return jsonify({"error": "No image file provided"}), 400

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]:
            return jsonify({"error": "Invalid image format"}), 400

        filename = f"eml_{secrets.token_hex(8)}{ext}"
        upload_dir = os.path.join(app.root_path, "static", "uploads", "email")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        return jsonify({"location": f"/static/uploads/email/{filename}"})
