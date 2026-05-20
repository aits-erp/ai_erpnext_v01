import frappe
import json
import os



def process_incoming_email(doc, method):
    try:
        frappe.log_error(
            f"doc={doc.name} s_o_r={doc.sent_or_received} subject={doc.subject}",
            "AI Hook Debug"
        )

        if doc.sent_or_received != "Received":
            return
        if doc.communication_type != "Communication":
            return
        if frappe.db.exists("AI Email Queue", {"communication_link": doc.name}):
            return

        body_lower = (doc.content or "").lower()
        keywords = ["quotation","quote","order","invoice","quantity",
                   "amount","total","price","rate","item","product","service","bill"]
        keyword_hits = sum(1 for k in keywords if k in body_lower)

        attachments = frappe.get_all("File",
            filters={"attached_to_doctype":"Communication","attached_to_name":doc.name},
            fields=["file_url","file_name"]
        )
        has_attachment = any(
            att.file_name and att.file_name.split(".")[-1].lower()
            in ["pdf","jpg","jpeg","png"]
            for att in attachments
        )
        if keyword_hits < 2 and not has_attachment:
              extracted = {
               "items": [],
         "document_type": "General Email"
        }

        extracted = None
        extraction_error = None

        # Try attachment first
        for att in attachments:
            if not att.file_name:
                continue
            ext = att.file_name.split(".")[-1].lower()
            if ext not in ["pdf","jpg","jpeg","png","webp"]:
                continue
            try:
                file_path = frappe.get_site_path("public") + att.file_url
                file_path = os.path.join(
                    frappe.get_site_path(), "public", att.file_url.lstrip("/")
                )
                # Also try private path if public doesn't exist
                if not os.path.exists(file_path):
                    file_path = os.path.join(
                        frappe.get_site_path(), att.file_url.lstrip("/")
                    )
                if not os.path.exists(file_path):
                    continue
                from ai_erpnext.claude_helper import extract_from_pdf, extract_from_image
                mime_map = {"jpg":"image/jpeg","jpeg":"image/jpeg",
                           "png":"image/png","webp":"image/webp"}
                extracted = extract_from_pdf(file_path) if ext == "pdf" \
                           else extract_from_image(file_path, mime_map[ext])
                break
            except Exception as e:
                extraction_error = str(e)
                frappe.log_error(str(e)[:5000], "AI Attachment Extract Error")
                continue

        # Try email body if no attachment worked
        if not extracted and keyword_hits >= 2:
            try:
                from ai_erpnext.claude_helper import extract_from_email_text
                extracted = extract_from_email_text(doc.content)
            except Exception as e:
                extraction_error = str(e)
                # ← KEY FIX: short title, long message
                frappe.log_error(str(e)[:5000], "AI Email Body Error")

        # Always save to queue if email looks relevant
        # Even if extraction failed — user can re-extract manually
        try:
            queue_doc = frappe.get_doc({
                "doctype": "AI Email Queue",
                "email_subject": (doc.subject or "(No Subject)")[:140],
                "from_email": (doc.sender or "")[:140],
                "received_on": doc.creation,
                "source_type": "Email",
                "extracted_json": json.dumps(extracted or {}, indent=2),
                "suggested_doctype": (extracted or {}).get("document_type","Pending Review"),
                "status": "Pending",
                "communication_link": doc.name,
                "email_body": (doc.content or "")[:5000]
            })
            queue_doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(str(e)[:5000], "AI Queue Insert Error")

    except Exception as e:
        # Outermost catch — never let this crash email fetching
        frappe.log_error(str(e)[:5000], "AI Hook Outer Error")


# def process_on_update(doc, method):
#     """Catches attachments that weren't ready at insert time"""
#     # Only run if not already queued
#     if doc.sent_or_received != "Received":
#         return
#     if frappe.db.exists("AI Email Queue", {"communication_link": doc.name}):
#         return
#     # Now attachments exist — run full processing
#     process_incoming_email(doc, method)

def process_on_update(doc, method):
    if doc.sent_or_received != "Received":
        return

    queue = frappe.db.get_value(
        "AI Email Queue",
        {"communication_link": doc.name},
        ["name", "extracted_json"],
        as_dict=True
    )

    if not queue:
        # Not queued at all — run full processing
        process_incoming_email(doc, method)
        return

    # Already queued — only retry if no items extracted yet
    try:
        existing = json.loads(queue.extracted_json or "{}")
    except Exception:
        existing = {}

    if existing.get("items"):
        return  # Already has data — skip

    # Try attachments now (they may be saved by on_update time)
    attachments = frappe.get_all("File",
        filters={"attached_to_doctype": "Communication", "attached_to_name": doc.name},
        fields=["file_url", "file_name", "is_private"]
    )

    for att in attachments:
        if not att.file_name:
            continue
        ext = att.file_name.split(".")[-1].lower()
        if ext not in ["pdf", "jpg", "jpeg", "png", "webp"]:
            continue
        try:
            # Try both public and private paths
            file_path = os.path.join(
                frappe.get_site_path(), "public", att.file_url.lstrip("/")
            )
            if not os.path.exists(file_path):
                file_path = os.path.join(
                    frappe.get_site_path(), att.file_url.lstrip("/")
                )
            if not os.path.exists(file_path):
                continue

            from ai_erpnext.claude_helper import extract_from_pdf, extract_from_image
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                       "png": "image/png", "webp": "image/webp"}
            extracted = extract_from_pdf(file_path) if ext == "pdf" \
                       else extract_from_image(file_path, mime_map[ext])

            if extracted and extracted.get("items"):
                frappe.db.set_value("AI Email Queue", queue.name, {
                    "extracted_json": json.dumps(extracted, indent=2),
                    "suggested_doctype": extracted.get("document_type", "Quotation"),
                    "source_type": f"Attachment: {att.file_name}"
                })
                frappe.db.commit()
                frappe.log_error(
                    f"Updated {queue.name} with attachment data from on_update",
                    "AI Hook Debug"
                )
            break
        except Exception as e:
            frappe.log_error(str(e)[:5000], "AI On Update Attachment Error")
