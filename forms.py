# forms.py
FORMS = [
    {
        "name": "Occurrence Report",
        "fields": [
            "incident_date",
            "incident_time",
            "location",
            "description",
            "reported_by_name",
            "reported_by_id",
            "supervisor_notified"
        ]
    },
    {
        "name": "Teddy Bear Tracking",
        "fields": [
            "date",
            "location",
            "recipient_type",      # Patient/Family/Bystander/Other
            "gender",               # Male/Female/Other/Prefer not to say
            "paramedic_name",
            "paramedic_id"
        ]
    },
    {
        "name": "Shift Log",
        "fields": [
            "shift_date",
            "start_time",
            "end_time",
            "location",
            "partner_name",
            "notes"
        ]
    },
    {
        "name": "Equipment Request",
        "fields": [
            "item_name",
            "quantity",
            "reason",
            "requested_by",
            "date"
        ]
    }
]