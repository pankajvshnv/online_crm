"""
Legacy module for backwards compatibility.
All logic has been migrated to routes/user_report.py.
"""
from routes.user_report import (
    user_report_routes,
    require_user_report_permission,
    lead_monitor_routes,
)

__all__ = [
    "user_report_routes",
    "lead_monitor_routes",
    "require_user_report_permission",
]
