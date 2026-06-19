from pydoc import doc

import frappe
import json
import os
from frappe.utils import cint
from frappe.utils import today, now
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


def _documents_for_action(data, action):
    documents = data.get("documents") or []
    if action in {
        "so_only",
        "si_only",
        "quotation_only",
        "quotation_to_so",
        "quotation_so_si",
        "so_to_si",
        "po_only",
        "pi_only",
        "po_to_pi",
    } and documents:
        return documents
    return [data]


@frappe.whitelist()
def process_document(file_url):
    try:
        file_doc = frappe.get_doc("File", {"file_url": file_url})
        if not file_doc:
            return {"success": False, "error": "File not found in system", "stage": "validation"}

        site_path = frappe.get_site_path()
        file_path = os.path.join(site_path, "public", file_doc.file_url.lstrip("/"))

        if not os.path.exists(file_path):
            return {"success": False, "error": "File missing on disk", "stage": "validation"}

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > 10:
            return {"success": False, "error": f"File too large ({size_mb:.1f}MB). Max 10MB.", "stage": "validation"}

        ext = os.path.splitext(file_path)[1].lower()
        allowed = [".pdf", ".jpg", ".jpeg", ".png", ".webp", ".xlsx", ".xls", ".csv"]
        if ext not in allowed:
            return {"success": False, "error": f"File type {ext} not supported", "stage": "validation"}

        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp"}

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
        elif ext in [".xlsx", ".xls", ".csv"]:
            from ai_erpnext.email_processor import extract_from_excel
            extracted = extract_from_excel(file_path)
        else:
            extracted = extract_from_image(file_path, mime_map[ext])

        if not extracted.get("items") or len(extracted["items"]) == 0:
            return {
                "success": False,
                "error": "No line items found in document. Is this a quotation/order/invoice?",
                "stage": "extraction",
                "raw_extracted": extracted
            }

        return {
            "success": True,
            "stage": "extracted",
            "extracted_data": extracted,
            "suggested_doctype": extracted.get("document_type", "Quotation")
        }

    except json.JSONDecodeError:
        return {"success": False, "error": "AI could not parse the document. Try a clearer scan.", "stage": "parsing"}
    except Exception as e:
        frappe.log_error(
            title="AI Doc Error",
            message=frappe.get_traceback()
        )
        return {"success": False, "error": str(e), "stage": "unknown"}


@frappe.whitelist()
def create_from_extracted(extracted_data_json, action):
    try:
        data = json.loads(extracted_data_json) if isinstance(extracted_data_json, str) else extracted_data_json

        results = []
        documents = _documents_for_action(data, action)

        for document_data in documents:
            if action == "quotation_only":
                name = create_quotation(document_data)
                results.append({"doctype": "Quotation", "name": name})

            elif action == "so_only":
                name = create_sales_order(document_data)
                results.append({"doctype": "Sales Order", "name": name})

            elif action == "si_only":
                name = create_sales_invoice(document_data)
                results.append({"doctype": "Sales Invoice", "name": name})

            elif action == "quotation_to_so":
                q = create_quotation(document_data)
                so = make_so_from_quotation(q)
                results.append({"doctype": "Quotation", "name": q})
                results.append({"doctype": "Sales Order", "name": so})

            elif action == "quotation_so_si":
                q = create_quotation(document_data)
                so = make_so_from_quotation(q)
                si = make_si_from_so(so)
                results.append({"doctype": "Quotation", "name": q})
                results.append({"doctype": "Sales Order", "name": so})
                results.append({"doctype": "Sales Invoice", "name": si})

            elif action == "po_only":
                name = create_purchase_order(document_data)
                results.append({"doctype": "Purchase Order", "name": name})

            elif action == "pi_only":
                name = create_purchase_invoice(document_data)
                results.append({"doctype": "Purchase Invoice", "name": name})

            elif action == "so_to_si":
                so = create_sales_order(document_data)
                so_doc = frappe.get_doc("Sales Order", so)
                so_doc.submit()
                make_si_fn = frappe.get_attr(
                    "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice"
                )
                si_doc = make_si_fn(so)
                si_doc.insert(ignore_permissions=True)
                results.append({"doctype": "Sales Order", "name": so})
                results.append({"doctype": "Sales Invoice", "name": si_doc.name})

            elif action == "po_to_pi":
                po = create_purchase_order(document_data)
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
        frappe.log_error(
            title="AI create Doc Error",
            message=frappe.get_traceback()
        )
        return {"success": False, "error": str(e), "stage": "unknown"}


@frappe.whitelist()
def get_pending_emails():
    items = frappe.get_all(
        "AI Email Queue",
        filters={"status": "Pending"},
        fields=["name", "email_subject", "from_email",
                "received_on", "suggested_doctype", "source_type"],
        order_by="received_on desc",
        limit=50
    )
    return {"success": True, "items": items}


def _repair_email_queue_received_dates():
    """Align queue dates with the original email Date stored on Communication."""
    queue_items = frappe.get_all(
        "AI Email Queue",
        filters={"communication_link": ["is", "set"]},
        fields=["name", "communication_link", "received_on"],
    )

    repaired = 0
    for item in queue_items:
        communication_date = frappe.db.get_value(
            "Communication", item.communication_link, "communication_date"
        )
        if communication_date and str(item.received_on) != str(communication_date):
            frappe.db.set_value(
                "AI Email Queue",
                item.name,
                "received_on",
                communication_date,
                update_modified=False,
            )
            repaired += 1

    return repaired


def _backfill_ai_queue_from_communications(full_sync=0):
    """Process existing received Communications that did not trigger the AI hook."""
    limit = 1000 if cint(full_sync) else 100
    communications = frappe.get_all(
        "Communication",
        filters={
            "sent_or_received": "Received",
            "communication_type": "Communication",
        },
        fields=["name"],
        order_by="communication_date desc, creation desc",
        limit=limit,
    )

    processed = 0
    from ai_erpnext.email_processor import (
        process_committed_email,
        process_on_update,
    )

    for row in communications:
        try:
            comm = frappe.get_doc("Communication", row.name)
            if frappe.db.exists(
                "AI Email Queue", {"communication_link": row.name}
            ):
                process_on_update(comm, "ai_backfill")
            else:
                process_committed_email(row.name)
            processed += 1
        except Exception:
            frappe.log_error(
                title=f"AI Email Backfill Error: {row.name}",
                message=frappe.get_traceback(),
            )

    return processed


def _has_extracted_items(extracted_json):
    try:
        extracted = json.loads(extracted_json or "{}")
    except Exception:
        return False
    return bool(extracted.get("items"))


def _ai_email_queue_has_column(fieldname):
    try:
        return bool(
            frappe.db.sql(
                "show columns from `tabAI Email Queue` like %s",
                fieldname,
            )
        )
    except Exception:
        return False


def _dedupe_ai_email_queue():
    has_message_id = _ai_email_queue_has_column("message_id")
    has_email_uid = _ai_email_queue_has_column("email_uid")
    fields = [
        "name",
        "email_subject",
        "from_email",
        "received_on",
        "communication_link",
        "status",
        "extracted_json",
        "creation",
    ]
    if has_message_id:
        fields.append("message_id")
    if has_email_uid:
        fields.append("email_uid")

    rows = frappe.get_all(
        "AI Email Queue",
        fields=fields,
        order_by="creation asc",
        limit=5000,
    )

    groups = {}
    for row in rows:
        key = None
        message_id = row.get("message_id") if has_message_id else None
        email_uid = row.get("email_uid") if has_email_uid else None
        if message_id:
            key = ("message_id", message_id)
        elif email_uid:
            key = ("email_uid", email_uid)
        elif row.communication_link:
            key = ("communication_link", row.communication_link)
        else:
            key = (
                "fallback",
                row.email_subject,
                row.from_email,
                str(row.received_on),
            )
        groups.setdefault(key, []).append(row)

    removed = 0
    for group in groups.values():
        if len(group) < 2:
            continue

        def score(row):
            return (
                1 if row.status == "Processed" else 0,
                1 if _has_extracted_items(row.extracted_json) else 0,
            )

        keep = sorted(group, key=score, reverse=True)[0]
        for row in group:
            if row.name == keep.name:
                continue
            frappe.delete_doc(
                "AI Email Queue",
                row.name,
                ignore_permissions=True,
                force=True,
            )
            removed += 1

    return removed


@frappe.whitelist()
def sync_ai_emails(full_sync=0):
    """Start Gmail sync in background.

    Kept for older deployed/cached JS that still calls this endpoint directly.
    """
    frappe.has_permission("Email Account", "read", throw=True)
    return _enqueue_ai_email_sync(full_sync=full_sync)


def _sync_ai_emails_impl(full_sync=0):
    """Pull recent unread mail, optionally followed by full historical sync."""

    accounts = frappe.get_all(
        "Email Account",
        filters={"enable_incoming": 1, "awaiting_password": 0},
        pluck="name",
    )
    if not accounts:
        return {
            "success": False,
            "error": "No enabled incoming Email Account was found.",
        }

    before_count = frappe.db.count("AI Email Queue")
    synced_accounts = []
    errors = []

    for account_name in accounts:
        try:
            account_unseen = frappe.get_doc("Email Account", account_name)
            if cint(account_unseen.use_imap):
                account_unseen.email_sync_option = "UNSEEN"
                account_unseen.receive()

                if cint(full_sync):
                    account_all = frappe.get_doc("Email Account", account_name)
                    account_all.email_sync_option = "ALL"
                    account_all.receive()
            else:
                account_unseen.receive()

            synced_accounts.append(account_name)
        except Exception:
            errors.append(account_name)
            frappe.log_error(
                title=f"AI Email Sync Error: {account_name}",
                message=frappe.get_traceback(),
            )

    backfilled = _backfill_ai_queue_from_communications(full_sync=full_sync)
    repaired_dates = _repair_email_queue_received_dates()
    removed_duplicates = _dedupe_ai_email_queue()
    frappe.db.commit()

    return {
        "success": bool(synced_accounts),
        "synced_accounts": synced_accounts,
        "failed_accounts": errors,
        "new_emails": max(0, frappe.db.count("AI Email Queue") - before_count),
        "repaired_dates": repaired_dates,
        "backfilled": backfilled,
        "removed_duplicates": removed_duplicates,
        "full_sync": bool(cint(full_sync)),
    }


def scheduled_sync_ai_emails():
    """Scheduled task: pull only new/unread mail."""
    return _sync_ai_emails_impl(full_sync=0)


@frappe.whitelist()
def sync_ai_emails_background(full_sync=0):
    """Start Gmail sync in the background so the inbox page stays responsive."""
    frappe.has_permission("Email Account", "read", throw=True)
    return _enqueue_ai_email_sync(full_sync=full_sync)


def _enqueue_ai_email_sync(full_sync=0):
    frappe.enqueue(
        method="ai_erpnext.api._sync_ai_emails_impl",
        queue="long",
        timeout=1800,
        full_sync=cint(full_sync),
    )
    return {"success": True, "queued": True}


@frappe.whitelist()
def get_queue_item_detail(queue_name):
    doc = frappe.get_doc("AI Email Queue", queue_name)
    attachments = []

    email_body = doc.email_body or ""
    if doc.communication_link:
        attachments = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "Communication",
                "attached_to_name": doc.communication_link,
            },
            fields=["file_name", "file_url", "is_private"],
            order_by="creation asc",
        )

    if not email_body and doc.communication_link:
        try:
            comm = frappe.get_doc("Communication", doc.communication_link)
            email_body = comm.content or ""
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
            "email_body": email_body,
            "attachments": attachments,
        }
    }


@frappe.whitelist()
def process_queue_item(queue_name, action):
    try:
        doc = frappe.get_doc("AI Email Queue", queue_name)
        extracted = json.loads(doc.extracted_json)

        from ai_erpnext.api import create_from_extracted
        result = create_from_extracted(doc.extracted_json, action)

        frappe.db.set_value("AI Email Queue", queue_name, {
            "status": "Processed",
            "created_document": result.get("created", [{}])[0].get("name", "")
        })
        frappe.db.commit()

        return result
    except Exception as e:
        frappe.log_error(
            title="queue process error",
            message=frappe.get_traceback()
        )
        return {"success": False, "error": str(e), "stage": "unknown"}


@frappe.whitelist()
def ignore_queue_item(queue_name):
    frappe.db.set_value("AI Email Queue", queue_name, "status", "Ignored")
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def restore_queue_item(queue_name):
    frappe.db.set_value("AI Email Queue", queue_name, "status", "Pending")
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def delete_duplicate_ai_email_queue_items():
    """Remove duplicate AI queue rows for same sender, subject, and received time."""
    rows = frappe.get_all(
        "AI Email Queue",
        fields=["name", "email_subject", "from_email", "received_on", "creation"],
        order_by="received_on desc, creation asc",
    )
    seen = set()
    deleted = 0

    for row in rows:
        key = (
            row.email_subject or "",
            row.from_email or "",
            str(row.received_on or ""),
        )
        if key in seen:
            frappe.delete_doc("AI Email Queue", row.name, ignore_permissions=True)
            deleted += 1
        else:
            seen.add(key)

    frappe.db.commit()
    return {"success": True, "deleted": deleted}


@frappe.whitelist()
def get_email_queue(
    status="Pending",
    search="",
    page=1,
    page_length=20,
    sort_by="newest",
    business_only=0,
):
    page = int(page)
    page_length = int(page_length)

    filters = {}

    if cint(business_only):
        status = "Pending"

    if status:
        filters["status"] = status

    business_doctypes = [
        "Quotation",
        "Sales Order",
        "Sales Invoice",
        "Purchase Order",
        "Purchase Invoice",
        "Tax Invoice",
        "Proforma Invoice",
        "RFQ",
        "Request for Quotation",
    ]

    if cint(business_only):
        filters["suggested_doctype"] = [
            "in",
            business_doctypes,
        ]

    start = (page - 1) * page_length
    order_by = "received_on asc" if sort_by == "oldest" else "received_on desc"
    or_filters = [
        ["email_subject", "like", f"%{search}%"],
        ["from_email", "like", f"%{search}%"]
    ] if search else []

    total_rows = frappe.get_all(
        "AI Email Queue",
        filters=filters,
        or_filters=or_filters,
        fields=["count(name) as count"],
    )
    total_count = total_rows[0].count if total_rows else 0

    items = frappe.get_all(
        "AI Email Queue",
        filters=filters,
        or_filters=or_filters,
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
        order_by=order_by,
        limit_start=start,
        limit_page_length=page_length,
    )

    # Calculate a lightweight score only for the visible page.
    for item in items:

        score = 0

        subject = (item.get("email_subject") or "").lower()
        full_text = subject

        high_priority = {
            "urgent": 50,
            "immediate": 45,
            "payment overdue": 50,
            "legal notice": 60,
            "final reminder": 55,
            "invoice overdue": 50,
            "action required": 45,
            "approval required": 45,
            "pending approval": 40,
            "security alert": 60,
            "account suspended": 60,
            "failed payment": 50,
            "gst notice": 45,
            "tax notice": 45
        }

        medium_priority = {
            "invoice": 30,
            "purchase order": 30,
            "sales order": 30,
            "quotation": 25,
            "rfq": 25,
            "proforma": 25,
            "payment": 25,
            "remittance": 25,
            "contract": 30,
            "agreement": 30,
            "shipment": 20,
            "dispatch": 20,
            "delivery": 20,
            "vendor": 20,
            "customer": 20,
            "gst": 20,
            "hsn": 15,
            "compliance": 25,
            "audit": 30,
            "purchase": 20,
            "sales": 20
        }

        low_priority = {
            "newsletter": -20,
            "promotion": -25,
            "discount": -15,
            "offer": -15,
            "sale": -10,
            "marketing": -20,
            "unsubscribe": -30,
            "webinar": -15,
            "event invitation": -15,
            "free trial": -20
        }

        for keyword, points in high_priority.items():
            if keyword in full_text:
                score += points

        for keyword, points in medium_priority.items():
            if keyword in full_text:
                score += points

        for keyword, points in low_priority.items():
            if keyword in full_text:
                score += points

        if item.get("source_type") == "Attachment":
            score += 20

        if item.get("status") == "Pending":
            score += 15

        score = max(0, min(score, 100))

        item["importance_score"] = score

        if score >= 70:
            item["importance_label"] = "High"
        elif score >= 40:
            item["importance_label"] = "Medium"
        else:
            item["importance_label"] = "Low"

    if sort_by == "important":
        items = sorted(
            items,
            key=lambda x: x.get("importance_score", 0),
            reverse=True
        )

    counts = {
        "pending": frappe.db.count("AI Email Queue", {"status": "Pending"}),
        "documents": frappe.db.count("AI Email Queue", {
            "status": "Pending",
            "suggested_doctype": ["in", business_doctypes],
        }),
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


@frappe.whitelist()
def check_dependencies():
    results = {}

    try:
        import anthropic
        results["anthropic"] = anthropic.__version__
    except ImportError as e:
        results["anthropic"] = f"MISSING: {e}"

    api_key = os.environ.get("CLAUDE_API_KEY") or frappe.conf.get("claude_api_key")
    results["api_key_set"] = bool(api_key)
    results["api_key_source"] = (
        "env" if os.environ.get("CLAUDE_API_KEY")
        else ("conf" if frappe.conf.get("claude_api_key") else "MISSING")
    )

    try:
        import fitz
        results["pymupdf"] = fitz.version
    except ImportError as e:
        results["pymupdf"] = f"MISSING: {e}"

    return results


@frappe.whitelist()
def extract_queue_item(queue_name):
    try:
        doc = frappe.get_doc("AI Email Queue", queue_name)
        existing = json.loads(doc.extracted_json or "{}")

        if existing.get("items"):
            return {"success": True, "extracted": existing, "cached": True}

        from ai_erpnext.claude_helper import extract_from_email_text
        extracted = extract_from_email_text(doc.email_body or "")

        frappe.db.set_value("AI Email Queue", queue_name, {
            "extracted_json": json.dumps(extracted, indent=2),
            "suggested_doctype": extracted.get("document_type", "Unknown")
        })
        frappe.db.commit()

        return {"success": True, "extracted": extracted, "cached": False}
    except Exception as e:
        frappe.log_error(
            title="on demand extraction error",
            message=frappe.get_traceback()
        )
        return {"success": False, "error": str(e), "stage": "unknown"}


@frappe.whitelist()
def reextract_queue_item(queue_name):
    try:
        doc = frappe.get_doc("AI Email Queue", queue_name)

        extracted = None

        if doc.communication_link:
            try:
                attachments = frappe.get_all(
                    "File",
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
                    if ext not in ["pdf", "jpg", "jpeg", "png","webp", "xlsx", "xls", "csv"]:
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
                    mime_map = {
                        "jpg": "image/jpeg",
                        "jpeg": "image/jpeg",
                        "png": "image/png",
                        "webp": "image/webp"
                    }
                    # extracted = (
                    #     extract_from_pdf(file_path) if ext == "pdf"
                    #     else extract_from_image(file_path, mime_map.get(ext, "image/jpeg"))
                    # )
                    if ext == "pdf":
                        extracted = extract_from_pdf(file_path)

                    elif ext in ["xlsx", "xls", "csv"]:
                        from ai_erpnext.email_processor import extract_from_excel
                        extracted = extract_from_excel(file_path)

                    else:
                        extracted = extract_from_image(
                            file_path,
                            mime_map.get(ext, "image/jpeg")
                        )
                    
                    if extracted and extracted.get("items"):
                        break
            except Exception as e:
                frappe.log_error(
                    title="ReExtract Attachment Error",
                    message=str(e)[:5000]
                )

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
        frappe.log_error(
            title="Re-extract Error",
            message=frappe.get_traceback()
        )
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
    return {"success": True}


@frappe.whitelist()
def delete_all_email_queue_items(status=""):
    try:
        filters = {}
        if status:
            filters["status"] = status

        records = frappe.get_all(
            "AI Email Queue",
            filters=filters,
            fields=["name"]
        )

        count = 0
        for r in records:
            frappe.delete_doc(
                "AI Email Queue",
                r.name,
                ignore_permissions=True
            )
            count += 1

        frappe.db.commit()

        return {
            "success": True,
            "deleted": count
        }

    except Exception as e:
        frappe.log_error(
            title="Delete All Email Queue Error",
            message=str(e)[:5000]
        )
        return {
            "success": False,
            "error": str(e)
        }
