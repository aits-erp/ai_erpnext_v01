app_name = "ai_erpnext"
app_title = "ai_erpnext"
app_publisher = "aits"
app_description = "aits ai app"
app_email = "nikhil@aitsind.com"
app_license = "mit"


# Trigger on every new incoming email/communication
doc_events = {
    "Communication": {
        "after_insert": "ai_erpnext.email_processor.process_incoming_email",
        "on_update": "ai_erpnext.email_processor.process_on_update"
    }
}

doctype_js = {
    "Sales Order":      "public/js/form_ai_button.js",
    "Quotation":        "public/js/form_ai_button.js",
    "Sales Invoice":    "public/js/form_ai_button.js",
    "Purchase Order":   "public/js/form_ai_button.js",
    "Purchase Invoice": "public/js/form_ai_button.js",
}


