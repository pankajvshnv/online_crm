from utils.permissions import require_permission
from flask import flash, redirect, request, session, url_for

from config import get_db_connection
from routes.lead_upload_common import create_and_import_lead_batch, prepare_records_from_file


def register_lead_upload_bulk_routes(app):
    @app.route("/leads/bulk-upload/file", methods=["POST"])
    def lead_upload_file():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        file_storage = request.files.get("lead_file")
        if not file_storage or not file_storage.filename:
            flash("Please select a CSV file.", "danger")
            return redirect(url_for("bulk_upload_leads"))

        mapping = {
            "name_column":    request.form.get("name_column"),
            "mobile_column":  request.form.get("mobile_column"),
            "email_column":   request.form.get("email_column"),
            "address_column": request.form.get("address_column"),
            "has_header":     request.form.get("has_header") == "1",
        }

        lead_source = (request.form.get("lead_source") or "").strip()
        if not lead_source:
            flash("Please select lead source.", "danger")
            return redirect(url_for("bulk_upload_leads"))

        lead_status          = (request.form.get("lead_status") or "").strip()
        assign_to_user_uuid  = (request.form.get("assign_to_user_uuid") or "").strip()
        batch_name           = (request.form.get("batch_name") or "").strip()

        try:
            records = prepare_records_from_file(file_storage, mapping)
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("bulk_upload_leads"))
        except Exception as error:
            flash(f"File could not be read: {error}", "danger")
            return redirect(url_for("bulk_upload_leads"))

        if not records:
            flash("No rows found in uploaded file.", "warning")
            return redirect(url_for("bulk_upload_leads"))

        conn = get_db_connection()
        try:
            _batch_uuid, imported_count, _batch = create_and_import_lead_batch(
                conn,
                "file",
                batch_name,
                records,
                logged_user_uuid,
                lead_source=lead_source,
                lead_status=lead_status or None,
                assign_to_user_uuid=assign_to_user_uuid or None,
            )
            flash(f"File upload processed! {imported_count} lead(s) imported successfully.", "success")
        except Exception as e:
            flash(f"Failed to process upload: {e}", "danger")
        finally:
            conn.close()

        # Reload same page so user sees updated Last Uploads table
        return redirect(url_for("bulk_upload_leads"))

