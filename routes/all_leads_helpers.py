from routes.settings_helpers import (
    decrypt_mobile,
    fetch_lead_source_limit_buttons,
    fetch_logged_user_settings,
    fetch_user_tree,
    get_page_size_options,
    mask_mobile_number,
    serialize_rows,
)


ACTIVITY_ICONS = (
    ("has_contact", "Contact", "mdi mdi-account-outline", "text-primary"),
    ("has_followup", "Follow-up", "mdi mdi-calendar-clock-outline", "text-success"),
    ("has_free_trial", "Free Trial", "mdi mdi-flask-outline", "text-warning"),
    ("has_so", "Sales Order", "mdi mdi-file-document-outline", "text-danger"),
)


def build_lead_activity_html(row):
    icons = []

    for field, title, icon, active_class in ACTIVITY_ICONS:
        icon_class = active_class if row[field] == 1 else "text-muted opacity-25"

        icons.append(
            f'<i class="{icon} {icon_class} me-2" '
            f'title="{title}" aria-label="{title}"></i>'
        )

    return "".join(icons)


def build_lead_activity_text(row):
    icons = []

    icons.append(
        "👤" if row["has_contact"] == 1 else "○"
    )

    icons.append(
        "📅" if row["has_followup"] == 1 else "○"
    )

    icons.append(
        "🧪" if row["has_free_trial"] == 1 else "○"
    )

    icons.append(
        "📄" if row["has_so"] == 1 else "○"
    )

    return "  ".join(icons)

# Fetch leads visible to the logged user hierarchy.
def fetch_all_leads(cursor, allowed_user_uuids, user_settings):
    if not allowed_user_uuids:
        return []

    placeholders = ", ".join(["%s"] * len(allowed_user_uuids))

    cursor.execute(
        f"""
        SELECT
            l.id,
            l.lead_uuid,
            l.name,
            l.mobile_number,
            l.email,
            l.address,
            l.lead_source,
            ls.source_name AS source_name,
            ls.id AS source_id,
            l.lead_status,
            l.call_status,
            l.current_owner_user_id,
            l.lead_batch_id,
            u.user_uuid AS owner_uuid,
            u.user_uuid AS user_uuid,
            u.user_uuid AS current_owner_user_uuid,
            u.full_name AS owner_name,
            l.created_at,
            l.updated_at,
            (CASE WHEN EXISTS (SELECT 1 FROM contacts c WHERE c.lead_id = l.id) THEN 1 ELSE 0 END) AS has_contact,
            (CASE WHEN EXISTS (SELECT 1 FROM followups f WHERE f.lead_id = l.id) THEN 1 ELSE 0 END) AS has_followup,
            (CASE WHEN EXISTS (SELECT 1 FROM free_trials ft WHERE ft.lead_id = l.id) THEN 1 ELSE 0 END) AS has_free_trial,
            (CASE WHEN EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id) THEN 1 ELSE 0 END) AS has_so,
            (CASE WHEN EXISTS (SELECT 1 FROM clients cl WHERE cl.lead_id = l.id) THEN 1 ELSE 0 END) AS is_paid_client,
            (CASE WHEN l.is_disposed = 1 OR l.disposed_by IS NOT NULL OR l.disposed_at IS NOT NULL THEN 1 ELSE 0 END) AS is_disposed,

            (
                SELECT c.contact_uuid
                FROM contacts c
                WHERE c.lead_id = l.id
                  AND c.status = 1
                ORDER BY c.id DESC
                LIMIT 1
            ) AS contact_uuid,

            (
                SELECT f.followup_uuid
                FROM followups f
                WHERE f.lead_id = l.id
                ORDER BY f.id DESC
                LIMIT 1
            ) AS followup_uuid,

            (
                SELECT ft.free_trial_uuid
                FROM free_trials ft
                WHERE ft.lead_id = l.id
                ORDER BY ft.id DESC
                LIMIT 1
            ) AS free_trial_uuid,

            (
                SELECT so.sales_order_uuid
                FROM sales_orders so
                WHERE so.lead_id = l.id
                ORDER BY so.id DESC
                LIMIT 1
            ) AS sales_order_uuid,

            l.comment AS latest_comment,
            0 AS comment_count

        FROM leads l
        LEFT JOIN lead_sources ls
            ON (ls.id = l.lead_source OR ls.source_name = l.lead_source)
        LEFT JOIN users u
            ON (u.id = l.current_owner_user_id OR u.user_uuid = l.current_owner_user_uuid)
        WHERE (l.current_owner_user_id IN (SELECT id FROM users WHERE user_uuid IN ({placeholders})) OR l.current_owner_user_uuid IN ({placeholders}))
          AND NOT EXISTS (SELECT 1 FROM sales_orders so WHERE so.lead_id = l.id AND (so.order_status IS NULL OR LOWER(so.order_status) != 'rejected'))
        ORDER BY l.id DESC
        """,
        allowed_user_uuids + allowed_user_uuids,
    )

    rows = serialize_rows(cursor.fetchall())
    show_masked_number = int(user_settings.get("number_show_hide") or 0) == 1
    click_to_call = int(user_settings.get("click_to_call") or 0)

    integer_fields = (
        "call_status",
        "has_contact",
        "has_followup",
        "has_free_trial",
        "has_so",
        "is_paid_client",
        "is_suspended",
        "comment_count",
    )

    default_values = {
        "name": "NA",
        "email": "NA",
        "address": "NA",
        "lead_source": "",
        "lead_status": "No Status",
        "lifecycle_status": "Lead",
        "lead_working_state": "Fresh",
        "owner_name": "No Owner",
    }

    for row in rows:
        mobile_number = decrypt_mobile(row.get("mobile_number"))

        row["client_code"] = str(row.get("id") or "")
        row["timeline_url"] = f'/leads/timeline/{row.get("lead_uuid") or ""}'
        row["mobile_number"] = (
            mask_mobile_number(mobile_number)
            if show_masked_number
            else mobile_number or "NA"
        )
        row["click_to_call_enabled"] = click_to_call

        for field in integer_fields:
            row[field] = int(row.get(field) or 0)

        for field, default in default_values.items():
            row[field] = row.get(field) or default

        row["lead_activity"] = build_lead_activity_text(row)

        latest_comment = str(row.get("latest_comment") or "").strip()
        row["comment_preview"] = (
            f"{latest_comment[:20]}{'...' if len(latest_comment) > 20 else ''}"
            if latest_comment
            else ""
        )

    return rows


# Fetch source, status, and owner filter options.
def fetch_all_lead_filters(cursor, allowed_user_ids, logged_user_uuid):
    cursor.execute(
        """
        SELECT source_name
        FROM lead_sources
        WHERE status = 1
        ORDER BY source_name ASC
        """
    )
    lead_sources = [
        {"value": row["source_name"], "label": row["source_name"]}
        for row in cursor.fetchall()
    ]

    cursor.execute(
        """
        SELECT status_name
        FROM lead_statuses
        WHERE status = 1
        ORDER BY status_name ASC
        """
    )
    lead_statuses = [
        {"value": row["status_name"], "label": row["status_name"]}
        for row in cursor.fetchall()
    ]

    owner_options = []

    if allowed_user_ids:
        placeholders = ", ".join(["%s"] * len(allowed_user_ids))

        cursor.execute(
            f"""
            SELECT user_uuid, full_name
            FROM users
            WHERE id IN ({placeholders})
              AND status = 1
            ORDER BY
                CASE WHEN user_uuid = %s THEN 0 ELSE 1 END,
                full_name ASC
            """,
            allowed_user_ids + [logged_user_uuid],
        )

        owner_options = [
            {"value": row["user_uuid"], "label": row["full_name"]}
            for row in cursor.fetchall()
        ]

    return lead_sources, lead_statuses, owner_options


# Define All Leads grid columns.
def get_all_lead_columns():
    return [
        {
            "headerName": "Client Code",
            "field": "client_code",
            "minWidth": 100,
            "flex": 1,
            "renderer": "button",
            "buttonIcon": "mdi mdi-eye-outline",
            "buttonClass": "btn btn-sm btn-light",
            "buttonAction": "lead_timeline",
        },
        {
            "headerName": "Name",
            "field": "name",
            "minWidth": 160,
            "flex": 1,
        },
        {
            "headerName": "Mobile",
            "field": "mobile_number",
            "minWidth": 130,
            "flex": 1,
            "renderer": "button",
            "buttonIcon": "mdi mdi-phone-outline",
            "buttonClass": "btn btn-sm btn-outline-primary",
            "buttonClassField": "call_status",
            "buttonClassValue": 1,
            "buttonClassMatch": "btn btn-sm btn-success",
            "buttonAction": "lead_call",
            "buttonEnabledField": "click_to_call_enabled",
        },
        {
            "headerName": "Lead Status",
            "field": "lead_status",
            "minWidth": 160,
            "flex": 1,
        },
        {
            "headerName": "Source",
            "field": "lead_source",
            "minWidth": 150,
            "flex": 1,
        },
        {
            "headerName": "Owner",
            "field": "owner_name",
            "minWidth": 170,
            "flex": 1,
        },
        {
            "headerName": "Lead Activity",
            "field": "lead_activity",
            "minWidth": 190,
            "sortable": False,
            "filter": False,
        },
        {
            "headerName": "Comment",
            "field": "comment_preview",
            "minWidth": 160,
            "flex": 1,
            "sortable": False,
            "renderer": "leadCommentPreview",
        },
        {
            "headerName": "Manage",
            "field": "lead_uuid",
            "minWidth": 170,
            "sortable": False,
            "renderer": "button",
            "buttonText": "Manage Lead",
            "buttonIcon": "mdi mdi-account-edit-outline",
            "buttonClass": "btn btn-sm btn-primary",
            "buttonAction": "manage_lead",
        },
    ]


# Build the All Leads grid context.
def get_all_lead_grid_context(
    rows,
    lead_sources,
    lead_statuses,
    owner_options,
    source_limit_buttons,
    logged_user_uuid,
):
    return {
        "grid_id": "allLeadsGrid",
        "data": rows,
        "columns": get_all_lead_columns(),
        "filters": [
            {
                "name": "call_status",
                "label": "Call Status",
                "options": [
                    {"value": "0", "label": "Not Called"},
                    {"value": "1", "label": "Called"},
                ],
                "default": "0",
                "selected_value": "0",
            },
            {
                "name": "lead_status",
                "label": "Lead Status",
                "options": [
                    {"value": "No Status", "label": "No Status"},
                    *lead_statuses,
                ],
            },
            {
                "name": "lead_source",
                "label": "Lead Source",
                "options": lead_sources,
            },
            {
                "name": "lifecycle_status",
                "label": "Lifecycle Status",
                "options": [
                    {"value": "Lead", "label": "Lead"},
                    {"value": "Contact", "label": "Contact"},
                    {"value": "Free Trial", "label": "Free Trial"},
                    {"value": "SO", "label": "SO"},
                    {"value": "Paid Client", "label": "Paid Client"},
                ],
            },
            {
                "name": "current_owner_user_uuid",
                "label": "Owner",
                "options": owner_options,
                "default": logged_user_uuid,
                "selected_value": logged_user_uuid,
            },
        ],
        "date_filters": [
            {"name": "created_at", "label": "Created Date"},
            {"name": "updated_at", "label": "Modified Date"},
        ],
        "toolbar_buttons": source_limit_buttons,
        "toolbar_position": "top_with_search",
        "grid_wrapper_class": "settings-master-wrap",
        "grid_wrapper_attrs": {
            "data-master-type": "all_leads",
            "data-default-owner": logged_user_uuid,
        },
        "row_id_field": "lead_uuid",
        "action_id_field": "lead_uuid",
        "page_size": 10,
        "page_size_options": get_page_size_options(),
    }