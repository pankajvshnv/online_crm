import os
import sys
import time
from dotenv import load_dotenv

# Ensure .env is explicitly loaded from project root
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask import Request as FlaskRequest
from werkzeug.exceptions import HTTPException

from config import Config, get_db_connection
from utils.permissions import load_user_permissions, has_permission, UNIVERSAL_SECURITY_RULES
from utils.product_helpers import get_plan_label, extract_active_product_plans
from routes.live_alerts import fetch_sidebar_live_counts
from routes import init_routes

# Configure maximum file upload and form payload sizes
FlaskRequest.max_content_length = 500 * 1024 * 1024
FlaskRequest.max_form_memory_size = 500 * 1024 * 1024
FlaskRequest.max_form_parts = 500_000

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config["SECRET_KEY"] or "zoibit-secure-key"


@app.after_request
def disable_browser_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private, post-check=0, pre-check=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "-1"
    response.headers["Vary"] = "Cookie, Accept-Encoding"
    return response


@app.errorhandler(404)
def handle_404(e=None):
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"status": "error", "message": "Endpoint not found"}), 404

    flash("This link is invalid or the page does not exist.", "warning")
    if session.get("user_uuid"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.errorhandler(Exception)
def handle_all_exceptions(e):
    if isinstance(e, HTTPException):
        if e.code == 404:
            return handle_404(e)
        return e
    import traceback
    print("[FLASK UNHANDLED EXCEPTION]", traceback.format_exc())
    return render_template("errors/service_blocked.html"), 500


@app.route("/api/version")
def api_version():
    return {"version": "v1.0.5-check", "status": "ok"}


# ---------------------------------------------------------
# Database Startup Verification Check
# ---------------------------------------------------------
db_conn = None
for _attempt in range(3):
    db_conn = get_db_connection()
    if db_conn:
        db_conn.close()
        break
    time.sleep(1)

if not db_conn:
    print("\n" + "=" * 48)
    print("DATABASE CONNECTION WARNING: Check .env / config.py")
    print("Application startup proceeded, but database is not reachable yet.")
    print("=" * 48 + "\n")


# ---------------------------------------------------------
# Global Service Block & Subscription Status Middleware
# ---------------------------------------------------------
_service_status_cache = {"is_blocked": False, "is_expired": False, "sub": {}, "ts": 0}


def get_service_status():
    """Checks if CRM service is locked/suspended or expired via service_settings (cached for 3s)."""
    return {
        "is_blocked": False,
        "is_expired": False,
        "sub": {},
        "ts": time.time()
    }


def is_service_blocked():
    """Compatibility helper for is_service_blocked."""
    return get_service_status().get("is_blocked", False)


@app.before_request
def require_login():
    # 0. Allow unregistered endpoints to be caught cleanly by 404 handler
    if request.endpoint is None:
        return None

    # 1. Allow static assets and all public /api/ endpoints
    if request.endpoint == "static" or request.path.startswith("/static/") or request.path.startswith("/api/"):
        return None

    status = get_service_status()

    # 2. Strict Service Block: If is_blocked == 1, block even the login page
    if status.get("is_blocked"):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return {"success": False, "message": "CRM Not Working. Contact Administrator."}, 503
        return render_template("errors/service_blocked.html"), 503

    # 3. Always allow logout endpoint so users can exit their session
    if request.path == "/logout" or request.endpoint == "logout":
        return None

    public_endpoints = {"login"}
    if request.endpoint in public_endpoints:
        return None

    user_uuid = session.get("user_uuid")
    if not user_uuid:
        return redirect(url_for("login", next=request.path))

    sess_token = session.get("session_token")
    if sess_token:
        from utils.session_manager import validate_user_session
        valid_sess = validate_user_session(sess_token, user_uuid)
        if not valid_sess:
            session.clear()
            flash("Your session has expired or was terminated. Please login again.", "warning")
            return redirect(url_for("login", next=request.path))


    load_user_permissions()

    path = request.path
    if request.endpoint in ["user_profile", "my_team_page", "change_password_page"]:
        return None

    if path in [
        "/", "/dashboard", "/logout",
        "/profile", "/my-profile", "/change-password", "/my-team",
        "/settings/user/profile", "/settings/user/my-team", "/settings/user/change-password"
    ] or path.startswith("/profile/"):
        return None

    for prefix, perm_tuple in UNIVERSAL_SECURITY_RULES:
        if path.startswith(prefix):
            module_key, action_key = perm_tuple
            if not has_permission(module_key, action_key):
                if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                    return {"success": False, "message": "Access Denied: You do not have permission to perform this action."}, 403
                flash("Access Denied: You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboard"))
            break

    return None



# ---------------------------------------------------------
# Global Template Context Processor (Single Optimized Connection)
# ---------------------------------------------------------
@app.context_processor
def inject_current_user():
    user_uuid = session.get("user_uuid")
    user_info = session.get("user") or {}
    user_id = user_info.get("id")

    current_user = None
    company_brand_name = "ClientOS"
    company_brand_logo = None
    company_brand_favicon = None
    company_brand_tax = "18"
    company_brand_sales_gst = "1"
    today_followups_count = 0
    today_free_trials_count = 0
    unread_emails_count = 0
    unread_chat_count = 0
    recent_research_count = 0
    service_sub = {}

    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                # 1. Fetch current user & live sidebar counts if authenticated
                if user_uuid:
                    cursor.execute("""
                        SELECT u.user_uuid, u.full_name, u.username, u.is_admin, e.extension_number
                        FROM users u
                        LEFT JOIN extensions e ON e.id = u.extension_id
                        WHERE u.user_uuid = %s AND u.status = 1
                        LIMIT 1
                    """, (user_uuid,))
                    current_user = cursor.fetchone()

                    today_followups_count, today_free_trials_count, unread_emails_count, unread_chat_count, recent_research_count = fetch_sidebar_live_counts(cursor, user_uuid, user_id)

                # 2. Fetch global company branding settings
                cursor.execute("SELECT setting_key, setting_value FROM system_settings")
                s_rows = cursor.fetchall() or []
                s_dict = {r["setting_key"]: r["setting_value"] for r in s_rows if r.get("setting_key")}

                name_val = str(s_dict.get("company_name") or "").strip()
                if name_val:
                    company_brand_name = name_val

                logo_val = str(s_dict.get("company_logo") or "").strip()
                if logo_val:
                    company_brand_logo = logo_val

                fav_val = str(s_dict.get("company_favicon") or "").strip()
                if fav_val:
                    company_brand_favicon = fav_val

                company_brand_tax = str(s_dict.get("tax_percentage") or "18").strip()
                company_brand_sales_gst = str(s_dict.get("sales_display_with_gst") or "1").strip()

                # 3. Fetch service settings subscription details (for is_admin sidebar display)
                cursor.execute("""
                    SELECT company_uid, company_name, crm_domain, plan_expiry_date 
                    FROM service_settings 
                    WHERE id = 1 
                    LIMIT 1
                """)
                service_sub = cursor.fetchone() or {}

        except Exception as e:
            print("Context processor error:", e)
        finally:
            conn.close()

    is_admin_flag = bool(session.get("user", {}).get("is_admin") == 1 or (current_user and current_user.get("is_admin") == 1))

    sub_data = service_sub if "service_sub" in locals() else {}

    return {
        "current_user": current_user,
        "is_admin_user": is_admin_flag,
        "service_subscription": sub_data,
        "company_brand_name": company_brand_name,
        "company_brand_logo": company_brand_logo,
        "company_brand_favicon": company_brand_favicon,
        "company_brand_tax": company_brand_tax,
        "company_brand_sales_gst": company_brand_sales_gst,
        "today_followups_count": today_followups_count,
        "today_free_trials_count": today_free_trials_count,
        "unread_emails_count": unread_emails_count,
        "recent_research_count": recent_research_count,
        "has_permission": has_permission,
        "get_plan_label": get_plan_label,
        "extract_active_product_plans": extract_active_product_plans,
    }


# ---------------------------------------------------------
# Register All Modular Routes
# ---------------------------------------------------------
init_routes(app)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5055))
    debug = os.getenv("FLASK_DEBUG", "0") in ("1", "true", "True")

    print(f"🚀 Starting CRM on http://{host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)
