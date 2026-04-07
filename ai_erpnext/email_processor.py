import frappe
import json
import os

def process_incoming_email(doc, method):
    """Fires on every new Communication. Checks if it's a business doc."""
    
    # Only process received emails, not sent ones
    if doc.sent_or_received != "Received":
        return
    if doc.communication_type != "Communication":
        return

    # Skip if already processed
    if frappe.db.exists("AI Email Queue", {"communication_link": doc.name}):
        return

    extracted = None
    source_hint = "Email Text"

    # ── PRIORITY 1: Check for PDF/Image attachments ──
    attachments = frappe.get_all("File",
        filters={
            "attached_to_doctype": "Communication",
            "attached_to_name": doc.name
        },
        fields=["file_url", "file_name"]
    )

    for att in attachments:
        if not att.file_name:
            continue
        ext = att.file_name.split(".")[-1].lower()
        if ext not in ["pdf", "jpg", "jpeg", "png", "webp"]:
            continue

        try:
            file_path = frappe.get_site_path("public") + att.file_url
            if not os.path.exists(file_path):
                continue

            from ai_erpnext.claude_helper import extract_from_pdf, extract_from_image
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                       "png": "image/png", "webp": "image/webp"}

            if ext == "pdf":
                extracted = extract_from_pdf(file_path)
            else:
                extracted = extract_from_image(file_path, mime_map[ext])

            source_hint = f"Attachment: {att.file_name}"
            break  # Stop after first valid attachment

        except Exception as e:
            frappe.log_error(str(e), "AI Email Attachment Error")
            continue

    # ── PRIORITY 2: Try email body text if no attachment worked ──
    if not extracted and doc.content:
        # Quick pre-check: does email body look like an order/quote?
        body_lower = (doc.content or "").lower()
        keywords = ["quotation", "quote", "order", "invoice",
                   "quantity", "amount", "total", "price", "rate",
                   "item", "product", "service", "bill"]
        
        keyword_hits = sum(1 for k in keywords if k in body_lower)
        
        if keyword_hits >= 3:  # Only call Claude if looks relevant
            try:
                from ai_erpnext.claude_helper import extract_from_email_text
                extracted = extract_from_email_text(doc.content)
                source_hint = "Email Body"
            except Exception as e:
                frappe.log_error(str(e), "AI Email Body Error")

    # ── Save to queue if we got something useful ──
    if extracted and extracted.get("items") and len(extracted["items"]) > 0:
        try:
            queue_doc = frappe.get_doc({
                "doctype": "AI Email Queue",
                "email_subject": doc.subject or "(No Subject)",
                "from_email": doc.sender or "",
                "received_on": doc.creation,
                "source_type": "Email",
                "extracted_json": json.dumps(extracted, indent=2),
                "suggested_doctype": extracted.get("document_type", "Quotation"),
                "status": "Pending",
                "communication_link": doc.name
            })
            queue_doc.insert(ignore_permissions=True)
            frappe.db.commit()

            # Optional: notify System Manager
            frappe.publish_realtime(
                event="ai_email_received",
                message={
                    "subject": doc.subject,
                    "from": doc.sender,
                    "suggested": extracted.get("document_type")
                },
                user=frappe.session.user
            )
        except Exception as e:
            frappe.log_error(str(e), "AI Queue Insert Error")