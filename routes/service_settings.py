from flask import render_template, request, session, redirect, url_for, flash
from config import get_db_connection
from utils.permissions import require_permission


def register_service_settings_routes(app):

    @app.route("/settings/system/service", methods=["GET", "POST"], endpoint="service_settings")
    def service_settings_page():
        # UI removed so no admin can modify Service & Security settings from browser
        return redirect(url_for("settings_home"))

    @app.route("/api/service/subscription/callback", methods=["POST"])
    def subscription_callback():
        """
        Receives recharge confirmation from Zoibit portal and updates local CRM license.
        Payload: { 'company_uid': '...', 'expiry_date': 'YYYY-MM-DD', 'amount': 5000.00 }
        """
        from flask import jsonify
        from datetime import date, datetime, timedelta

        data = request.get_json(silent=True) or request.form.to_dict() or {}
        new_expiry_date = data.get("expiry_date")
        days = data.get("days")
        amount = data.get("amount") or 5000.00

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    # If days is provided instead of fixed date, calculate new expiry
                    if not new_expiry_date and days:
                        cursor.execute("SELECT plan_expiry_date FROM service_settings WHERE id = 1 LIMIT 1")
                        curr_row = cursor.fetchone() or {}
                        curr_exp = curr_row.get("plan_expiry_date")
                        today = date.today()
                        base_date = curr_exp if (curr_exp and curr_exp > today) else today
                        new_expiry_date = (base_date + timedelta(days=int(days))).strftime("%Y-%m-%d")

                    if not new_expiry_date:
                        return jsonify({"status": "error", "message": "Missing expiry_date or days in payload"}), 400

                    cursor.execute("""
                        UPDATE service_settings
                        SET plan_expiry_date = %s,
                            is_blocked = 0,
                            updated_at = NOW()
                        WHERE id = 1
                    """, (new_expiry_date,))
                    conn.commit()
                return jsonify({
                    "status": "success",
                    "message": "Subscription successfully renewed on CRM instance",
                    "plan_expiry_date": str(new_expiry_date)
                }), 200
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
            finally:
                conn.close()

        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    @app.route("/api/service/info", methods=["GET", "POST"], strict_slashes=False)
    def get_service_settings_api():
        from flask import jsonify

        # Strictly POST method only
        if request.method != "POST":
            return jsonify({
                "status": "error",
                "message": "Method Not Allowed. Only POST requests are permitted."
            }), 405

        # Read company_uid from POST payload (JSON or form)
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        company_uid = str(data.get("company_uid") or data.get("company_id") or "").strip()

        if not company_uid:
            return jsonify({
                "status": "error",
                "message": "No company available"
            }), 404

        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, company_uid, company_name, crm_domain, ips_list, 
                           plan_expiry_date, is_blocked, notes, created_at, updated_at
                    FROM service_settings 
                    WHERE company_uid = %s
                    LIMIT 1
                """, (company_uid,))
                row = cursor.fetchone()

            # If company_uid does not match
            if not row:
                return jsonify({
                    "status": "error",
                    "message": "No company available"
                }), 404

            # If valid, return company service settings data
            for k, v in row.items():
                if hasattr(v, "strftime"):
                    row[k] = str(v)

            return jsonify({
                "status": "success",
                "data": row
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
        finally:
            conn.close()

    @app.route("/api/service/update", methods=["GET", "POST"], strict_slashes=False)
    def update_service_settings_api():
        """
        API Endpoint to update/save service_settings data.
        Validates company_uid against DB before updating.
        Accepts: company_uid (required) + any of:
        - company_name
        - crm_domain
        - ips_list
        - plan_expiry_date (or days)
        - is_blocked
        - notes
        """
        from flask import jsonify

        # Strictly POST method only
        if request.method != "POST":
            return jsonify({
                "status": "error",
                "message": "Method Not Allowed. Only POST requests are permitted."
            }), 405

        data = request.get_json(silent=True) or request.form.to_dict() or {}
        company_uid = str(data.get("company_uid") or data.get("company_id") or "").strip()

        if not company_uid:
            return jsonify({
                "status": "error",
                "message": "No company available"
            }), 404

        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                # 1. Verify company_uid matches in service_settings
                cursor.execute("""
                    SELECT id FROM service_settings 
                    WHERE company_uid = %s 
                    LIMIT 1
                """, (company_uid,))
                existing = cursor.fetchone()

                if not existing:
                    return jsonify({
                        "status": "error",
                        "message": "No company available"
                    }), 404

                record_id = existing["id"]

                # 2. Build dynamic UPDATE fields from POST data
                update_fields = []
                params = []

                if "company_name" in data and data["company_name"] is not None:
                    update_fields.append("company_name = %s")
                    params.append(str(data["company_name"]).strip())

                if "crm_domain" in data and data["crm_domain"] is not None:
                    update_fields.append("crm_domain = %s")
                    params.append(str(data["crm_domain"]).strip())

                if "ips_list" in data and data["ips_list"] is not None:
                    update_fields.append("ips_list = %s")
                    params.append(str(data["ips_list"]).strip())

                if "plan_expiry_date" in data and data["plan_expiry_date"]:
                    update_fields.append("plan_expiry_date = %s")
                    params.append(str(data["plan_expiry_date"]).strip())
                elif "days" in data and data["days"]:
                    from datetime import date, timedelta
                    cursor.execute("SELECT plan_expiry_date FROM service_settings WHERE id = %s", (record_id,))
                    curr_exp = (cursor.fetchone() or {}).get("plan_expiry_date")
                    today = date.today()
                    base_d = curr_exp if (curr_exp and curr_exp > today) else today
                    new_exp = (base_d + timedelta(days=int(data["days"]))).strftime("%Y-%m-%d")
                    update_fields.append("plan_expiry_date = %s")
                    params.append(new_exp)

                if "is_blocked" in data and data["is_blocked"] is not None:
                    update_fields.append("is_blocked = %s")
                    params.append(int(data["is_blocked"]))

                if "notes" in data and data["notes"] is not None:
                    update_fields.append("notes = %s")
                    params.append(str(data["notes"]).strip())

                if update_fields:
                    update_fields.append("updated_at = NOW()")
                    sql = f"UPDATE service_settings SET {', '.join(update_fields)} WHERE id = %s"
                    params.append(record_id)
                    cursor.execute(sql, tuple(params))
                    conn.commit()

            return jsonify({
                "status": "success",
                "message": "Data saved successfully"
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
        finally:
            conn.close()

