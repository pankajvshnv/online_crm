import os
import uuid
from werkzeug.utils import secure_filename
from utils.permissions import require_permission
from flask import render_template, request, jsonify, session, redirect, url_for, flash
from config import get_db_connection

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads', 'company')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def register_company_routes(app):

    @require_permission('settings', 'system_controls')
    @app.route("/settings/system/company", methods=["GET", "POST"], endpoint="company_settings")
    def company_settings_page():
        if not session.get("user_uuid"):
            flash("Please log in to access Company Settings.", "warning")
            return redirect(url_for("login"))

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                if request.method == "POST":
                    company_name = str(request.form.get("company_name") or "").strip()
                    tax_percentage = str(request.form.get("tax_percentage") or "0").strip()
                    sales_display_with_gst = str(request.form.get("sales_display_with_gst") or "0").strip()
                    free_trial_days = str(request.form.get("free_trial_days") or "7").strip()
                    chart_desigs_input = str(request.form.get("dashboard_chart_designations") or "").strip()
                    if not chart_desigs_input:
                        chart_desigs_list = request.form.getlist("dashboard_chart_designations")
                        chart_desigs_str = ",".join([d.strip() for d in chart_desigs_list if d.strip()])
                    else:
                        chart_desigs_str = chart_desigs_input

                    enable_birthday_alert = str(request.form.get("enable_birthday_alert") or "1").strip()
                    enable_so_approved_alert = str(request.form.get("enable_so_approved_alert") or "1").strip()
                    enable_target_achieved_alert = str(request.form.get("enable_target_achieved_alert") or "1").strip()
                    enable_joining_day_alert = str(request.form.get("enable_joining_day_alert") or "1").strip()
                    enable_work_anniversary_alert = str(request.form.get("enable_work_anniversary_alert") or "1").strip()

                    settings_to_update = {
                        "company_name": company_name,
                        "tax_percentage": tax_percentage,
                        "sales_display_with_gst": sales_display_with_gst,
                        "free_trial_days": free_trial_days,
                        "dashboard_chart_designations": chart_desigs_str,
                        "enable_birthday_alert": enable_birthday_alert,
                        "enable_so_approved_alert": enable_so_approved_alert,
                        "enable_target_achieved_alert": enable_target_achieved_alert,
                        "enable_joining_day_alert": enable_joining_day_alert,
                        "enable_work_anniversary_alert": enable_work_anniversary_alert,
                    }

                    # File Upload: Logo
                    logo_file = request.files.get("company_logo")
                    if logo_file and logo_file.filename and allowed_file(logo_file.filename):
                        ext = logo_file.filename.rsplit('.', 1)[1].lower()
                        filename = f"logo_{uuid.uuid4().hex[:8]}.{ext}"
                        filepath = os.path.join(UPLOAD_FOLDER, filename)
                        logo_file.save(filepath)
                        settings_to_update["company_logo"] = f"/static/uploads/company/{filename}"

                    # File Upload: Favicon
                    fav_file = request.files.get("company_favicon")
                    if fav_file and fav_file.filename and allowed_file(fav_file.filename):
                        ext = fav_file.filename.rsplit('.', 1)[1].lower()
                        filename = f"favicon_{uuid.uuid4().hex[:8]}.{ext}"
                        filepath = os.path.join(UPLOAD_FOLDER, filename)
                        fav_file.save(filepath)
                        settings_to_update["company_favicon"] = f"/static/uploads/company/{filename}"

                    for key, val in settings_to_update.items():
                        cursor.execute("""
                            INSERT INTO system_settings (setting_key, setting_value)
                            VALUES (%s, %s)
                            ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                        """, (key, val))

                    conn.commit()
                    flash("Company settings updated successfully.", "success")
                    return redirect(url_for("company_settings"))

                # GET request: fetch current settings
                cursor.execute("SELECT setting_key, setting_value FROM system_settings")
                rows = cursor.fetchall()
                settings = {r["setting_key"]: r["setting_value"] for r in rows}

                # Fetch available designations for Dashboard Chart selection (strictly from DB)
                cursor.execute("SELECT id, designation_name FROM designations WHERE status = 1 ORDER BY designation_name ASC")
                d_rows = cursor.fetchall()
                
                desig_by_id = {str(r["id"]): r for r in d_rows}
                desig_by_name = {str(r["designation_name"]).strip().lower(): r for r in d_rows}

                saved_chart_desigs_str = settings.get("dashboard_chart_designations", "")
                raw_items = [x.strip() for x in saved_chart_desigs_str.split(",") if x.strip()]

                saved_chart_designation_ids = []
                for item in raw_items:
                    if item in desig_by_id:
                        if item not in saved_chart_designation_ids:
                            saved_chart_designation_ids.append(item)
                    elif item.lower() in desig_by_name:
                        d_id = str(desig_by_name[item.lower()]["id"])
                        if d_id not in saved_chart_designation_ids:
                            saved_chart_designation_ids.append(d_id)

                saved_set = set(saved_chart_designation_ids)
                ordered_designations_list = []
                for did in saved_chart_designation_ids:
                    if did in desig_by_id:
                        ordered_designations_list.append(desig_by_id[did])
                for r in d_rows:
                    if str(r["id"]) not in saved_set:
                        ordered_designations_list.append(r)

        finally:
            conn.close()

        return render_template(
            "settings/company_settings.html",
            settings=settings,
            ordered_designations_list=ordered_designations_list,
            saved_chart_designations=saved_chart_designation_ids,
            page_title="Company Settings",
            active_group="settings",
            active_page="company_settings",
        )
