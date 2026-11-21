import uuid
from flask import render_template, request, session, redirect, url_for, flash, jsonify
from config import get_db_connection
from utils.permissions import has_permission, require_permission, get_assignable_users
from routes.settings_helpers import encrypt_mobile
from routes.lead_upload_common import resolve_lead_source_id, resolve_lead_status_id

def get_user_team_users(cursor, user_id):
    """
    Returns list of user dicts (id, full_name, username) in team of user_id (self + all reportees recursively).
    """
    if not user_id:
        return []
    team_ids = {user_id}
    to_process = [user_id]
    
    while to_process:
        curr = to_process.pop(0)
        cursor.execute("SELECT id FROM users WHERE reporting_to_user_id = %s AND status = 1", (curr,))
        reportees = cursor.fetchall()
        for r in reportees:
            r_id = r["id"]
            if r_id not in team_ids:
                team_ids.add(r_id)
                to_process.append(r_id)
                
    team_ids_str = ",".join(map(str, team_ids))
    cursor.execute(f"SELECT id, full_name, username FROM users WHERE id IN ({team_ids_str}) AND status = 1 ORDER BY id ASC")
    return cursor.fetchall()


def add_lead_routes(app):
    @require_permission('leads', 'add')
    @app.route("/leads/add", methods=["GET", "POST"])
    def add_lead():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        connection = get_db_connection()
        if not connection:
            flash("Database connection error.", "danger")
            return redirect(url_for("all_leads"))

        form_data = {}

        try:
            with connection.cursor() as cursor:
                # Get logged-in user
                cursor.execute("SELECT id, user_uuid, full_name, username, role_id FROM users WHERE user_uuid = %s LIMIT 1", (logged_user_uuid,))
                logged_user = cursor.fetchone()
                if not logged_user:
                    return redirect(url_for("login"))

                user_id = logged_user["id"]

                # Load assignable users dropdown (Global Data Access -> All Users, else Team Users)
                team_users = get_assignable_users(cursor, user_id)

                cursor.execute("SELECT id, source_name FROM lead_sources WHERE status = 1 ORDER BY source_name ASC")
                lead_sources = cursor.fetchall()
                default_source_id = lead_sources[0]["id"] if lead_sources else 1

                cursor.execute("SELECT id, status_name, status_tone FROM lead_statuses WHERE status = 1 ORDER BY id ASC")
                lead_statuses = cursor.fetchall()
                default_status_id = lead_statuses[0]["id"] if lead_statuses else None

                if request.method == "POST":
                    name = (request.form.get("name") or "").strip()
                    mobile_number = (request.form.get("mobile") or request.form.get("mobile_number") or "").strip()
                    email = (request.form.get("email") or "").strip()
                    address = (request.form.get("address") or "").strip()
                    raw_source = (request.form.get("lead_source") or "").strip()
                    raw_status = (request.form.get("lead_status") or "").strip()
                    raw_owner = (request.form.get("current_owner_user_id") or "").strip()
                    assigned_owner_id = None
                    if raw_owner:
                        cursor.execute("SELECT id FROM users WHERE (user_uuid = %s OR id = %s) AND status = 1 LIMIT 1", (raw_owner, int(raw_owner) if raw_owner.isdigit() else 0))
                        o_row = cursor.fetchone()
                        if o_row:
                            assigned_owner_id = o_row["id"]

                    comment = (request.form.get("comment") or "").strip()

                    resolved_source_id = resolve_lead_source_id(cursor, raw_source) if raw_source else None
                    resolved_status_id = resolve_lead_status_id(cursor, raw_status) if raw_status else None

                    form_data = {
                        "name": name,
                        "mobile_number": mobile_number,
                        "email": email,
                        "address": address,
                        "lead_source": resolved_source_id,
                        "lead_status": resolved_status_id,
                        "current_owner_user_id": assigned_owner_id,
                        "comment": comment
                    }

                    if not name or not mobile_number or not raw_source:
                        flash("Lead Name, Mobile Number, and Lead Source are required.", "danger")
                    else:
                        # Clean 10-digit mobile number
                        clean_m = encrypt_mobile(mobile_number) or mobile_number

                        # Check duplicate mobile number in leads
                        cursor.execute("SELECT id FROM leads WHERE mobile_number = %s LIMIT 1", (clean_m,))
                        dup_mob = cursor.fetchone()

                        # Check duplicate email in leads
                        dup_email = None
                        if email:
                            cursor.execute("SELECT id FROM leads WHERE LOWER(email) = %s LIMIT 1", (email.lower(),))
                            dup_email = cursor.fetchone()

                        if dup_mob:
                            flash(f"Lead already exists! Mobile number '{mobile_number}' is already registered (Lead #{dup_mob['id']}).", "danger")
                        elif dup_email:
                            flash(f"Lead already exists! Email address '{email}' is already registered (Lead #{dup_email['id']}).", "danger")
                        else:
                            lead_uuid = f"LEAD{uuid.uuid4().hex[:8].upper()}"
                            # Store clean 10-digit mobile number in leads table
                            cursor.execute("""
                                INSERT INTO leads (
                                    lead_uuid, name, mobile_number, email, address,
                                    lead_source, lead_status, current_owner_user_id,
                                    created_by, comment, created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                            """, (
                                lead_uuid, name, clean_m, email or None, address or None,
                                resolved_source_id, resolved_status_id, assigned_owner_id,
                                user_id, comment
                            ))
                            lead_id = cursor.lastrowid
                            
                            connection.commit()
                            flash("Lead added successfully!", "success")
                            return redirect(url_for("all_leads"))

                return render_template(
                    "leads/add_lead.html",
                    active_group="add_lead",
                    active_page="add_lead",
                    page_title="Add New Lead",
                    logged_user=logged_user,
                    team_users=team_users,
                    lead_sources=lead_sources,
                    lead_statuses=lead_statuses,
                    form_data=form_data
                )
        finally:
            connection.close()
