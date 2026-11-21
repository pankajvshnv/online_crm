from utils.permissions import require_permission
from flask import flash, redirect, request, session, url_for
from config import get_db_connection
from routes.lead_upload_common import (
    create_and_import_lead_batch,
    normalize_mobile,
    prepare_records_from_paste,
    split_pasted_numbers,
)


def register_lead_upload_quick_routes(app):
    @app.route("/leads/paste-leads", methods=["POST"], endpoint="lead_upload_quick_paste_alt")
    @app.route("/leads/bulk-upload/paste", methods=["POST"], endpoint="lead_upload_quick_paste")
    def lead_upload_quick_paste():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        paste_text = request.form.get("paste_numbers") or ""
        tokens = split_pasted_numbers(paste_text)
        if not tokens:
            flash("Please paste at least one mobile number.", "warning")
            return redirect(url_for("paste_leads"))

        # Strict validation: Check for invalid non-numeric or non-10-digit mobile tokens
        invalid_tokens = []
        for token in tokens:
            normalized, _msg = normalize_mobile(token)
            if not normalized:
                invalid_tokens.append(token)

        if invalid_tokens:
            preview = ", ".join(invalid_tokens[:5])
            extra = f" (+{len(invalid_tokens)-5} more)" if len(invalid_tokens) > 5 else ""
            flash(
                f"Invalid mobile number(s) detected: '{preview}{extra}'. Please enter valid 10-digit Indian mobile numbers starting with 6, 7, 8, or 9.",
                "danger",
            )
            return redirect(url_for("paste_leads"))

        records = prepare_records_from_paste(paste_text)
        lead_source = (request.form.get("lead_source") or "").strip()
        if not lead_source:
            flash("Please select lead source.", "danger")
            return redirect(url_for("paste_leads"))

        lead_status = (request.form.get("lead_status") or "").strip()
        assign_to_user_uuid = (request.form.get("assign_to_user_uuid") or "").strip()
        batch_name = (request.form.get("batch_name") or "").strip()

        conn = get_db_connection()
        if not conn:
            flash("Database connection error.", "danger")
            return redirect(url_for("paste_leads"))

        try:
            batch_uuid, imported_count, batch = create_and_import_lead_batch(
                conn,
                "quick_paste",
                batch_name,
                records,
                logged_user_uuid,
                lead_source=lead_source,
                lead_status=lead_status or None,
                assign_to_user_uuid=assign_to_user_uuid or None,
            )
            flash(f"Paste leads batch processed! Imported {imported_count} new lead(s) successfully.", "success")
        except Exception as e:
            flash(f"Failed to process paste leads: {e}", "danger")
        finally:
            conn.close()

        # Reload same page so user sees updated Last Uploads list right below
        return redirect(url_for("paste_leads"))
