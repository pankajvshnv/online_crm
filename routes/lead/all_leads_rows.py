from datetime import (
    date,
    datetime,
)


def first_available_value(
    row,
    fields,
    default_value="",
):
    """
    Return the first non-empty value from the provided row fields.
    """

    for field in fields:
        value = row.get(field)

        if value not in {
            None,
            "",
        }:
            return value

    return default_value


def normalize_flag(value):
    """
    Convert a database flag into either zero or one.
    """

    try:
        return (
            1
            if int(value or 0) == 1
            else 0
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


def serialize_value(value):
    """
    Convert date values into JSON-safe strings.
    """

    if isinstance(
        value,
        datetime,
    ):
        return value.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    if isinstance(
        value,
        date,
    ):
        return value.strftime(
            "%Y-%m-%d"
        )

    return value


def serialize_row_values(row):
    """
    Convert every row value into a JSON-safe value.
    """

    return {
        key: serialize_value(value)
        for key, value in row.items()
    }


def prepare_lead_identity(
    prepared_row,
    row,
    user_settings=None,
    last_dialed_lead_uuid="",
):
    """
    Prepare the lead identity and contact fields.
    """

    prepared_row["lead_uuid"] = (
        first_available_value(
            row,
            [
                "lead_uuid",
                "uuid",
            ],
        )
    )

    prepared_row["client_code"] = (
        first_available_value(
            row,
            [
                "client_code",
                "lead_code",
                "id",
            ],
        )
    )

    prepared_row["name"] = (
        first_available_value(
            row,
            [
                "name",
                "full_name",
                "lead_name",
            ],
            "NA",
        )
    )

    from routes.settings_helpers import apply_mobile_and_last_dialed_context
    apply_mobile_and_last_dialed_context(prepared_row, user_settings, last_dialed_lead_uuid)


TONE_TO_BOOTSTRAP_MAP = {
    "green": "success",
    "blue": "primary",
    "red": "danger",
    "orange": "warning",
    "cyan": "info",
    "purple": "dark",
    "teal": "info",
    "rose": "danger",
    "slate": "secondary",
    "gray": "secondary",
    "grey": "secondary",
}


def get_bootstrap_color(tone):
    norm_tone = str(tone or "").strip().lower()
    return TONE_TO_BOOTSTRAP_MAP.get(
        norm_tone,
        norm_tone if norm_tone in {"success", "primary", "danger", "warning", "info", "secondary", "dark", "light"} else "secondary",
    )


def prepare_lead_status(
    prepared_row,
    row,
):
    """
    Prepare the lead status fields.
    """

    prepared_row["status_id"] = (
        first_available_value(
            row,
            [
                "status_id",
                "lead_status_id",
                "lead_status_uuid",
                "status_uuid",
            ],
        )
    )

    prepared_row["status_name"] = (
        first_available_value(
            row,
            [
                "status_name",
                "lead_status_name",
                "lead_status",
                "status",
            ],
            "No Status",
        )
    )

    raw_color = first_available_value(
        row,
        [
            "status_color",
            "status_tone",
            "lead_status_color",
            "color",
        ],
        "secondary",
    )

    prepared_row["status_color"] = get_bootstrap_color(raw_color)
    prepared_row["status_tone"] = raw_color


def prepare_lead_source(
    prepared_row,
    row,
):
    """
    Prepare the lead source fields.
    """

    prepared_row["source_id"] = (
        first_available_value(
            row,
            [
                "source_id",
                "lead_source_id",
                "source_uuid",
                "lead_source_uuid",
            ],
        )
    )

    prepared_row["source_name"] = (
        first_available_value(
            row,
            [
                "source_name",
                "lead_source_name",
                "lead_source",
                "source",
            ],
            "No Source",
        )
    )


def prepare_lead_owner(
    prepared_row,
    row,
):
    """
    Prepare the lead owner fields.
    """

    prepared_row["owner_uuid"] = (
        first_available_value(
            row,
            [
                "owner_uuid",
                "assigned_to_uuid",
                "user_uuid",
            ],
        )
    )

    prepared_row["owner_name"] = (
        first_available_value(
            row,
            [
                "owner_name",
                "assigned_user_name",
                "assigned_to_name",
            ],
            "Unassigned",
        )
    )


def prepare_lead_activity(
    prepared_row,
    row,
):
    """
    Prepare activity flags used to show or hide table buttons.
    """

    prepared_row["has_contact"] = (
        normalize_flag(
            row.get("has_contact")
        )
    )

    prepared_row["has_followup"] = (
        normalize_flag(
            row.get("has_followup")
        )
    )

    prepared_row["has_free_trial"] = (
        normalize_flag(
            row.get("has_free_trial")
        )
    )

    prepared_row["has_so"] = (
        normalize_flag(
            row.get("has_so")
        )
    )

    prepared_row["contact_count"] = (
        first_available_value(
            row,
            [
                "contact_count",
            ],
            0,
        )
    )

    prepared_row["followup_count"] = (
        first_available_value(
            row,
            [
                "followup_count",
            ],
            0,
        )
    )

    prepared_row["free_trial_count"] = (
        first_available_value(
            row,
            [
                "free_trial_count",
            ],
            0,
        )
    )

    prepared_row["so_count"] = (
        first_available_value(
            row,
            [
                "so_count",
            ],
            0,
        )
    )


def prepare_lead_comment(
    prepared_row,
    row,
):
    """
    Prepare the latest lead comment fields.
    """

    raw_comment = first_available_value(
        row,
        [
            "comment",
            "latest_comment",
            "last_comment",
        ],
        "No comment",
    )
    prepared_row["latest_comment"] = raw_comment if raw_comment and raw_comment != "" else "No comment"
    prepared_row["comment"] = prepared_row["latest_comment"]

    prepared_row["latest_comment_at"] = (
        serialize_value(
            first_available_value(
                row,
                [
                    "latest_comment_at",
                    "last_comment_at",
                    "comment_created_at",
                ],
            )
        )
    )

    prepared_row["latest_comment_by"] = (
        first_available_value(
            row,
            [
                "latest_comment_by",
                "comment_user_name",
                "commented_by_name",
            ],
        )
    )


def prepare_lead_dates(
    prepared_row,
    row,
):
    """
    Prepare the created, modified and assigned dates.
    """

    prepared_row["created_at"] = (
        serialize_value(
            first_available_value(
                row,
                [
                    "created_at",
                    "lead_created_at",
                    "created_date",
                ],
            )
        )
    )

    prepared_row["updated_at"] = (
        serialize_value(
            first_available_value(
                row,
                [
                    "updated_at",
                    "modified_at",
                    "last_modified_at",
                    "lead_updated_at",
                ],
            )
        )
    )

    prepared_row["assigned_at"] = (
        serialize_value(
            first_available_value(
                row,
                [
                    "assigned_at",
                    "assignment_date",
                    "lead_assigned_at",
                ],
            )
        )
    )


def prepare_lead_actions(
    prepared_row,
    row,
):
    """
    Prepare values required by lead action buttons.
    """

    prepared_row["timeline_url"] = (
        first_available_value(
            row,
            [
                "timeline_url",
            ],
        )
    )

    prepared_row["call_status"] = (
        normalize_flag(
            row.get("call_status")
        )
    )


def prepare_lead_row(row, user_settings=None, last_dialed_lead_uuid=""):
    """
    Prepare one database lead row for the Bootstrap table.
    """

    prepared_row = (
        serialize_row_values(
            dict(row)
        )
    )

    prepare_lead_identity(
        prepared_row,
        row,
        user_settings,
        last_dialed_lead_uuid,
    )

    prepare_lead_status(
        prepared_row,
        row,
    )

    prepare_lead_source(
        prepared_row,
        row,
    )

    prepare_lead_owner(
        prepared_row,
        row,
    )

    prepare_lead_activity(
        prepared_row,
        row,
    )

    prepare_lead_comment(
        prepared_row,
        row,
    )

    prepare_lead_dates(
        prepared_row,
        row,
    )

    prepare_lead_actions(
        prepared_row,
        row,
    )

    return prepared_row