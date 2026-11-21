"""
Central Routes Registry & Initialization for Online CRM.
Registers all modular blueprints and endpoints onto the Flask application.
"""
from flask import render_template
from utils.permissions import require_permission

# Authentication
from routes.auth import auth_routes

# Core CRM Modules
from routes.dashboard import dashboard_routes
from routes.add_lead import add_lead_routes
from routes.lead.all_leads import all_leads_routes
from routes.lead_upload import register_lead_upload_routes
from routes.lead_upload_bulk import register_lead_upload_bulk_routes
from routes.lead_upload_quick import register_lead_upload_quick_routes
from routes.free_trials import free_trial_routes
from routes.followups import followup_routes
from routes.payments import payments_routes

# Communication & Activities
from routes.chat import chat_routes
from routes.email import email_routes
from routes.research import research_routes
from routes.calling_api import calling_apis
from routes.calling_history import calling_history_routes
from routes.search import search_routes
from routes.handbook import handbook_routes
from routes.live_alerts import live_alerts_routes

# Reports
from routes.lead_report import lead_report_routes
from routes.sales_report import sales_report_routes
from routes.employee_report import employee_report_routes
from routes.user_report import user_report_routes

# Settings & Administration
from routes.settings_home import settings_home_routes
from routes.users import user_management
from routes.designations import designation_routes
from routes.role_permissions import role_permission_routes
from routes.product_settings import register_product_routes
from routes.company_settings import register_company_routes
from routes.service_settings import register_service_settings_routes
from routes.extensions import extension_routes
from routes.lead_sources import lead_source_routes
from routes.lead_statuses import lead_status_routes
from routes.lead_role_limits import lead_source_limits


PLACEHOLDER_ROUTES = [
    # Sidebar: Operations Placeholders
    ("/operations/free-trials-operation", "operations_free_trials", "placeholder.html", "operations", "operations_free_trials", "Free Trials Operation", ("operations", "free_trials_operation")),
    ("/operations/followups-operation", "operations_followups", "placeholder.html", "operations", "operations_followups", "Follow-ups Operation", ("operations", "followups_operation")),
    ("/operations/client-operation", "operations_client", "placeholder.html", "operations", "operations_client", "Client Operation", ("operations", "client_operation")),
    ("/operations/contact-operation", "operations_contact", "placeholder.html", "operations", "operations_contact", "Contact Operation", ("operations", "contact_operation")),
]


def register_placeholder_routes(app):
    for rule, endpoint, template, active_group, active_page, page_title, req_perm in PLACEHOLDER_ROUTES:
        def view_func(t=template, ag=active_group, ap=active_page, pt=page_title):
            return render_template(t, active_group=ag, active_page=ap, page_title=pt)

        if req_perm:
            view_func = require_permission(req_perm[0], req_perm[1])(view_func)

        view_func.__name__ = endpoint
        app.add_url_rule(rule, endpoint, view_func)


def init_routes(app):
    """Registers all application modules and endpoints."""
    # Auth & Security
    auth_routes(app)

    # Core Features
    dashboard_routes(app)
    add_lead_routes(app)
    all_leads_routes(app)
    register_lead_upload_routes(app)
    register_lead_upload_bulk_routes(app)
    register_lead_upload_quick_routes(app)
    free_trial_routes(app)
    followup_routes(app)
    payments_routes(app)

    # Communications & Realtime
    chat_routes(app)
    email_routes(app)
    research_routes(app)
    calling_apis(app)
    calling_history_routes(app)
    search_routes(app)
    handbook_routes(app)
    live_alerts_routes(app)

    # Reports
    lead_report_routes(app)
    sales_report_routes(app)
    employee_report_routes(app)
    user_report_routes(app)

    # Settings & User Management
    settings_home_routes(app)
    user_management(app)
    designation_routes(app)
    role_permission_routes(app)
    register_product_routes(app)
    register_company_routes(app)
    register_service_settings_routes(app)
    extension_routes(app)
    lead_source_routes(app)
    lead_status_routes(app)
    lead_source_limits(app)

    # Placeholders
    register_placeholder_routes(app)

    @app.route("/whatsapp", endpoint="whatsapp_home")
    def whatsapp_home():
        from flask import flash, redirect, url_for
        flash("The WhatsApp module has been removed.", "info")
        return redirect(url_for("dashboard"))
