import frappe
import json
import os
from ai_erpnext.erpnext_mapper import create_document
from ai_erpnext.erpnext_mapper import (
    create_quotation,
    create_sales_order,
    create_sales_invoice,
    make_so_from_quotation,
    make_si_from_so,
    create_purchase_order,
    create_purchase_invoice
)

# api.py - add this before calling claude
@frappe.whitelist()
def process_document(file_url):
    try:
        # ── STEP 1: Validate file exists ──
        file_doc = frappe.get_doc("File", {"file_url": file_url})
        if not file_doc:
            return {"success": False, "error": "File not found in system", "stage": "validation"}

        site_path = frappe.get_site_path()
        file_path = os.path.join(site_path, "public", file_doc.file_url.lstrip("/"))

        if not os.path.exists(file_path):
            return {"success": False, "error": "File missing on disk", "stage": "validation"}

        # ── STEP 2: Validate file size (skip files >10MB) ──
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > 10:
            return {"success": False, "error": f"File too large ({size_mb:.1f}MB). Max 10MB.", "stage": "validation"}

        # ── STEP 3: Validate extension ──
        ext = os.path.splitext(file_path)[1].lower()
        allowed = [".pdf", ".jpg", ".jpeg", ".png", ".webp"]
        if ext not in allowed:
            return {"success": False, "error": f"File type {ext} not supported", "stage": "validation"}

        # ── Only NOW call Claude ──
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp"}

        # Lazy import (only when needed)
        try:
            from ai_erpnext.claude_helper import extract_from_pdf, extract_from_image
        except ImportError:
            return {
                "success": False,
                "error": "AI feature not available. Required module 'anthropic' is not installed.",
                "stage": "dependency"
            }

        if ext == ".pdf":
            extracted = extract_from_pdf(file_path)
        else:
            extracted = extract_from_image(file_path, mime_map[ext])

        # ── STEP 4: Validate Claude returned usable data ──
        if not extracted.get("items") or len(extracted["items"]) == 0:
            return {
                "success": False,
                "error": "No line items found in document. Is this a quotation/order/invoice?",
                "stage": "extraction",
                "raw_extracted": extracted  # show what Claude DID find
            }

        # Return extracted data only — don't create doc yet
        # User will choose action next (saves tokens, no wasted doc creation)
        return {
            "success": True,
            "stage": "extracted",
            "extracted_data": extracted,
            "suggested_doctype": extracted.get("document_type", "Quotation")
        }

    except json.JSONDecodeError:
        return {"success": False, "error": "AI could not parse the document. Try a clearer scan.", "stage": "parsing"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "AI Doc Error")
        return {"success": False, "error": str(e), "stage": "unknown"}


# ── Separate endpoint: called AFTER user confirms ──
@frappe.whitelist()
def create_from_extracted(extracted_data_json, action):
    """
    action = "quotation_only" | "so_only" | "si_only" | 
             "quotation_to_so" | "quotation_so_si" | "po_only" | "pi_only"
    """
    try:
        import json as _json
        data = _json.loads(extracted_data_json) if isinstance(extracted_data_json, str) else extracted_data_json

        results = []

        if action == "quotation_only":
            name = create_quotation(data)
            results.append({"doctype": "Quotation", "name": name})

        elif action == "so_only":
            name = create_sales_order(data)
            results.append({"doctype": "Sales Order", "name": name})

        elif action == "si_only":
            name = create_sales_invoice(data)
            results.append({"doctype": "Sales Invoice", "name": name})

        elif action == "quotation_to_so":
            q = create_quotation(data)
            so = make_so_from_quotation(q)
            results.append({"doctype": "Quotation", "name": q})
            results.append({"doctype": "Sales Order", "name": so})

        elif action == "quotation_so_si":
            q = create_quotation(data)
            so = make_so_from_quotation(q)
            si = make_si_from_so(so)
            results.append({"doctype": "Quotation", "name": q})
            results.append({"doctype": "Sales Order", "name": so})
            results.append({"doctype": "Sales Invoice", "name": si})

        elif action == "po_only":
            name = create_purchase_order(data)
            results.append({"doctype": "Purchase Order", "name": name})

        elif action == "pi_only":
            name = create_purchase_invoice(data)
            results.append({"doctype": "Purchase Invoice", "name": name})

        return {"success": True, "created": results}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "AI Create Doc Error")
        return {"success": False, "error": str(e)}
      

@frappe.whitelist()
def get_pending_emails():
    """Get all unprocessed email queue items"""
    items = frappe.get_all("AI Email Queue",
        filters={"status": "Pending"},
        fields=["name", "email_subject", "from_email",
                "received_on", "suggested_doctype", "source_type"],
        order_by="received_on desc",
        limit=50
    )
    return {"success": True, "items": items}

@frappe.whitelist()
def get_queue_item_detail(queue_name):
    doc = frappe.get_doc("AI Email Queue", queue_name)
    return {
        "success": True,
        "data": {
            "name": doc.name,
            "email_subject": doc.email_subject,
            "from_email": doc.from_email,
            "received_on": str(doc.received_on),
            "extracted": json.loads(doc.extracted_json or "{}"),
            "suggested_doctype": doc.suggested_doctype,
            "source_type": doc.source_type
        }
    }

@frappe.whitelist()
def process_queue_item(queue_name, action):
    """User reviewed and confirmed — now create the doc"""
    try:
        doc = frappe.get_doc("AI Email Queue", queue_name)
        extracted = json.loads(doc.extracted_json)

        result = frappe.call(
            "ai_erpnext.api.create_from_extracted",
            extracted_data_json=doc.extracted_json,
            action=action
        )

        # Mark as processed
        frappe.db.set_value("AI Email Queue", queue_name, {
            "status": "Processed",
            "created_document": result.get("created", [{}])[0].get("name", "")
        })
        frappe.db.commit()

        return result
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Queue Process Error")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def ignore_queue_item(queue_name):
    frappe.db.set_value("AI Email Queue", queue_name, "status", "Ignored")
    frappe.db.commit()
    return {"success": True}

@frappe.whitelist()
def get_email_queue(status="Pending", search=""):
    filters = {}
    if status:
        filters["status"] = status
    if search:
        filters["email_subject"] = ["like", f"%{search}%"]

    items = frappe.get_all("AI Email Queue",
        filters=filters,
        fields=["name","email_subject","from_email","received_on",
                "suggested_doctype","status","created_document","source_type"],
        order_by="received_on desc",
        limit=100
    )

    from frappe.utils import today
    counts = {
        "pending": frappe.db.count("AI Email Queue", {"status": "Pending"}),
        "ignored": frappe.db.count("AI Email Queue", {"status": "Ignored"}),
        "processed_today": frappe.db.count("AI Email Queue", {
            "status": "Processed",
            "modified": [">=", today()]
        })
    }
    return {"success": True, "items": items, "counts": counts}