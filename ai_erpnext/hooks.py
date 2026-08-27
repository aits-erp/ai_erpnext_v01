app_name = "ai_erpnext"
app_title = "ai_erpnext"
app_publisher = "aits"
app_description = "aits ai app"
app_email = "nikhil@aitsind.com"
app_license = "mit"


# Trigger on every new incoming email/communication
# doc_events = {
#     "Communication": {
#         "after_insert": "ai_erpnext.email_processor.process_incoming_email",
#         "on_update": "ai_erpnext.email_processor.process_on_update"
#     }
# }

doc_events = {
    "Communication": {
        "after_insert": "ai_erpnext.email_processor.enqueue_incoming_email",
        "on_update": "ai_erpnext.email_processor.process_on_update"
    },
    "File": {
        "after_insert": "ai_erpnext.email_processor.process_file_attachment"
    }
}

scheduled_events = {
    "cron": {
        "*/5 * * * *": [
            "ai_erpnext.api.scheduled_sync_ai_emails"
        ]
    }
}


doctype_js = {
    "Api Controller": "public/js/api_controller.js",
}
