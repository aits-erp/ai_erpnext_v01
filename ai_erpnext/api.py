# api.py — top of file, replace your current imports with this
from pydoc import doc

import frappe
import json
import os
from frappe.utils import today, now  # ← THIS was missing
from ai_erpnext.claude_helper import extract_from_pdf, extract_from_image
from ai_erpnext.erpnext_mapper import (
    create_document,
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
# @frappe.whitelist()
# def create_from_extracted(extracted_data_json, action):
#     """
#     action = "quotation_only" | "so_only" | "si_only" | 
#              "quotation_to_so" | "quotation_so_si" | "po_only" | "pi_only"
#     """
#     try:
#         import json as _json
#         data = _json.loads(extracted_data_json) if isinstance(extracted_data_json, str) else extracted_data_json

#         results = []

#         if action == "quotation_only":
#             name = create_quotation(data)
#             results.append({"doctype": "Quotation", "name": name})

#         elif action == "so_only":
#             name = create_sales_order(data)
#             results.append({"doctype": "Sales Order", "name": name})

#         elif action == "si_only":
#             name = create_sales_invoice(data)
#             results.append({"doctype": "Sales Invoice", "name": name})

#         elif action == "quotation_to_so":
#             q = create_quotation(data)
#             so = make_so_from_quotation(q)
#             results.append({"doctype": "Quotation", "name": q})
#             results.append({"doctype": "Sales Order", "name": so})

#         elif action == "quotation_so_si":
#             q = create_quotation(data)
#             so = make_so_from_quotation(q)
#             si = make_si_from_so(so)
#             results.append({"doctype": "Quotation", "name": q})
#             results.append({"doctype": "Sales Order", "name": so})
#             results.append({"doctype": "Sales Invoice", "name": si})

#         elif action == "po_only":
#             name = create_purchase_order(data)
#             results.append({"doctype": "Purchase Order", "name": name})

#         elif action == "pi_only":
#             name = create_purchase_invoice(data)
#             results.append({"doctype": "Purchase Invoice", "name": name})

#         return {"success": True, "created": results}

#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), "AI Create Doc Error")
#         return {"success": False, "error": str(e)}

@frappe.whitelist()
def create_from_extracted(extracted_data_json, action):
    try:
        data = json.loads(extracted_data_json) if isinstance(extracted_data_json, str) else extracted_data_json

        # ── HSN Fallback: if any item missing HSN, try to find from notes/doc ──
        # Also find a common HSN from items that DO have it
        all_hsn = [i.get("hsn_code","") for i in data.get("items",[]) if i.get("hsn_code")]
        fallback_hsn = all_hsn[0] if all_hsn else ""

        for item in data.get("items", []):
            if not item.get("hsn_code") and fallback_hsn:
                item["hsn_code"] = fallback_hsn

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
        
        # elif action == "so_to_si":
        #     so = create_sales_order(data)
        #     # Submit SO first
        #     so_doc = frappe.get_doc("Sales Order", so)
        #     so_doc.submit()
        #     make_sales_invoice = frappe.get_attr(
        #         "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice"
        #     )
        #     si = make_sales_invoice(so)
        #     si_doc = frappe.get_doc("Sales Invoice", si.name if hasattr(si, 'name') else si)
        #     si_doc.insert(ignore_permissions=True)

        #     results.append({"doctype": "Sales Order", "name": so})
        #     results.append({"doctype": "Sales Invoice", "name": si_doc.name})

        # elif action == "po_to_pi":
        #     po = create_purchase_order(data)
        #     po_doc = frappe.get_doc("Purchase Order", po)
        #     po_doc.submit()
        #     make_purchase_invoice = frappe.get_attr(
        #         "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice"
        #     )
        #     pi = make_purchase_invoice(po)
        #     pi_doc = frappe.get_doc("Purchase Invoice", pi.name if hasattr(pi, 'name') else pi)
        #     pi_doc.insert(ignore_permissions=True)
        #     results.append({"doctype": "Purchase Order", "name": po})
        #     results.append({"doctype": "Purchase Invoice", "name": pi_doc.name})
        
        elif action == "so_to_si":
            so = create_sales_order(data)
            so_doc = frappe.get_doc("Sales Order", so)
            so_doc.submit()
            make_si_fn = frappe.get_attr(
                "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice"
            )
            si_doc = make_si_fn(so)          # returns unsaved doc
            si_doc.insert(ignore_permissions=True)   # save it
            results.append({"doctype": "Sales Order", "name": so})
            results.append({"doctype": "Sales Invoice", "name": si_doc.name})

        elif action == "po_to_pi":
            po = create_purchase_order(data)
            po_doc = frappe.get_doc("Purchase Order", po)
            po_doc.submit()
            make_pi_fn = frappe.get_attr(
                "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice"
            )
            pi_doc = make_pi_fn(po)
            pi_doc.insert(ignore_permissions=True)
            results.append({"doctype": "Purchase Order", "name": po})
            results.append({"doctype": "Purchase Invoice", "name": pi_doc.name})

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

# @frappe.whitelist()
# def get_queue_item_detail(queue_name):
#     doc = frappe.get_doc("AI Email Queue", queue_name)
#     return {
#         "success": True,
#         "data": {
#             "name": doc.name,
#             "email_subject": doc.email_subject,
#             "from_email": doc.from_email,
#             "received_on": str(doc.received_on),
#             "extracted": json.loads(doc.extracted_json or "{}"),
#             "suggested_doctype": doc.suggested_doctype,
#             "source_type": doc.source_type
#         }
#     }

@frappe.whitelist()
def get_queue_item_detail(queue_name):
    doc = frappe.get_doc("AI Email Queue", queue_name)
    
    # If email_body missing, fetch live from linked Communication
    email_body = doc.email_body or ""
    if not email_body and doc.communication_link:
        try:
            comm = frappe.get_doc("Communication", doc.communication_link)
            email_body = comm.content or ""
            # Save it so we don't fetch again
            frappe.db.set_value("AI Email Queue", queue_name, 
                "email_body", email_body[:5000])
        except Exception:
            email_body = "(Could not fetch email body)"

    return {
        "success": True,
        "data": {
            "name": doc.name,
            "email_subject": doc.email_subject,
            "from_email": doc.from_email,
            "received_on": str(doc.received_on),
            "extracted": json.loads(doc.extracted_json or "{}"),
            "suggested_doctype": doc.suggested_doctype,
            "source_type": doc.source_type,
            "status": doc.status,
            "created_document": doc.created_document or "",
            "email_body": email_body
        }
    }

@frappe.whitelist()
def process_queue_item(queue_name, action):
    """User reviewed and confirmed — now create the doc"""
    try:
        doc = frappe.get_doc("AI Email Queue", queue_name)
        extracted = json.loads(doc.extracted_json)

        # result = frappe.call(
        #     "ai_erpnext.api.create_from_extracted",
        #     extracted_data_json=doc.extracted_json,
        #     action=action
        # )
        from ai_erpnext.api import create_from_extracted
        result = create_from_extracted(doc.extracted_json, action)

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
def get_email_queue(status="Pending", search="", page=1, page_length=20):

    page = int(page)
    page_length = int(page_length)

    filters = {}

    if status:
        filters["status"] = status

    if search:
        filters["email_subject"] = ["like", f"%{search}%"]

    start = (page - 1) * page_length

    items = frappe.get_all(
        "AI Email Queue",
        filters=filters,
        fields=[
            "name",
            "email_subject",
            "from_email",
            "received_on",
            "suggested_doctype",
            "status",
            "created_document",
            "source_type"
        ],
        order_by="received_on desc",
        start=start,
        limit_page_length=page_length
    )

    total_count = frappe.db.count("AI Email Queue", filters)

    counts = {
        "pending": frappe.db.count("AI Email Queue", {"status": "Pending"}),
        "ignored": frappe.db.count("AI Email Queue", {"status": "Ignored"}),
        "processed_today": frappe.db.count("AI Email Queue", {
            "status": "Processed",
            "modified": [">=", today()]
        })
    }

    return {
        "success": True,
        "items": items,
        "counts": counts,
        "pagination": {
            "page": page,
            "page_length": page_length,
            "total": total_count,
            "total_pages": (total_count + page_length - 1) // page_length
        }
    }

    counts = {
        "pending": frappe.db.count("AI Email Queue", {"status": "Pending"}),
        "ignored": frappe.db.count("AI Email Queue", {"status": "Ignored"}),
        "processed_today": frappe.db.count("AI Email Queue", {
            "status": "Processed",
            "modified": [">=", today()]
        })
    }
    return {"success": True, "items": items, "counts": counts}

@frappe.whitelist()
def check_dependencies():
    results = {}
    
    # Check anthropic
    try:
        import anthropic
        results["anthropic"] = anthropic.__version__
    except ImportError as e:
        results["anthropic"] = f"MISSING: {e}"
    
    # Check API key
    api_key = os.environ.get("CLAUDE_API_KEY") or frappe.conf.get("claude_api_key")
    results["api_key_set"] = bool(api_key)
    results["api_key_source"] = "env" if os.environ.get("CLAUDE_API_KEY") else ("conf" if frappe.conf.get("claude_api_key") else "MISSING")
    
    # Check PyMuPDF
    try:
        import fitz
        results["pymupdf"] = fitz.version
    except ImportError as e:
        results["pymupdf"] = f"MISSING: {e}"
    
    return results

@frappe.whitelist()
def extract_queue_item(queue_name):
    """Called when user clicks Review on an unextracted email"""
    try:
        doc = frappe.get_doc("AI Email Queue", queue_name)
        existing = json.loads(doc.extracted_json or "{}")
        
        # Already extracted
        if existing.get("items"):
            return {"success": True, "extracted": existing, "cached": True}
        
        # Try extracting now
        from ai_erpnext.claude_helper import extract_from_email_text
        extracted = extract_from_email_text(doc.email_body or "")
        
        # Save result back
        frappe.db.set_value("AI Email Queue", queue_name, {
            "extracted_json": json.dumps(extracted, indent=2),
            "suggested_doctype": extracted.get("document_type", "Unknown")
        })
        frappe.db.commit()
        
        return {"success": True, "extracted": extracted, "cached": False}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "On-Demand Extract Error")
        return {"success": False, "error": str(e)}

# @frappe.whitelist()
# def reextract_queue_item(queue_name):
#     """Re-run Claude extraction on an already-queued item with updated prompt"""
#     try:
#         doc = frappe.get_doc("AI Email Queue", queue_name)
        
#         # Get email body
#         body = doc.email_body or ""
#         if not body and doc.communication_link:
#             comm = frappe.get_doc("Communication", doc.communication_link)
#             body = comm.content or ""

#         if not body:
#             return {"success": False, "error": "No email body to extract from"}

#         from ai_erpnext.claude_helper import extract_from_email_text
#         extracted = extract_from_email_text(body)

#         frappe.db.set_value("AI Email Queue", queue_name, {
#             "extracted_json": json.dumps(extracted, indent=2),
#             "suggested_doctype": extracted.get("document_type", "Quotation")
#         })
#         frappe.db.commit()

#         return {"success": True, "extracted": extracted}
#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), "Re-extract Error")
#         return {"success": False, "error": str(e)}

@frappe.whitelist()
def reextract_queue_item(queue_name):
    try:
        doc = frappe.get_doc("AI Email Queue", queue_name)

        extracted = None

        # Try attachments from linked communication first
        if doc.communication_link:
            try:
                comm = frappe.get_doc("Communication", doc.communication_link)
                attachments = frappe.get_all("File",
                    filters={
                        "attached_to_doctype": "Communication",
                        "attached_to_name": doc.communication_link
                    },
                    fields=["file_url", "file_name"]
                )
                for att in attachments:
                    if not att.file_name:
                        continue
                    ext = att.file_name.split(".")[-1].lower()
                    if ext not in ["pdf", "jpg", "jpeg", "png"]:
                        continue
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
                               "png": "image/png"}
                    extracted = extract_from_pdf(file_path) if ext == "pdf" \
                               else extract_from_image(file_path, mime_map.get(ext, "image/jpeg"))
                    if extracted and extracted.get("items"):
                        break
            except Exception as e:
                frappe.log_error(str(e)[:5000], "ReExtract Attachment Error")

        # Fallback to email body
        if not extracted or not extracted.get("items"):
            body = doc.email_body or ""
            if not body and doc.communication_link:
                try:
                    comm = frappe.get_doc("Communication", doc.communication_link)
                    body = comm.content or ""
                except Exception:
                    pass
            if body:
                from ai_erpnext.claude_helper import extract_from_email_text
                extracted = extract_from_email_text(body)

        if not extracted:
            return {"success": False, "error": "Nothing to extract from"}

        frappe.db.set_value("AI Email Queue", queue_name, {
            "extracted_json": json.dumps(extracted, indent=2),
            "suggested_doctype": extracted.get("document_type", "Quotation")
        })
        frappe.db.commit()
        return {"success": True, "extracted": extracted}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Re-extract Error")
        return {"success": False, "error": str(e)}
        
@frappe.whitelist()
def mark_queue_processed(queue_name, created_document=""):
    frappe.db.set_value("AI Email Queue", queue_name, {
        "status": "Processed",
        "created_document": created_document
    })
    frappe.db.commit()
    return {"success": True}
@frappe.whitelist()
def delete_email_queue_items(names):

    if isinstance(names, str):
        names = json.loads(names)

    for name in names:

        frappe.delete_doc(
            "AI Email Queue",
            name,
            force=True
        )

    frappe.db.commit()

    return {
        "success": True
    }