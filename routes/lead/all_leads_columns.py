def get_lead_table_columns():
    """
    Return the All Leads Bootstrap table column configuration.
    """

    return [
        {
            "label": "Client Code",
            "field": "client_code",
            "sortable": True,
            "width": "130px",
        },
        {
            "label": "Name",
            "field": "name",
            "sortable": True,
            "width": "190px",
        },
        {
            "label": "Mobile",
            "field": "mobile_number",
            "type": "buttons",
            "sortable": True,
            "width": "150px",
            "buttons": [
                {
                    "action": "lead_call",
                    "labelField": "mobile_number",
                    "showLabel": True,
                    "showIcon": True,
                    "icon": "mdi mdi-phone-outline",
                    "title": "Call Lead",
                    "classField": "call_status",
                    "classMap": {
                        0: "btn btn-outline-primary btn-sm d-inline-flex align-items-center gap-1",
                        1: "btn btn-success btn-sm d-inline-flex align-items-center gap-1",
                    },
                    "class": "btn btn-outline-primary btn-sm d-inline-flex align-items-center gap-1",
                },
            ],
        },
        {
            "label": "Status",
            "field": "status_name",
            "sortable": True,
            "width": "150px",
        },
        {
            "label": "Activity",
            "field": "activity",
            "type": "buttons",
            "sortable": False,
            "width": "190px",
            "className": "text-nowrap",
            "buttons": [
                {
                    "action": "lead_followup",
                    "icon": "mdi mdi-calendar-clock-outline fs-5",
                    "showLabel": False,
                    "title": "Add Follow-up",
                    "modalId": "addFollowupModal",
                    "class": "btn btn-sm btn-soft-warning rounded-circle me-1",
                },
                {
                    "action": "lead_free_trial",
                    "icon": "mdi mdi-flask-outline fs-5",
                    "showLabel": False,
                    "title": "Add Free Trial",
                    "modalId": "addFreeTrialModal",
                    "class": "btn btn-sm btn-soft-info rounded-circle me-1",
                },
                {
                    "action": "lead_sales_order",
                    "icon": "mdi mdi-cash-multiple fs-5",
                    "showLabel": False,
                    "title": "Create Sales Order",
                    "modalId": "addSalesOrderModal",
                    "class": "btn btn-sm btn-soft-success rounded-circle",
                },
            ],
        },
        {
            "label": "Source",
            "field": "source_name",
            "sortable": True,
            "width": "150px",
        },
        {
            "label": "Owner",
            "field": "owner_name",
            "sortable": True,
            "width": "170px",
        },
        {
            "label": "Latest Comment",
            "field": "latest_comment",
            "sortable": True,
            "width": "280px",
        },
        {
            "label": "Created",
            "field": "created_at",
            "sortable": True,
            "width": "165px",
        },
        {
            "label": "Modified",
            "field": "updated_at",
            "sortable": True,
            "width": "165px",
        },
        {
            "label": "Assigned",
            "field": "assigned_at",
            "sortable": True,
            "width": "165px",
        },
        {
            "label": "Actions",
            "field": "actions",
            "type": "buttons",
            "sortable": False,
            "width": "130px",
            "className": "text-center text-nowrap",
            "buttons": [
                {
                    "action": "lead_timeline",
                    "title": "Lead Timeline",
                    "icon": "mdi mdi-timeline-clock-outline",
                    "showLabel": False,
                    "class": "btn btn-sm btn-light",
                },
                {
                    "action": "manage_lead",
                    "title": "Manage Lead",
                    "icon": "mdi mdi-account-edit-outline",
                    "showLabel": False,
                    "class": "btn btn-sm btn-light",
                },
            ],
        },
    ]