from flask import render_template
from utils.permissions import require_permission


def settings_home_routes(app):
    @require_permission('settings', 'view')
    @app.route("/settings", endpoint="settings_home")
    def settings_home():
        return render_template(
            "settings/settings_home.html",
            active_group="settings",
            active_page="settings_home",
            page_title="Settings Hub"
        )
