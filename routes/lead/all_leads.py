from flask import (
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from config import get_db_connection
from utils.permissions import require_permission, has_permission
from routes.lead.all_leads_actions import (
    process_add_followup,
    process_add_free_trial,
    process_add_sales_order,
    process_assign_leads,
    process_check_field_duplicate,
    process_delete_lead,
    process_dispose_lead,
    process_fetch_leads_from_source,
    process_get_lead_contacts,
    process_get_lead_details_for_so,
    process_get_sales_order_for_edit,
    process_update_sales_order,
    process_get_lead_timeline,
    process_lead_click_to_call,
    process_resume_lead,
    process_save_contact,
    process_save_lead_response,
)
from routes.lead.all_leads_columns import (
    get_lead_table_columns,
)
from routes.lead.all_leads_filters import (
    fetch_lead_filter_context,
)
from routes.lead.all_leads_helpers import (
    fetch_lead_source_limit_buttons,
)
from routes.lead.all_leads_table import (
    fetch_lead_rows,
    get_lead_table_data,
)


def all_leads_routes(app):

    @app.route(
        "/leads",
        endpoint="all_leads",
    )
    def all_leads():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return redirect(url_for("login"))

        try:
            connection = get_db_connection()
            if not connection:
                raise Exception("Database connection failed. Please check MySQL server status or configuration.")

            try:
                with connection.cursor() as cursor:
                    filter_context = fetch_lead_filter_context(cursor, logged_user_uuid)
                    source_limit_buttons = fetch_lead_source_limit_buttons(cursor, logged_user_uuid)

                    cursor.execute("""
                        SELECT id, product_name, weekly, two_weekly, monthly, two_monthly, quarterly, six_monthly, nine_monthly, yearly, eighteen_monthly, twenty_four_monthly
                        FROM products
                        WHERE status = 1
                        ORDER BY product_name ASC
                    """)
                    products = cursor.fetchall()

                    cursor.execute("SELECT setting_key, setting_value FROM system_settings")
                    setting_rows = cursor.fetchall()
                    settings = {r["setting_key"]: r["setting_value"] for r in setting_rows}
            finally:
                connection.close()

            # Shell-first initial render: returns page structure in milliseconds, data is loaded seamlessly via AJAX
            table_data = {
                "success": True,
                "data": [],
                "page": 1,
                "page_size": 10,
                "total": 0,
                "total_pages": 1,
                "sort": "created_at",
                "order": "desc",
            }
            leads = []

            from routes.settings_helpers import resolve_selected_owner
            return render_template(
                "leads/view_all_lead.html",
                leads=leads,
                table_data=table_data,
                products=products,
                settings=settings,
                table_id="allLeadsBootstrapTable",
                api_url="/api/leads/table-data",
                columns=get_lead_table_columns(),
                filters=filter_context["filters"],
                source_limit_buttons=source_limit_buttons,
                page_size=10,
                page_size_options=[10, 25, 50, 100, 500, 1000],
                default_sort="created_at",
                default_order="desc",
                logged_user_uuid=logged_user_uuid,
                selected_owner=resolve_selected_owner(logged_user_uuid),
                active_group="all_leads",
                active_page="all_leads",
                page_title="All Leads",
            )
        except Exception as e:
            print("ERROR RENDERING /leads:", e)
            import traceback
            traceback.print_exc()
            return f"""
            <div style="padding: 30px; font-family: sans-serif;">
                <div style="background: #f8d7da; color: #842029; padding: 20px; border-radius: 8px; border: 1px solid #f5c2c7;">
                    <h3 style="margin-top: 0;">⚠️ /leads Page Render Error</h3>
                    <p><strong>Error Message:</strong> {e}</p>
                    <pre style="background: #fff; padding: 15px; border-radius: 4px; overflow-x: auto; font-size: 13px;">{traceback.format_exc()}</pre>
                </div>
            """, 500

    @app.route(
        "/api/leads/table-data",
        methods=["POST"],
        endpoint="all_leads_table_data",
    )
    def all_leads_table_data():
        logged_user_uuid = session.get(
            "user_uuid"
        )

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        # Security check: Block direct browser address bar URL navigation
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json
        if not is_ajax:
            return jsonify({
                "success": False,
                "message": "Direct browser URL access is strictly forbidden.",
            }), 403

        try:
            payload = request.get_json(silent=True) or {}
            request_params = {**request.args.to_dict(), **payload}

            result = get_lead_table_data(
                logged_user_uuid,
                request_params,
            )

            connection = get_db_connection()
            try:
                with connection.cursor() as cursor:
                    buttons = fetch_lead_source_limit_buttons(cursor, logged_user_uuid)
            finally:
                connection.close()

            result["buttons"] = buttons
            return jsonify(result)

        except Exception as error:
            app.logger.exception(
                "Unable to load lead table data: %s",
                error,
            )

            return jsonify({
                "success": False,
                "message": (
                    "Unable to load leads."
                ),
            }), 500

    @app.route(
        "/api/leads/click-to-call",
        methods=["POST"],
        endpoint="lead_click_to_call",
    )
    def lead_click_to_call():
        logged_user_uuid = session.get(
            "user_uuid"
        )

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = (
            request.get_json(
                silent=True
            )
            or {}
        )

        lead_uuid = str(
            payload.get("lead_uuid")
            or ""
        ).strip()

        if not lead_uuid:
            return jsonify({
                "success": False,
                "message": "Lead is required.",
            }), 400

        action_result = (
            process_lead_click_to_call(
                logged_user_uuid,
                lead_uuid,
                ip_address=request.remote_addr,
            )
        )

        status_code = action_result.pop(
            "status_code",
            200,
        )

        if not action_result.get(
            "success"
        ):
            return jsonify(
                action_result
            ), status_code

        return jsonify(
            action_result["result"]
        ), status_code

    @app.route(
        "/api/leads/fetch-from-source",
        methods=["POST"],
        endpoint="fetch_leads_from_source",
    )
    def fetch_leads_from_source():
        logged_user_uuid = session.get(
            "user_uuid"
        )

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = (
            request.get_json(
                silent=True
            )
            or {}
        )

        source_id = payload.get("source_id")

        if not source_id:
            return jsonify({
                "success": False,
                "message": "Source is required.",
            }), 400

        action_result = (
            process_fetch_leads_from_source(
                logged_user_uuid,
                source_id,
                ip_address=request.remote_addr,
            )
        )

        status_code = action_result.pop(
            "status_code",
            200,
        )

        category = "success" if action_result.get("success") else "warning"
        if action_result.get("message"):
            flash(action_result["message"], category)

        return jsonify(
            action_result
        ), status_code

    @app.route(
        "/api/leads/save-response",
        methods=["POST"],
        endpoint="save_lead_response",
    )
    @require_permission("leads", "edit")
    def save_lead_response():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = request.get_json(silent=True) or {}
        lead_uuid = str(payload.get("lead_uuid") or "").strip()
        status_name = str(payload.get("status_name") or payload.get("status") or "").strip()
        comment = str(payload.get("comment") or "").strip()

        if not lead_uuid:
            return jsonify({
                "success": False,
                "message": "Lead is required.",
            }), 400

        if not status_name or status_name == "no_status":
            return jsonify({
                "success": False,
                "message": "Please select a valid Lead Status.",
            }), 400

        action_result = process_save_lead_response(
            logged_user_uuid,
            lead_uuid,
            status_name,
            comment,
            ip_address=request.remote_addr,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/leads/dispose",
        methods=["POST"],
        endpoint="dispose_lead",
    )
    @app.route(
        "/leads/dispose",
        methods=["POST"],
        endpoint="dispose_lead_alt",
    )
    @require_permission("leads", "view")
    def dispose_lead():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = request.get_json(silent=True) or request.form or {}
        lead_uuid = str(payload.get("lead_uuid") or payload.get("id") or "").strip()
        status_name = str(payload.get("status_name") or payload.get("status_id") or "").strip()
        reason = str(payload.get("comment") or payload.get("reason") or "").strip()

        if not lead_uuid:
            return jsonify({
                "success": False,
                "message": "Lead is required.",
            }), 400

        action_result = process_dispose_lead(
            logged_user_uuid,
            lead_uuid,
            status_name,
            reason,
            ip_address=request.remote_addr,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/leads/resume",
        methods=["POST"],
        endpoint="resume_lead_api",
    )
    @require_permission("leads", "view")
    def resume_lead_api():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = request.get_json(silent=True) or request.form or {}
        lead_uuid = str(payload.get("lead_uuid") or payload.get("id") or "").strip()

        if not lead_uuid:
            return jsonify({
                "success": False,
                "message": "Lead is required.",
            }), 400

        action_result = process_resume_lead(
            logged_user_uuid,
            lead_uuid,
            ip_address=request.remote_addr,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/leads/delete",
        methods=["POST"],
        endpoint="delete_lead",
    )
    def delete_lead():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = request.get_json(silent=True) or {}
        lead_uuids = payload.get("lead_uuids") or payload.get("lead_uuid") or []

        if not lead_uuids:
            return jsonify({
                "success": False,
                "message": "Please select at least one lead to delete.",
            }), 400

        action_result = process_delete_lead(
            logged_user_uuid,
            lead_uuids,
            ip_address=request.remote_addr,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/contacts/delete",
        methods=["POST"],
        endpoint="delete_contacts_api",
    )
    @require_permission("contacts", "delete")
    def delete_contacts_api():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Login is required."}), 401

        payload = request.get_json(silent=True) or {}
        contact_uuids = payload.get("contact_uuids") or []
        if isinstance(contact_uuids, str):
            contact_uuids = [contact_uuids]
        lead_uuids = payload.get("lead_uuids") or []
        if isinstance(lead_uuids, str):
            lead_uuids = [lead_uuids]

        if not contact_uuids and not lead_uuids:
            return jsonify({"success": False, "message": "Please select at least one contact to delete."}), 400

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                deleted_count = 0
                if contact_uuids:
                    placeholders = ", ".join(["%s"] * len(contact_uuids))
                    cursor.execute(f"DELETE FROM contacts WHERE contact_uuid IN ({placeholders})", tuple(contact_uuids))
                    deleted_count += cursor.rowcount
                elif lead_uuids:
                    placeholders = ", ".join(["%s"] * len(lead_uuids))
                    cursor.execute(f"DELETE FROM contacts WHERE lead_id IN (SELECT id FROM leads WHERE lead_uuid IN ({placeholders}))", tuple(lead_uuids))
                    deleted_count += cursor.rowcount

                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({"success": False, "message": f"Error deleting contacts: {str(e)}"}), 500
        finally:
            if conn:
                conn.close()

        return jsonify({"success": True, "message": f"Successfully deleted {deleted_count} contact(s)."})

    @app.route(
        "/api/leads/assign",
        methods=["POST"],
        endpoint="api_assign_leads",
    )
    def api_assign_leads():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        can_assign = (
            has_permission("leads", "transfer") or
            has_permission("followups", "transfer") or
            has_permission("free_trials", "transfer") or
            has_permission("contacts", "transfer")
        )
        if not can_assign:
            return jsonify({
                "success": False,
                "message": "Access Denied: You do not have permission to assign.",
            }), 403

        payload = request.get_json(silent=True) or {}
        target_user_uuid = payload.get("target_user_uuid") or payload.get("user_uuid") or "keep_same"
        lead_uuids = payload.get("lead_uuids") or payload.get("lead_uuid") or []
        new_source = payload.get("new_source") or payload.get("lead_source")
        reset_data = bool(payload.get("reset_data"))
        apply_all_matching = bool(payload.get("apply_all_matching"))
        filter_params = payload.get("filters") or request.args

        action_result = process_assign_leads(
            logged_user_uuid=logged_user_uuid,
            target_user_uuid=target_user_uuid,
            lead_uuids=lead_uuids,
            new_source=new_source,
            reset_data=reset_data,
            apply_all_matching=apply_all_matching,
            filter_params=filter_params,
            ip_address=request.remote_addr,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @require_permission('leads', 'view_history')
    @app.route(
        "/api/leads/timeline",
        methods=["POST"],
        endpoint="api_get_lead_timeline",
    )
    def api_get_lead_timeline():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        # Security check: Block direct browser address bar URL navigation
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json
        if not is_ajax:
            return jsonify({
                "success": False,
                "message": "Direct browser URL access is strictly forbidden.",
            }), 403

        payload = request.get_json(silent=True) or {}
        target_lead_uuid = payload.get("lead_uuid") or request.args.get("lead_uuid")
        page = payload.get("page") or request.args.get("page", 1)
        limit = payload.get("limit") or payload.get("page_size") or request.args.get("limit", 15)

        if not target_lead_uuid:
            return jsonify({
                "success": False,
                "message": "Lead identifier is required.",
            }), 400

        action_result = process_get_lead_timeline(
            logged_user_uuid=logged_user_uuid,
            lead_uuid=target_lead_uuid,
            page=page,
            limit=limit,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/leads/save-contact",
        methods=["POST"],
        endpoint="api_save_lead_contact",
    )
    def api_save_lead_contact():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = request.get_json(silent=True) or {}
        lead_uuid = payload.get("lead_uuid")
        contact_name = payload.get("contact_name")
        mobile_number = payload.get("mobile_number")
        email = payload.get("email")
        address = payload.get("address")
        product_id = payload.get("product_id")
        plan_type = payload.get("plan_type")
        notes = payload.get("notes")
        status_name = payload.get("status_name")
        status_id = payload.get("status_id")

        action_result = process_save_contact(
            logged_user_uuid=logged_user_uuid,
            lead_uuid=lead_uuid,
            contact_name=contact_name,
            mobile_number=mobile_number,
            email=email,
            address=address,
            product_id=product_id,
            plan_type=plan_type,
            notes=notes,
            status_name=status_name,
            status_id=status_id,
            ip_address=request.remote_addr,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/leads/add-followup",
        methods=["POST"],
        endpoint="api_add_lead_followup",
    )
    def api_add_lead_followup():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = request.get_json(silent=True) or {}
        lead_uuid = payload.get("lead_uuid")
        followup_date = payload.get("followup_date")
        remarks = payload.get("remarks")
        name = payload.get("name")
        email = payload.get("email")
        address = payload.get("address")

        lead_status = payload.get("lead_status")

        action_result = process_add_followup(
            logged_user_uuid=logged_user_uuid,
            lead_uuid=lead_uuid,
            followup_date=followup_date,
            remarks=remarks,
            name=name,
            email=email,
            address=address,
            lead_status=lead_status,
            ip_address=request.remote_addr,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/leads/add-free-trial",
        methods=["POST"],
        endpoint="api_add_free_trial",
    )
    def api_add_free_trial():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = request.get_json(silent=True) or {}
        lead_uuid = payload.get("lead_uuid")
        product_id = payload.get("product_id")
        start_date = payload.get("start_date")
        notes = payload.get("notes")
        lead_status = payload.get("lead_status")
        name = payload.get("name")

        action_result = process_add_free_trial(
            logged_user_uuid=logged_user_uuid,
            lead_uuid=lead_uuid,
            product_id=product_id,
            start_date=start_date,
            notes=notes,
            lead_status=lead_status,
            name=name,
            ip_address=request.remote_addr,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/leads/get-free-trial-config",
        methods=["POST"],
        endpoint="api_get_free_trial_config",
    )
    def api_get_free_trial_config():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, product_name
                    FROM products
                    WHERE status = 1
                    ORDER BY product_name ASC
                """)
                prods = cursor.fetchall()

                cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'free_trial_days' LIMIT 1")
                row = cursor.fetchone()
                trial_days = int(row["setting_value"]) if (row and str(row.get("setting_value", "")).isdigit()) else 7

                return jsonify({
                    "success": True,
                    "free_trial_days": trial_days,
                    "products": prods,
                })
        finally:
            conn.close()

    @app.route(
        "/leads/select-sales-order-lead",
        methods=["POST"],
        endpoint="select_sales_order_lead",
    )
    def select_sales_order_lead():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            flash("Login is required.", "warning")
            return redirect(url_for("login"))

        lead_uuid = request.form.get("lead_uuid")
        if lead_uuid:
            session["active_so_lead_uuid"] = lead_uuid
        return redirect(url_for("create_sales_order_page"))

    @app.route(
        "/leads/sales-order",
        methods=["GET", "POST"],
        endpoint="create_sales_order_page",
    )
    @app.route(
        "/leads/create-sales-order",
        methods=["GET", "POST"],
    )
    def create_sales_order_page():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            flash("Login is required to access sales order.", "warning")
            return redirect(url_for("login"))

        lead_uuid = (request.args.get("lead_uuid") or request.form.get("lead_uuid") or session.get("active_so_lead_uuid") or "").strip()
        if lead_uuid:
            session["active_so_lead_uuid"] = lead_uuid

        if not lead_uuid:
            flash("Please select a lead to create a sales order.", "warning")
            return redirect(url_for("all_leads"))

        details = process_get_lead_details_for_so(
            logged_user_uuid=logged_user_uuid,
            lead_uuid=lead_uuid,
        )

        if not details.get("success"):
            flash(details.get("message", "Lead not found."), "danger")
            return redirect(url_for("all_leads"))

        error_message = None
        form_data = {}

        if request.method == "POST":
            form_data = request.form.to_dict()
            action_result = process_add_sales_order(
                logged_user_uuid=logged_user_uuid,
                lead_uuid=lead_uuid,
                invoice_name=form_data.get("invoice_name"),
                email=form_data.get("email"),
                address=form_data.get("address"),
                state=form_data.get("state"),
                city=form_data.get("city"),
                gst_number=form_data.get("gst_number"),
                pan_number=form_data.get("pan_number"),
                aadhaar_number=form_data.get("aadhaar_number"),
                dob=form_data.get("dob"),
                product_id=form_data.get("product_id"),
                plan_name=form_data.get("plan_name"),
                service_start_date=form_data.get("service_start_date"),
                service_expiry_date=form_data.get("service_expiry_date"),
                gross_amount=form_data.get("gross_amount", 0.0),
                tax_percentage=details.get("tax_percentage", 18.0),
                tax_amount=form_data.get("tax_amount", 0.0),
                net_amount=form_data.get("net_amount", 0.0),
                payment_mode=form_data.get("payment_mode"),
                reference_number=form_data.get("reference_number"),
                payment_date=form_data.get("payment_date"),
                service_mode=form_data.get("service_mode"),
                notes=form_data.get("notes"),
                ip_address=request.remote_addr,
            )

            if action_result.get("success"):
                flash(action_result.get("message", "Sales order submitted successfully!"), "success")
                return redirect(url_for("create_sales_order_page"))
            else:
                error_message = action_result.get("message", "Failed to submit sales order.")

        return render_template(
            "leads/create_sales_order.html",
            lead=details.get("lead"),
            products=details.get("products"),
            tax_percentage=details.get("tax_percentage"),
            product_expiry_mode=details.get("product_expiry_mode", "auto"),
            existing_orders=details.get("existing_orders"),
            has_pending_so=details.get("has_pending_so"),
            pending_order_number=details.get("pending_order_number"),
            pending_so=details.get("pending_so"),
            latest_so=details.get("latest_so", {}),
            error_message=error_message,
            form_data=form_data,
            active_group="payments",
            active_page="all_payments",
        )

    @app.route(
        "/leads/edit-sales-order",
        methods=["GET", "POST"],
        endpoint="edit_sales_order_clean_page",
    )
    @app.route(
        "/leads/edit-sales-order/<sales_order_uuid>",
        methods=["GET", "POST"],
        endpoint="edit_sales_order_page",
    )
    def edit_sales_order_page(sales_order_uuid=None):
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            flash("Login is required to access sales order.", "warning")
            return redirect(url_for("login"))

        if sales_order_uuid:
            session["active_edit_so_uuid"] = sales_order_uuid
        else:
            sales_order_uuid = session.get("active_edit_so_uuid")

        if not sales_order_uuid:
            flash("Please select a sales order to edit.", "warning")
            return redirect(url_for("all_payments"))

        details = process_get_sales_order_for_edit(
            logged_user_uuid=logged_user_uuid,
            sales_order_uuid=sales_order_uuid,
        )

        if not details.get("success"):
            flash(details.get("message", "Sales order not found."), "danger")
            return redirect(url_for("all_payments"))

        sales_order = details.get("sales_order") or {}
        error_message = None

        if request.method == "POST":
            form_data = request.form.to_dict()
            action_result = process_update_sales_order(
                logged_user_uuid=logged_user_uuid,
                sales_order_uuid=sales_order_uuid,
                invoice_name=form_data.get("invoice_name"),
                email=form_data.get("email"),
                address=form_data.get("address"),
                state=form_data.get("state"),
                city=form_data.get("city"),
                gst_number=form_data.get("gst_number"),
                pan_number=form_data.get("pan_number"),
                aadhaar_number=form_data.get("aadhaar_number"),
                dob=form_data.get("dob"),
                product_id=form_data.get("product_id"),
                product_name=form_data.get("product_name"),
                plan_name=form_data.get("plan_name"),
                service_start_date=form_data.get("service_start_date"),
                service_expiry_date=form_data.get("service_expiry_date"),
                service_mode=form_data.get("service_mode"),
                gross_amount=form_data.get("gross_amount"),
                payment_mode=form_data.get("payment_mode"),
                payment_date=form_data.get("payment_date"),
                reference_number=form_data.get("reference_number"),
                notes=form_data.get("notes"),
                order_status=form_data.get("order_status"),
                kyc_status=form_data.get("kyc_status"),
            )

            if action_result.get("success"):
                flash(action_result.get("message", "Sales order updated successfully!"), "success")
                return redirect(url_for("all_payments"))
            else:
                error_message = action_result.get("message", "Failed to update sales order.")

        return render_template(
            "leads/edit_sales_order.html",
            sales_order=sales_order,
            lead=details.get("lead"),
            products=details.get("products"),
            error_message=error_message,
            active_group="payments",
            active_page="all_payments",
        )

    @app.route(
        "/leads/view-sales-order",
        methods=["GET"],
        endpoint="view_sales_order_clean_page",
    )
    @app.route(
        "/leads/view-sales-order/<sales_order_uuid>",
        methods=["GET"],
        endpoint="view_sales_order_page",
    )
    def view_sales_order_page(sales_order_uuid=None):
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            flash("Login is required to access sales order.", "warning")
            return redirect(url_for("login"))

        if sales_order_uuid:
            session["active_view_so_uuid"] = sales_order_uuid
            return redirect(url_for("view_sales_order_clean_page"))
        else:
            sales_order_uuid = session.get("active_view_so_uuid")

        if not sales_order_uuid:
            flash("Please select a sales order to view.", "warning")
            return redirect(url_for("all_payments"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        so.*, 
                        l.lead_uuid, l.name AS lead_name, l.mobile_number, l.email AS lead_email, l.address AS lead_address,
                        u_creator.full_name AS creator_name,
                        u_approved.full_name AS approver_name
                    FROM sales_orders so
                    JOIN leads l ON l.id = so.lead_id
                    LEFT JOIN users u_creator ON u_creator.id = so.created_by_user_id
                    LEFT JOIN users u_approved ON u_approved.id = so.approved_by_user_id
                    WHERE so.sales_order_uuid = %s
                    LIMIT 1
                """, (sales_order_uuid,))
                so = cursor.fetchone()
                if not so:
                    flash("Sales Order not found.", "warning")
                    return redirect(url_for("all_payments"))

                for k in ["gross_amount", "net_amount", "tax_amount", "tax_percentage"]:
                    if so.get(k) is not None:
                        so[k] = float(so[k])

                from routes.settings_helpers import (
                    fetch_logged_user_settings,
                    fetch_last_dialed_lead_uuid,
                    build_mobile_button_context,
                )

                user_settings = fetch_logged_user_settings(cursor, logged_user_uuid)
                last_dialed_lead_uuid = fetch_last_dialed_lead_uuid(cursor, logged_user_uuid)

                raw_mob = str(so.get("mobile_number") or "").strip()
                lead_uuid_val = str(so.get("lead_uuid") or "").strip()
                lead_name_val = str(so.get("lead_name") or "Client").strip()
                call_status_val = int(so.get("call_status") or 0)

                mobile_ctx = build_mobile_button_context(
                    raw_mobile=raw_mob,
                    lead_uuid=lead_uuid_val,
                    lead_name=lead_name_val,
                    call_status=call_status_val,
                    user_settings=user_settings,
                    last_dialed_lead_uuid=last_dialed_lead_uuid,
                )

                lead = {
                    "lead_uuid": lead_uuid_val,
                    "name": lead_name_val,
                    "email": so.get("lead_email"),
                    "address": so.get("lead_address"),
                    "mobile_ctx": mobile_ctx,
                }
        finally:
            conn.close()

        return render_template(
            "leads/view_sales_order.html",
            so=so,
            lead=lead,
            active_group="payments",
            active_page="all_payments",
            page_title=f"Sales Order - #{so.get('order_number')}",
            page_heading=f"Sales Order Details: {so.get('order_number')}"
        )

    @app.route(
        "/api/leads/get-lead-details-for-so",
        methods=["POST"],
        endpoint="api_get_lead_details_for_so",
    )
    def api_get_lead_details_for_so():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = request.get_json(silent=True) or {}
        lead_uuid = payload.get("lead_uuid")

        action_result = process_get_lead_details_for_so(
            logged_user_uuid=logged_user_uuid,
            lead_uuid=lead_uuid,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/leads/add-sales-order",
        methods=["POST"],
        endpoint="api_add_sales_order",
    )
    def api_add_sales_order():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = request.get_json(silent=True) or {}
        action_result = process_add_sales_order(
            logged_user_uuid=logged_user_uuid,
            lead_uuid=payload.get("lead_uuid"),
            invoice_name=payload.get("invoice_name"),
            email=payload.get("email"),
            address=payload.get("address"),
            state=payload.get("state"),
            city=payload.get("city"),
            gst_number=payload.get("gst_number"),
            pan_number=payload.get("pan_number"),
            aadhaar_number=payload.get("aadhaar_number"),
            dob=payload.get("dob"),
            product_id=payload.get("product_id"),
            plan_name=payload.get("plan_name"),
            service_start_date=payload.get("service_start_date"),
            service_expiry_date=payload.get("service_expiry_date"),
            gross_amount=payload.get("gross_amount", 0.0),
            tax_percentage=payload.get("tax_percentage", 18.0),
            tax_amount=payload.get("tax_amount", 0.0),
            net_amount=payload.get("net_amount", 0.0),
            payment_mode=payload.get("payment_mode"),
            reference_number=payload.get("reference_number"),
            notes=payload.get("notes"),
            ip_address=request.remote_addr,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/leads/check-field-duplicate",
        methods=["POST"],
        endpoint="api_check_field_duplicate",
    )
    def api_check_field_duplicate():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"is_duplicate": False, "message": "Unauthorized"}), 401
        
        payload = request.get_json(silent=True) or {}
        lead_uuid = payload.get("lead_uuid")
        field_name = payload.get("field_name")
        field_value = payload.get("field_value")

        res = process_check_field_duplicate(lead_uuid, field_name, field_value)
        return jsonify(res)

    @app.route(
        "/api/leads/update-sales-order",
        methods=["POST"],
        endpoint="api_update_sales_order",
    )
    def api_update_sales_order():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = request.get_json(silent=True) or {}
        action_result = process_update_sales_order(
            logged_user_uuid=logged_user_uuid,
            sales_order_uuid=payload.get("sales_order_uuid"),
            invoice_name=payload.get("invoice_name"),
            email=payload.get("email"),
            address=payload.get("address"),
            state=payload.get("state"),
            city=payload.get("city"),
            gst_number=payload.get("gst_number"),
            pan_number=payload.get("pan_number"),
            aadhaar_number=payload.get("aadhaar_number"),
            dob=payload.get("dob"),
            product_id=payload.get("product_id"),
            plan_name=payload.get("plan_name"),
            gross_amount=payload.get("gross_amount"),
            tax_percentage=payload.get("tax_percentage", 18.0),
            service_start_date=payload.get("service_start_date"),
            service_expiry_date=payload.get("service_expiry_date"),
            payment_mode=payload.get("payment_mode"),
            reference_number=payload.get("reference_number"),
            notes=payload.get("notes"),
            order_status=payload.get("order_status"),
            kyc_status=payload.get("kyc_status"),
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/leads/get-contacts",
        methods=["POST"],
        endpoint="api_get_lead_contacts",
    )
    def api_get_lead_contacts():
        logged_user_uuid = session.get("user_uuid")

        if not logged_user_uuid:
            return jsonify({
                "success": False,
                "message": "Login is required.",
            }), 401

        payload = request.get_json(silent=True) or {}
        lead_uuid = payload.get("lead_uuid") or request.args.get("lead_uuid")

        action_result = process_get_lead_contacts(
            logged_user_uuid=logged_user_uuid,
            lead_uuid=lead_uuid,
        )

        status_code = action_result.pop("status_code", 200)
        return jsonify(action_result), status_code

    @app.route(
        "/api/leads/update-basic-info",
        methods=["POST"],
        endpoint="api_update_lead_basic_info",
    )
    def api_update_lead_basic_info():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Login is required."}), 401

        payload = request.get_json(silent=True) or {}
        lead_uuid = payload.get("lead_uuid")
        name = (payload.get("name") or "").strip()
        email = (payload.get("email") or "").strip()
        address = (payload.get("address") or "").strip()
        state = (payload.get("state") or "").strip()
        city = (payload.get("city") or "").strip()

        if not lead_uuid:
            return jsonify({"success": False, "message": "Lead UUID is required."}), 400
        if not name:
            return jsonify({"success": False, "message": "Lead name is required."}), 400

        connection = get_db_connection()
        if not connection:
            return jsonify({"success": False, "message": "Database connection error."}), 500

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE leads
                    SET name = %s,
                        email = %s,
                        address = %s,
                        state = %s,
                        city = %s,
                        updated_at = NOW()
                    WHERE lead_uuid = %s
                """, (name, email or None, address or None, state or None, city or None, lead_uuid))
                connection.commit()
                return jsonify({"success": True, "message": "Lead basic info updated successfully!"})
        except Exception as error:
            return jsonify({"success": False, "message": f"Unable to update lead: {str(error)}"}), 500
        finally:
            connection.close()

    @app.route("/contacts", methods=["GET"], endpoint="view_contacts")
    def view_contacts():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return redirect(url_for("login"))

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                from routes.settings_helpers import fetch_owner_filter_options, resolve_selected_owner
                from utils.permissions import has_permission
                from routes.lead_action import get_current_user
                user = get_current_user(cursor, logged_user_uuid)
                is_global = bool(user.get("is_admin")) or str(user.get("role_name", "")).lower() == "admin" or has_permission('global_access_scope', 'global_data_access')

                owner_context = fetch_owner_filter_options(cursor, logged_user_uuid)
                owners = owner_context["owners"]
                allowed_user_ids = None
                if not is_global:
                    allowed_user_ids = owner_context["allowed_user_ids"]

                # 1. Fetch active products
                cursor.execute("""
                    SELECT id, product_name
                    FROM products
                    WHERE status = 1
                    ORDER BY product_name ASC
                """)
                products = cursor.fetchall()

                target_lead_uuid = request.args.get("lead_uuid") or ""

                sql = """
                    SELECT 
                        c.id, c.contact_uuid, c.contact_name, c.mobile_number, c.email, c.address,
                        c.plan_type, c.notes, c.created_at,
                        l.id as lead_id, l.lead_uuid, l.name as lead_name,
                        p.id as product_id, p.product_name,
                        COALESCE(u.full_name, c.created_by_name, 'System') as created_by_name,
                        ow.user_uuid as owner_uuid, COALESCE(ow.full_name, 'Unassigned') as owner_name
                    FROM contacts c
                    JOIN leads l ON c.lead_id = l.id
                    LEFT JOIN products p ON c.product_id = p.id
                    LEFT JOIN users u ON c.created_by_user_id = u.id
                    LEFT JOIN users ow ON l.current_owner_user_id = ow.id
                    WHERE 1=1
                """
                params = []

                if allowed_user_ids:
                    placeholders = ", ".join(["%s"] * len(allowed_user_ids))
                    sql += f" AND (l.current_owner_user_id IN ({placeholders}) OR l.created_by IN ({placeholders}))"
                    params.extend(allowed_user_ids)
                    params.extend(allowed_user_ids)

                if target_lead_uuid:
                    sql += " AND (l.lead_uuid = %s OR l.id = %s)"
                    params.extend([target_lead_uuid, int(target_lead_uuid) if str(target_lead_uuid).isdigit() else -1])

                sql += " ORDER BY c.id DESC"
                cursor.execute(sql, params)
                contacts = cursor.fetchall()

                from routes.settings_helpers import fetch_logged_user_settings, fetch_last_dialed_lead_uuid, apply_mobile_and_last_dialed_context
                user_settings = fetch_logged_user_settings(cursor, logged_user_uuid)
                last_dialed_lead_uuid = fetch_last_dialed_lead_uuid(cursor, logged_user_uuid)

                for c in contacts:
                    apply_mobile_and_last_dialed_context(c, user_settings, last_dialed_lead_uuid)
                    c["client_code"] = str(c["lead_id"])
                    c["created_at_fmt"] = c["created_at"].strftime("%d %b %Y, %I:%M %p") if c.get("created_at") else ""

        finally:
            connection.close()

        plan_types = [
            "Weekly", "Two Weekly", "Monthly", "Two Monthly",
            "Quarterly", "Six Monthly", "Nine Monthly", "Yearly",
            "Eighteen Monthly", "Twenty Four Monthly"
        ]

        return render_template(
            "leads/view_contacts.html",
            contacts=contacts,
            products=products,
            plan_types=plan_types,
            owners=owners,
            logged_user_uuid=logged_user_uuid,
            selected_owner=resolve_selected_owner(logged_user_uuid),
            target_lead_uuid=target_lead_uuid,
            active_group="contacts",
            active_page="view_contacts",
            page_title="View Contacts",
            page_heading="Contact Details",
        )

    @app.route("/api/contacts/table-data", methods=["POST"], endpoint="contacts_table_data")
    def contacts_table_data():
        logged_user_uuid = session.get("user_uuid")
        if not logged_user_uuid:
            return jsonify({"success": False, "message": "Login is required."}), 401

        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json
        if not is_ajax:
            return jsonify({"success": False, "message": "Direct browser URL access is strictly forbidden."}), 403

        try:
            payload = request.get_json(silent=True) or {}
            request_params = {**request.args.to_dict(), **payload}

            connection = get_db_connection()
            try:
                with connection.cursor() as cursor:
                    from routes.settings_helpers import fetch_user_tree
                    from utils.permissions import has_permission
                    from routes.lead_action import get_current_user
                    user = get_current_user(cursor, logged_user_uuid)
                    is_global = bool(user.get("is_admin")) or str(user.get("role_name", "")).lower() == "admin" or has_permission('global_access_scope', 'global_data_access')

                    allowed_user_ids = None
                    if not is_global:
                        allowed_user_ids, allowed_user_uuids = fetch_user_tree(cursor, logged_user_uuid)

                    page = int(request_params.get("page") or 1)
                    page_size = int(request_params.get("page_size") or 25)
                    search = str(request_params.get("search") or "").strip()
                    product_id = request_params.get("product_id") or ""
                    plan_type = request_params.get("plan_type") or ""
                    owner_uuid = request_params.get("owner") or ""
                    target_lead_uuid = request_params.get("lead_uuid") or ""

                    where_clauses = ["1=1"]
                    params = []

                    if allowed_user_ids:
                        placeholders = ", ".join(["%s"] * len(allowed_user_ids))
                        where_clauses.append(f"(l.current_owner_user_id IN ({placeholders}) OR l.created_by IN ({placeholders}))")
                        params.extend(allowed_user_ids)
                        params.extend(allowed_user_ids)

                    if target_lead_uuid:
                        where_clauses.append("(l.lead_uuid = %s OR l.id = %s)")
                        params.extend([target_lead_uuid, int(target_lead_uuid) if str(target_lead_uuid).isdigit() else -1])

                    if product_id and product_id != "all":
                        where_clauses.append("c.product_id = %s")
                        params.append(product_id)

                    if plan_type and plan_type != "all":
                        where_clauses.append("c.plan_type = %s")
                        params.append(plan_type)

                    if owner_uuid and owner_uuid != "all":
                        if owner_uuid == "unassigned":
                            where_clauses.append("(l.current_owner_user_id IS NULL OR ow.id IS NULL)")
                        else:
                            cursor.execute("SELECT id FROM users WHERE user_uuid = %s LIMIT 1", (owner_uuid,))
                            usr = cursor.fetchone()
                            if usr:
                                where_clauses.append("(l.current_owner_user_id = %s OR c.created_by_user_id = %s)")
                                params.extend([usr["id"], usr["id"]])

                    if search:
                        where_clauses.append("(c.contact_name LIKE %s OR c.mobile_number LIKE %s OR c.email LIKE %s OR l.name LIKE %s OR p.product_name LIKE %s OR c.notes LIKE %s)")
                        like_str = f"%{search}%"
                        params.extend([like_str, like_str, like_str, like_str, like_str, like_str])

                    where_sql = " AND ".join(where_clauses)

                    count_sql = f"""
                        SELECT COUNT(*) as cnt
                        FROM contacts c
                        JOIN leads l ON c.lead_id = l.id
                        LEFT JOIN products p ON c.product_id = p.id
                        LEFT JOIN users ow ON l.current_owner_user_id = ow.id
                        WHERE {where_sql}
                    """
                    cursor.execute(count_sql, params)
                    cnt_row = cursor.fetchone()
                    total = cnt_row["cnt"] if cnt_row else 0

                    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1
                    page = max(1, min(page, total_pages))
                    offset = (page - 1) * page_size

                    data_sql = f"""
                        SELECT 
                            c.id, c.contact_uuid, c.contact_name, c.mobile_number, c.email, c.address,
                            c.plan_type, c.notes, c.created_at,
                            l.id as lead_id, l.lead_uuid, l.name as lead_name, l.call_status,
                            p.id as product_id, p.product_name,
                            COALESCE(u.full_name, c.created_by_name, 'System') as created_by_name,
                            ow.user_uuid as owner_uuid, COALESCE(ow.full_name, 'Unassigned') as owner_name
                        FROM contacts c
                        JOIN leads l ON c.lead_id = l.id
                        LEFT JOIN products p ON c.product_id = p.id
                        LEFT JOIN users u ON c.created_by_user_id = u.id
                        LEFT JOIN users ow ON l.current_owner_user_id = ow.id
                        WHERE {where_sql}
                        ORDER BY c.id DESC
                        LIMIT %s OFFSET %s
                    """
                    cursor.execute(data_sql, params + [page_size, offset])
                    rows = cursor.fetchall()

                    formatted_data = []
                    from routes.settings_helpers import fetch_logged_user_settings, format_mobile_display, fetch_last_dialed_lead_uuid
                    user_settings = fetch_logged_user_settings(cursor, logged_user_uuid)
                    last_dialed_lead_uuid = fetch_last_dialed_lead_uuid(cursor, logged_user_uuid)

                    show_hide = int(user_settings.get("number_show_hide", 1)) if user_settings else 1
                    for r in rows:
                        raw_mob = r.get("mobile_number") or ""
                        display_text, dec_mob = format_mobile_display(raw_mob, user_settings)
                        safe_mob = display_text if show_hide == 1 else raw_mob
                        safe_dec = display_text if show_hide == 1 else dec_mob
                        formatted_data.append({
                            "id": r["id"],
                            "contact_uuid": r["contact_uuid"],
                            "lead_id": r["lead_id"],
                            "lead_uuid": r["lead_uuid"],
                            "client_code": str(r["lead_id"]),
                            "lead_name": r.get("lead_name") or "",
                            "contact_name": r.get("contact_name") or "",
                            "mobile_number": safe_mob,
                            "decrypted_mobile": safe_dec,
                            "mobile_display": display_text,
                            "click_to_call_active": (int(user_settings.get("click_to_call", 0)) == 1) if user_settings else True,
                            "is_last_dialed": bool(r.get("lead_uuid") and last_dialed_lead_uuid and str(r["lead_uuid"]) == str(last_dialed_lead_uuid)),
                            "call_status": r.get("call_status", 0),
                            "email": r.get("email") or "",
                            "address": r.get("address") or "",
                            "product_name": r.get("product_name") or "None",
                            "plan_type": r.get("plan_type") or "None",
                            "notes": r.get("notes") or "",
                            "owner_name": r.get("owner_name") or "Unassigned",
                            "owner_uuid": r.get("owner_uuid") or "",
                            "created_by_name": r.get("created_by_name") or "System",
                            "created_at_fmt": r["created_at"].strftime("%d %b %Y, %I:%M %p") if r.get("created_at") else "",
                        })

                    return jsonify({
                        "success": True,
                        "data": formatted_data,
                        "total": total,
                        "page": page,
                        "page_size": page_size,
                        "total_pages": total_pages,
                    })
            finally:
                connection.close()
        except Exception as error:
            app.logger.exception("Unable to load contact table data: %s", error)
            return jsonify({"success": False, "message": "Unable to load contacts."}), 500