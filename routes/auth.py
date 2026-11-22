import uuid
import random
import re
import json
from datetime import datetime
import requests
from flask import render_template, request, session, redirect, url_for, flash

from config import get_db_connection
from utils.permissions import set_user_session
from utils.session_manager import create_user_session, terminate_user_session, validate_user_session


def get_client_ip():
    """Extract client IP address for activity logging."""
    if request.headers.get("CF-Connecting-IP"):
        return request.headers.get("CF-Connecting-IP").strip()
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    if request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP").strip()
    return (request.remote_addr or "127.0.0.1").strip()


def get_service_settings_data():
    """Fetches service settings (ips_list, is_blocked, plan_expiry_date) from service_settings table."""
    conn = get_db_connection()
    row = None
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, company_uid, company_name, crm_domain, ips_list, 
                           plan_expiry_date, is_blocked 
                    FROM service_settings 
                    LIMIT 1
                """)
                row = cursor.fetchone()
        except Exception as e:
            print(f"[AUTH] Error reading service_settings: {e}")
        finally:
            conn.close()
    return row or {}


def is_client_office_ip(client_ip=None, ips_list_raw=None):
    """IP restriction is disabled: all locations are permitted."""
    return True


def format_whatsapp_phone(raw_phone):
    """Formats phone number to international E.164 format with country code (defaults to +91)."""
    if not raw_phone:
        return None
    phone_clean = re.sub(r"[^\d+]", "", str(raw_phone).strip())
    if not phone_clean:
        return None
    if phone_clean.startswith("+"):
        return phone_clean
    if len(phone_clean) == 10:
        return f"+91{phone_clean}"
    if len(phone_clean) == 12 and phone_clean.startswith("91"):
        return f"+{phone_clean}"
    return f"+91{phone_clean}"


def mask_phone_for_display(formatted_phone):
    """Masks phone number for safe UI display, e.g. +91 93992 ****58."""
    if not formatted_phone or len(formatted_phone) < 8:
        return formatted_phone or ""
    return f"{formatted_phone[:5]}****{formatted_phone[-3:]}"


def send_whatsapp_otp(phone_number, otp_code):
    """
    Sends WhatsApp OTP via Zoibit WhatsApp API.
    Endpoint: https://zoibit.com/api/send
    """
    try:
        url = "https://zoibit.com/api/send"
        payload = {
            "phone": str(phone_number),
            "otp": str(otp_code)
        }
        headers = {
            "Content-Type": "application/json"
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        try:
            resp_data = resp.json()
        except Exception:
            resp_data = {"raw_response": resp.text, "status_code": resp.status_code}
        is_success = resp.status_code == 200 and resp_data.get("status") == "success"
        return is_success, resp_data
    except Exception as ex:
        print("[WhatsApp OTP Error]", ex)
        return False, str(ex)


def log_user_login_activity(cursor, user_id, username, ip_address, via_otp=False):
    activity_uuid = f"UACT{uuid.uuid4().hex[:12].upper()}"
    desc = f"User '{username}' logged in successfully" + (" via WhatsApp OTP" if via_otp else "")
    cursor.execute("""
        INSERT INTO user_activities (
            user_activity_uuid, user_id, action_type, description, ip_address
        ) VALUES (%s, %s, 'User Login', %s, %s)
    """, (activity_uuid, user_id, desc, ip_address or None))


def auth_routes(app):

    @app.route("/login", methods=["GET", "POST"])
    def login():
        try:
            return _handle_login()
        except Exception as e:
            import traceback
            print("[LOGIN ERROR]", traceback.format_exc())
            flash(f"Login error: {str(e)}", "danger")
            return render_template("auth/login.html", page_title="Login", require_otp_step=False)

    def _handle_login():
        if session.get("user_uuid"):
            return redirect(url_for("dashboard"))

        pending_user_id = session.get("pending_otp_user_id")
        pending_user_uuid = session.get("pending_otp_user_uuid")
        pending_username = session.get("pending_otp_username")
        pending_phone_masked = session.get("pending_otp_phone_masked", "")

        if request.method == "POST":
            action = request.form.get("action")

            # -----------------------------------------------------------------
            # Option A: Cancel OTP step
            # -----------------------------------------------------------------
            if action == "cancel_otp":
                session.pop("pending_otp_user_id", None)
                session.pop("pending_otp_user_uuid", None)
                session.pop("pending_otp_username", None)
                session.pop("pending_otp_phone_masked", None)
                return redirect(url_for("login"))

            # -----------------------------------------------------------------
            # Option B: Resend OTP
            # -----------------------------------------------------------------
            if action == "resend_otp" and pending_user_id:
                conn = get_db_connection()
                user = None
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT id, username, mobile
                            FROM users
                            WHERE id = %s AND status = 1
                            LIMIT 1
                        """, (pending_user_id,))
                        user = cursor.fetchone()
                    conn.close()

                if not user:
                    flash("User account not found. Please log in again.", "danger")
                    return redirect(url_for("login", cancel_otp="1"))

                phone_formatted = format_whatsapp_phone(user.get("mobile"))
                if not phone_formatted:
                    flash("No valid mobile number registered for WhatsApp OTP.", "danger")
                    return render_template(
                        "auth/login.html",
                        page_title="Verify OTP",
                        require_otp_step=True,
                        pending_username=pending_username,
                        pending_phone_masked=pending_phone_masked
                    )

                # Generate new 6-digit OTP
                new_otp = f"{random.randint(100000, 999999)}"

                # Save OTP ONLY in database SQL (NEVER in session to prevent bypass)
                conn = get_db_connection()
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            UPDATE users
                            SET login_otp = %s, login_otp_created_at = NOW()
                            WHERE id = %s
                        """, (new_otp, pending_user_id))
                        conn.commit()
                    conn.close()

                # Dispatch WhatsApp API
                sent_ok, api_resp = send_whatsapp_otp(phone_formatted, new_otp)
                masked_display = mask_phone_for_display(phone_formatted)
                session["pending_otp_phone_masked"] = masked_display

                if sent_ok:
                    flash(f"A new 6-digit OTP has been sent to your WhatsApp number ({masked_display}).", "info")
                else:
                    flash(f"OTP generated in system, but WhatsApp delivery returned an alert: {api_resp}. Please enter the OTP.", "warning")

                return render_template(
                    "auth/login.html",
                    page_title="Verify OTP",
                    require_otp_step=True,
                    pending_username=pending_username,
                    pending_phone_masked=masked_display
                )

            # -----------------------------------------------------------------
            # Option C: Verify OTP (Verified directly against SQL database)
            # -----------------------------------------------------------------
            if action == "verify_otp" and pending_user_id:
                submitted_otp = str(request.form.get("otp_code") or "").strip()

                # Fetch OTP strictly from SQL DB (no session bypass possible)
                conn = get_db_connection()
                user = None
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT id, user_uuid, username, login_otp, login_otp_created_at
                            FROM users
                            WHERE id = %s AND status = 1
                            LIMIT 1
                        """, (pending_user_id,))
                        user = cursor.fetchone()
                    conn.close()

                if not user:
                    flash("User account not found.", "danger")
                    return redirect(url_for("login", cancel_otp="1"))

                db_otp = str(user.get("login_otp") or "").strip()
                created_at = user.get("login_otp_created_at")

                # Expiry Check: Max 5 minutes (300 seconds)
                if created_at and isinstance(created_at, datetime):
                    time_diff = (datetime.now() - created_at).total_seconds()
                    if time_diff > 300:
                        flash("OTP has expired (Max 5 minutes valid). Please click Resend OTP.", "danger")
                        return render_template(
                            "auth/login.html",
                            page_title="Verify OTP",
                            require_otp_step=True,
                            pending_username=pending_username,
                            pending_phone_masked=pending_phone_masked
                        )

                # Direct DB comparison
                if db_otp and db_otp == submitted_otp:
                    # Clear OTP in database immediately after successful verification
                    conn = get_db_connection()
                    if conn:
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                UPDATE users
                                SET login_otp = NULL, login_otp_created_at = NULL
                                WHERE id = %s
                            """, (user["id"],))
                            log_user_login_activity(cursor, user["id"], user["username"], get_client_ip(), via_otp=True)
                            conn.commit()
                        conn.close()

                    # Clear pending OTP session variables
                    session.pop("pending_otp_user_id", None)
                    session.pop("pending_otp_user_uuid", None)
                    session.pop("pending_otp_username", None)
                    session.pop("pending_otp_phone_masked", None)

                    # Initialize authenticated user session & record in user_sessions table
                    set_user_session(user["user_uuid"])
                    create_user_session(user["id"], user["user_uuid"], user["username"], get_client_ip())
                    next_url = request.args.get("next")
                    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
                        next_url = url_for("dashboard")
                    return redirect(next_url)
                else:
                    flash("Invalid OTP. Please enter the correct 6-digit OTP sent to your WhatsApp.", "danger")
                    return render_template(
                        "auth/login.html",
                        page_title="Verify OTP",
                        require_otp_step=True,
                        pending_username=pending_username,
                        pending_phone_masked=pending_phone_masked
                    )

            # -----------------------------------------------------------------
            # Option D: Initial Username & Password Submission
            # -----------------------------------------------------------------
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""

            conn = get_db_connection()
            if not conn:
                flash("Cannot connect to MySQL database. Please make sure MySQL is running and database.sql is imported.", "danger")
                return render_template("auth/login.html", page_title="Login", require_otp_step=False)

            user = None
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        u.id,
                        u.user_uuid,
                        u.username,
                        u.password,
                        u.mobile,
                        u.require_otp_for_login,
                        u.outside_login,
                        u.is_admin,
                        r.permissions
                    FROM users u
                    LEFT JOIN roles r ON r.id = u.role_id
                    WHERE u.username = %s AND u.status = 1
                    LIMIT 1
                """, (username,))
                user = cursor.fetchone()
            conn.close()

            if user and user["password"] == password:
                client_ip = get_client_ip()

                # Check if user specifically requires OTP (admins log in directly)
                require_otp = int(user.get("require_otp_for_login") or 0)
                if require_otp == 1 and int(user.get("is_admin") or 0) != 1:
                    phone_formatted = format_whatsapp_phone(user.get("mobile"))
                    if not phone_formatted:
                        flash("Your account requires WhatsApp OTP verification, but no valid mobile number is registered. Please contact your administrator.", "danger")
                        return redirect(url_for("login"))

                    # Generate 6-digit OTP
                    generated_otp = f"{random.randint(100000, 999999)}"

                    conn = get_db_connection()
                    if conn:
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                UPDATE users
                                SET login_otp = %s, login_otp_created_at = NOW()
                                WHERE id = %s
                            """, (generated_otp, user["id"]))
                            conn.commit()
                        conn.close()

                    masked_display = mask_phone_for_display(phone_formatted)
                    session["pending_otp_user_id"] = user["id"]
                    session["pending_otp_user_uuid"] = user["user_uuid"]
                    session["pending_otp_username"] = user["username"]
                    session["pending_otp_phone_masked"] = masked_display

                    sent_ok, api_resp = send_whatsapp_otp(phone_formatted, generated_otp)
                    flash(f"A 6-digit verification code has been sent to your WhatsApp ({masked_display}). Please enter the OTP to login.", "info")

                    return render_template(
                        "auth/login.html",
                        page_title="Verify OTP",
                        require_otp_step=True,
                        pending_username=user["username"],
                        pending_phone_masked=masked_display
                    )
                else:
                    # Direct Login (IP restrictions completely removed)
                    conn = get_db_connection()
                    if conn:
                        with conn.cursor() as cursor:
                            log_user_login_activity(cursor, user["id"], user["username"], client_ip, via_otp=False)
                            conn.commit()
                        conn.close()

                    session.clear()
                    set_user_session(user["user_uuid"])
                    create_user_session(user["id"], user["user_uuid"], user["username"], client_ip)
                    next_url = request.args.get("next")
                    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
                        next_url = url_for("dashboard")
                    return redirect(next_url)

            flash("Invalid username or password.", "danger")

        # ---------------------------------------------------------------------
        # GET Request Handler
        # ---------------------------------------------------------------------
        if request.args.get("cancel_otp") or request.args.get("back"):
            session.pop("pending_otp_user_id", None)
            session.pop("pending_otp_user_uuid", None)
            session.pop("pending_otp_username", None)
            session.pop("pending_otp_phone_masked", None)
            return redirect(url_for("login"))

        if pending_user_id:
            return render_template(
                "auth/login.html",
                page_title="Verify OTP",
                require_otp_step=True,
                pending_username=pending_username,
                pending_phone_masked=pending_phone_masked
            )

        return render_template("auth/login.html", page_title="Login", require_otp_step=False)

    @app.route("/register", methods=["GET", "POST"])
    @app.route("/signup", methods=["GET", "POST"])
    def register():
        if session.get("user_uuid"):
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            full_name = (request.form.get("full_name") or "").strip()
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            confirm_password = request.form.get("confirm_password") or ""
            mobile = (request.form.get("mobile") or "").strip()

            if not username or not password:
                flash("Username (ID) and Password are required.", "danger")
                return render_template("auth/register.html", page_title="Create Account", full_name=full_name, username=username, mobile=mobile)

            if len(password) < 4:
                flash("Password must be at least 4 characters long.", "danger")
                return render_template("auth/register.html", page_title="Create Account", full_name=full_name, username=username, mobile=mobile)

            if password != confirm_password:
                flash("Passwords do not match. Please re-enter your password.", "danger")
                return render_template("auth/register.html", page_title="Create Account", full_name=full_name, username=username, mobile=mobile)

            conn = get_db_connection()
            if not conn:
                flash("Cannot connect to database. Please make sure MySQL is running.", "danger")
                return render_template("auth/register.html", page_title="Create Account", full_name=full_name, username=username, mobile=mobile)

            try:
                with conn.cursor() as cursor:
                    # Check if username already exists
                    cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s) LIMIT 1", (username,))
                    existing = cursor.fetchone()
                    if existing:
                        flash(f"Username '{username}' is already in use. Please choose another username.", "warning")
                        return render_template("auth/register.html", page_title="Create Account", full_name=full_name, username=username, mobile=mobile)

                    new_uuid = f"usr-{uuid.uuid4().hex[:12]}"
                    user_name_display = full_name if full_name else username

                    cursor.execute("""
                        INSERT INTO users (
                            user_uuid, full_name, username, mobile, password,
                            role_id, is_admin, status, click_to_call, number_show_hide,
                            require_otp_for_login, outside_login
                        ) VALUES (%s, %s, %s, %s, %s, 1, 1, 1, '1', '1', 0, 1)
                    """, (new_uuid, user_name_display, username, mobile or None, password))
                    conn.commit()

                flash("Account created successfully! Please sign in with your ID and password.", "success")
                return redirect(url_for("login"))
            except Exception as e:
                print("[REGISTER ERROR]", e)
                flash(f"Error creating account: {str(e)}", "danger")
                return render_template("auth/register.html", page_title="Create Account", full_name=full_name, username=username, mobile=mobile)
            finally:
                conn.close()

        return render_template("auth/register.html", page_title="Create Account")

    @app.route("/logout")
    def logout():
        terminate_user_session()
        return redirect(url_for("login"))

    @app.route("/api/session/verify", methods=["GET", "POST"])
    def api_verify_session():
        token = request.args.get("token") or request.form.get("token")
        if not token and request.is_json:
            token = (request.get_json(silent=True) or {}).get("token")
        if not token:
            token = session.get("session_token")

        if not token:
            return {"status": "error", "message": "No session token provided"}, 400

        conn = get_db_connection()
        if not conn:
            return {"status": "error", "message": "Database connection unavailable"}, 503

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, session_token, user_id, user_uuid, username, ip_address, is_active, created_at, last_activity
                    FROM user_sessions
                    WHERE session_token = %s AND is_active = 1
                    LIMIT 1
                """, (token,))
                sess = cursor.fetchone()
                if sess:
                    if sess.get("created_at") and hasattr(sess["created_at"], "strftime"):
                        sess["created_at"] = sess["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                    if sess.get("last_activity") and hasattr(sess["last_activity"], "strftime"):
                        sess["last_activity"] = sess["last_activity"].strftime("%Y-%m-%d %H:%M:%S")
                    return {"status": "success", "session": sess}
                return {"status": "error", "message": "Session is inactive or invalid"}, 401
        finally:
            conn.close()
