import uuid
from flask import render_template, request, jsonify, session, redirect, url_for
from config import get_db_connection
from utils.permissions import require_permission, has_permission


def get_current_user(cursor, user_uuid):
    if not user_uuid:
        return None
    cursor.execute("SELECT id, user_uuid, full_name, role_id FROM users WHERE user_uuid = %s LIMIT 1", (user_uuid,))
    return cursor.fetchone()


def handbook_routes(app):

    # 1. Handbook Home List Page
    @app.route("/handbook")
    @require_permission("handbook", "view")
    def handbook_home():
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, handbook_uuid, title, category, created_by_name, created_at, updated_at
                FROM handbooks
                WHERE status = 1
                ORDER BY id DESC
            """)
            handbooks = cursor.fetchall() or []
        conn.close()

        return render_template(
            "handbook/handbook_home.html",
            handbooks=handbooks,
            can_add=has_permission("handbook", "add"),
            can_edit=has_permission("handbook", "edit"),
            can_delete=has_permission("handbook", "delete"),
            active_group="handbook",
            active_page="handbook_home",
            page_title="Handbook Center"
        )

    # 2. Full Page: Add New Handbook (Requires 'add' permission)
    @app.route("/handbook/add")
    @require_permission("handbook", "add")
    def handbook_add_page():
        return render_template(
            "handbook/handbook_form.html",
            handbook=None,
            is_edit=False,
            active_group="handbook",
            active_page="handbook_home",
            page_title="Add New Handbook"
        )

    # 3. Full Page: Edit Handbook (Requires 'edit' permission)
    @app.route("/handbook/edit/<hb_uuid>")
    @require_permission("handbook", "edit")
    def handbook_edit_page(hb_uuid):
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, handbook_uuid, title, category, description, created_by_name, created_at, updated_at
                FROM handbooks
                WHERE handbook_uuid = %s AND status = 1
                LIMIT 1
            """, (hb_uuid,))
            hb = cursor.fetchone()
        conn.close()

        if not hb:
            return redirect(url_for("handbook_home"))

        return render_template(
            "handbook/handbook_form.html",
            handbook=hb,
            is_edit=True,
            active_group="handbook",
            active_page="handbook_home",
            page_title=f"Edit Handbook: {hb['title']}"
        )

    # 4. Full Page: View Handbook (Requires 'view' permission)
    @app.route("/handbook/view/<hb_uuid>")
    @require_permission("handbook", "view")
    def handbook_view_page(hb_uuid):
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, handbook_uuid, title, category, description, created_by_name, created_at, updated_at
                FROM handbooks
                WHERE handbook_uuid = %s AND status = 1
                LIMIT 1
            """, (hb_uuid,))
            hb = cursor.fetchone()
        conn.close()

        if not hb:
            return redirect(url_for("handbook_home"))

        return render_template(
            "handbook/handbook_view.html",
            handbook=hb,
            can_edit=has_permission("handbook", "edit"),
            can_delete=has_permission("handbook", "delete"),
            active_group="handbook",
            active_page="handbook_home",
            page_title=hb["title"]
        )

    # ---------------------------------------------------------------------
    # API ENDPOINTS
    # ---------------------------------------------------------------------

    @app.route("/api/handbook/add", methods=["POST"])
    @require_permission("handbook", "add")
    def api_handbook_add():
        data = request.get_json() or {}
        title = str(data.get("title") or "").strip()
        description = str(data.get("description") or "").strip()

        if not title:
            return jsonify({"success": False, "message": "Handbook Title is required."}), 400

        if not description or description == "<p></p>":
            return jsonify({"success": False, "message": "Handbook Description content is required."}), 400

        user_uuid = session.get("user_uuid")
        conn = get_db_connection()
        with conn.cursor() as cursor:
            user = get_current_user(cursor, user_uuid)
            user_id = user["id"] if user else None
            user_name = user["full_name"] if user else "Admin"
            hb_uuid = str(uuid.uuid4())

            cursor.execute("""
                INSERT INTO handbooks (handbook_uuid, title, category, description, created_by_user_id, created_by_name)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (hb_uuid, title, 'General', description, user_id, user_name))
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": f"Handbook '{title}' created successfully!", "handbook_uuid": hb_uuid})

    @app.route("/api/handbook/get/<hb_uuid>", methods=["GET"])
    @require_permission("handbook", "view")
    def api_handbook_get(hb_uuid):
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT handbook_uuid, title, category, description, created_by_name, created_at, updated_at
                FROM handbooks
                WHERE handbook_uuid = %s AND status = 1
                LIMIT 1
            """, (hb_uuid,))
            hb = cursor.fetchone()
        conn.close()

        if not hb:
            return jsonify({"success": False, "message": "Handbook not found."}), 404

        if hb.get("created_at"):
            hb["created_at"] = str(hb["created_at"])
        if hb.get("updated_at"):
            hb["updated_at"] = str(hb["updated_at"])

        return jsonify({"success": True, "handbook": hb})

    @app.route("/api/handbook/update", methods=["POST"])
    @require_permission("handbook", "edit")
    def api_handbook_update():
        data = request.get_json() or {}
        hb_uuid = str(data.get("handbook_uuid") or "").strip()
        title = str(data.get("title") or "").strip()
        description = str(data.get("description") or "").strip()

        if not hb_uuid:
            return jsonify({"success": False, "message": "Handbook ID is required."}), 400
        if not title:
            return jsonify({"success": False, "message": "Handbook Title is required."}), 400
        if not description or description == "<p></p>":
            return jsonify({"success": False, "message": "Handbook Description content is required."}), 400

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE handbooks
                SET title = %s, description = %s, updated_at = NOW()
                WHERE handbook_uuid = %s AND status = 1
            """, (title, description, hb_uuid))
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": f"Handbook '{title}' updated successfully!", "handbook_uuid": hb_uuid})

    @app.route("/api/handbook/delete", methods=["POST"])
    @require_permission("handbook", "delete")
    def api_handbook_delete():
        data = request.get_json() or {}
        hb_uuid = str(data.get("handbook_uuid") or "").strip()

        if not hb_uuid:
            return jsonify({"success": False, "message": "Handbook ID is required."}), 400

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE handbooks SET status = 0 WHERE handbook_uuid = %s", (hb_uuid,))
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "Handbook deleted successfully!"})
