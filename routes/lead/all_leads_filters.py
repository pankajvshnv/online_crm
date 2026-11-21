
from routes.lead.all_leads_helpers import (
    fetch_all_lead_filters,
    fetch_user_tree,
)


def normalize_value(value):
    if value is None:
        return ""

    return str(value).strip().lower()


def normalize_filter_option(
    option,
    value_fields,
    label_fields,
):
    if not isinstance(option, dict):
        value = str(option)

        return {
            "value": value,
            "label": value,
        }

    value = ""

    for field in value_fields:
        field_value = option.get(field)

        if field_value not in {
            None,
            "",
        }:
            value = str(field_value)
            break

    label = ""

    for field in label_fields:
        field_value = option.get(field)

        if field_value not in {
            None,
            "",
        }:
            label = str(field_value)
            break

    if not label:
        label = value

    return {
        "value": value,
        "label": label,
    }


def normalize_filter_options(
    options,
    value_fields,
    label_fields,
):
    normalized_options = []
    used_values = set()

    for option in options or []:
        normalized_option = normalize_filter_option(
            option,
            value_fields,
            label_fields,
        )

        option_value = normalized_option["value"]

        if not option_value:
            continue

        if option_value in used_values:
            continue

        used_values.add(option_value)

        normalized_options.append(
            normalized_option
        )

    return normalized_options


def get_lead_source_options(
    lead_sources,
):
    return normalize_filter_options(
        lead_sources,
        value_fields=[
            "value",
            "source_uuid",
            "lead_source_uuid",
            "source_id",
            "id",
            "source_name",
            "name",
        ],
        label_fields=[
            "label",
            "source_name",
            "name",
        ],
    )


def get_lead_status_options(
    lead_statuses,
):
    options = [
        {
            "value": "no_status",
            "label": "No Status",
        }
    ]
    options.extend(
        normalize_filter_options(
            lead_statuses,
            value_fields=[
                "value",
                "status_uuid",
                "lead_status_uuid",
                "status_id",
                "id",
                "status_name",
                "name",
            ],
            label_fields=[
                "label",
                "status_name",
                "name",
            ],
        )
    )
    return options


def get_lead_owner_options(
    owner_options,
):
    return normalize_filter_options(
        owner_options,
        value_fields=[
            "value",
            "user_uuid",
            "owner_uuid",
            "user_id",
            "id",
            "full_name",
            "owner_name",
            "name",
        ],
        label_fields=[
            "label",
            "full_name",
            "owner_name",
            "name",
        ],
    )


def build_lead_filters(
    lead_sources,
    lead_statuses,
    owner_options,
):
    return [
        {
            "name": "source",
            "label": "Source",
            "placeholder": "All Sources",
            "options": get_lead_source_options(
                lead_sources
            ),
        },
        {
            "name": "status",
            "label": "Status",
            "placeholder": "All Statuses",
            "options": get_lead_status_options(
                lead_statuses
            ),
        },
        {
            "name": "owner",
            "label": "Owner",
            "placeholder": "All Owners",
            "options": get_lead_owner_options(
                owner_options
            ),
        },
    ]


def fetch_lead_filter_context(
    cursor,
    logged_user_uuid,
):
    (
        allowed_user_ids,
        allowed_user_uuids,
    ) = fetch_user_tree(
        cursor,
        logged_user_uuid,
    )

    (
        lead_sources,
        lead_statuses,
        owner_options,
    ) = fetch_all_lead_filters(
        cursor,
        allowed_user_ids,
        logged_user_uuid,
    )

    return {
        "filters": build_lead_filters(
            lead_sources,
            lead_statuses,
            owner_options,
        ),
        "allowed_user_ids": allowed_user_ids,
        "allowed_user_uuids": allowed_user_uuids,
    }


def get_filter_request_values(
    request_args,
    logged_user_uuid="",
):
    call_status_param = request_args.get("call_status")
    status_param = request_args.get("status")
    owner_param = request_args.get("owner")
    disposed_param = request_args.get("disposed")

    if owner_param in (None, ""):
        owner_param = logged_user_uuid or "all"
    elif str(owner_param).lower() in ("all", "all_owners"):
        owner_param = "all"

    if disposed_param is None:
        disposed_param = "0"

    return {
        "search": str(
            request_args.get("search")
            or ""
        ).strip(),
        "source": str(
            request_args.get("source")
            or ""
        ).strip(),
        "status": (
            str(status_param).strip()
            if status_param not in (None, "")
            else "all"
        ),
        "owner": str(
            owner_param
            or ""
        ).strip(),
        "call_status": (
            str(call_status_param).strip()
            if call_status_param is not None
            else ""
        ),
        "disposed": str(
            disposed_param
        ).strip(),
        "created_from": str(request_args.get("created_from") or request_args.get("created_date_from") or "").strip(),
        "created_to": str(request_args.get("created_to") or request_args.get("created_date_to") or "").strip(),
        "modified_from": str(request_args.get("modified_from") or request_args.get("modified_date_from") or "").strip(),
        "modified_to": str(request_args.get("modified_to") or request_args.get("modified_date_to") or "").strip(),
        "assigned_from": str(request_args.get("assigned_from") or request_args.get("assigned_date_from") or "").strip(),
        "assigned_to": str(request_args.get("assigned_to") or request_args.get("assigned_date_to") or "").strip(),
    }


def value_matches_filter(
    row,
    filter_value,
    fields,
):
    normalized_filter = normalize_value(
        filter_value
    )

    if not normalized_filter:
        return True

    for field in fields:
        row_value = normalize_value(
            row.get(field)
        )

        if row_value == normalized_filter:
            return True

    return False


def row_matches_search(
    row,
    search_value,
):
    normalized_search = normalize_value(
        search_value
    )

    if not normalized_search:
        return True

    searchable_fields = [
        "client_code",
        "lead_code",
        "name",
        "full_name",
        "lead_name",
        "mobile_number",
        "email",
        "source_name",
        "lead_source",
        "status_name",
        "lead_status",
        "owner_name",
        "assigned_user_name",
        "assigned_to_name",
        "city",
        "state",
    ]

    searchable_text = " ".join(
        normalize_value(
            row.get(field)
        )
        for field in searchable_fields
    )

    return normalized_search in searchable_text


def apply_lead_filters(
    rows,
    filter_values,
):
    filtered_rows = []

    for row in rows:
        call_status = filter_values.get("call_status")
        if call_status != "" and call_status is not None:
            row_call_status = str(row.get("call_status", 0))
            if row_call_status != str(call_status):
                continue

        source_filter = filter_values.get("source")
        if source_filter not in ("all", "ALL", "All", "", None):
            if not value_matches_filter(
                row,
                source_filter,
                [
                    "source_uuid",
                    "lead_source_uuid",
                    "source_id",
                    "source_name",
                    "lead_source",
                ],
            ):
                continue

        status_filter = filter_values.get("status")
        if status_filter in ("all", "ALL", "All", "", None):
            pass
        elif status_filter == "no_status":
            row_status = row.get("status_name") or row.get("lead_status") or ""
            if row_status not in ("", "No Status", None):
                continue
        elif status_filter:
            if not value_matches_filter(
                row,
                status_filter,
                [
                    "status_uuid",
                    "lead_status_uuid",
                    "status_id",
                    "status_name",
                    "lead_status",
                    "status",
                ],
            ):
                continue

        owner_filter = filter_values.get("owner")
        if owner_filter in ("all", "ALL", "All", "", None):
            pass
        elif owner_filter in ("unassigned", "0", "not_assigned", "un_assigned"):
            row_owner = row.get("current_owner_user_id")
            if row_owner not in (None, 0, "", "None"):
                continue
        elif owner_filter:
            if not value_matches_filter(
                row,
                owner_filter,
                [
                    "owner_uuid",
                    "current_owner_user_id",
                    "assigned_to_uuid",
                    "user_uuid",
                    "owner_id",
                    "owner_name",
                    "assigned_user_name",
                    "assigned_to_name",
                ],
            ):
                continue

        disposed_filter = filter_values.get("disposed", "0")
        if disposed_filter in ("0", "1"):
            row_is_disposed = int(row.get("is_disposed") or 0)
            if row_is_disposed != int(disposed_filter):
                continue

        # Created Date Filter (leads.created_at)
        created_from = filter_values.get("created_from")
        created_to = filter_values.get("created_to")
        if created_from or created_to:
            row_created = str(row.get("created_at") or "")[:10]
            if row_created:
                if created_from and row_created < created_from:
                    continue
                if created_to and row_created > created_to:
                    continue

        # Modification Date Filter (leads.updated_at)
        modified_from = filter_values.get("modified_from")
        modified_to = filter_values.get("modified_to")
        if modified_from or modified_to:
            row_modified = str(row.get("updated_at") or "")[:10]
            if row_modified:
                if modified_from and row_modified < modified_from:
                    continue
                if modified_to and row_modified > modified_to:
                    continue

        # Assigned Date Filter (leads.assigned_at)
        assigned_from = filter_values.get("assigned_from")
        assigned_to = filter_values.get("assigned_to")
        if assigned_from or assigned_to:
            row_assigned = str(row.get("assigned_at") or "")[:10]
            if row_assigned:
                if assigned_from and row_assigned < assigned_from:
                    continue
                if assigned_to and row_assigned > assigned_to:
                    continue

        if not row_matches_search(
            row,
            filter_values.get("search"),
        ):
            continue

        filtered_rows.append(row)

    return filtered_rows

