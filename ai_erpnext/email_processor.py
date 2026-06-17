# import frappe
# import json
# import os
# import re


# def normalize_header(value):
#     return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


# def header_matches(header, alias):
#     return (
#         header == alias
#         or header.startswith(alias + "_")
#         or header.endswith("_" + alias)
#     )


# def find_header_index(headers, *aliases):
#     for alias in aliases:
#         for index, header in enumerate(headers):
#             if header_matches(header, alias):
#                 return index
#     return None


# def to_number(value):
#     if value in (None, ""):
#         return 0

#     cleaned = re.sub(r"[^0-9.\-]", "", str(value))
#     try:
#         return float(cleaned) if cleaned else 0
#     except (TypeError, ValueError):
#         return 0


# def extract_items_from_rows(rows):
#     """Find an item-table header in CSV/XLSX rows and parse its data rows."""
#     item_aliases = (
#         "item_name", "item_code", "sku", "item", "product", "description"
#     )
#     qty_aliases = (
#         "qty", "quantity", "stock_qty", "order_qty",
#         "order_quantity", "total_order_ctns_pcs", "order_ctns_pcs",
#     )
#     rate_aliases = ("rate", "price", "unit_price")
#     amount_aliases = ("amount", "total", "base_amount", "net_amount")

#     header_index = None
#     headers = []

#     for index, row in enumerate(rows):
#         normalized = [normalize_header(cell) for cell in row]
#         has_item = find_header_index(normalized, *item_aliases) is not None
#         has_value = any(
#             find_header_index(normalized, *aliases) is not None
#             for aliases in (qty_aliases, rate_aliases, amount_aliases)
#         )
#         if has_item and has_value:
#             header_index = index
#             headers = normalized
#             break

#     if header_index is None:
#         return []

#     item_name_index = find_header_index(
#         headers, "item_name", "item", "product", "description", "item_code"
#     )
#     item_code_index = find_header_index(headers, "item_code", "code", "sku")
#     description_index = find_header_index(headers, "description")
#     qty_index = find_header_index(headers, *qty_aliases)
#     order_qty_index = find_header_index(
#         headers, "order_qty", "order_quantity",
#         "total_order_ctns_pcs", "order_ctns_pcs",
#     )
#     rate_index = find_header_index(headers, *rate_aliases)
#     amount_index = find_header_index(headers, *amount_aliases)
#     uom_index = find_header_index(headers, "uom", "stock_uom", "unit")
#     hsn_index = find_header_index(headers, "hsn_code", "hsn", "gst_hsn_code")

#     def cell(row, index, default=""):
#         return row[index] if index is not None and index < len(row) else default

#     items = []
#     for row in rows[header_index + 1:]:
#         item_name = str(cell(row, item_name_index)).strip()
#         item_code = str(cell(row, item_code_index)).strip()

#         # ERPNext export templates sometimes include a second field-name row.
#         if normalize_header(item_name) in item_aliases:
#             continue
#         if not item_name and not item_code:
#             continue

#         qty = to_number(cell(row, qty_index))
#         if order_qty_index is not None and qty <= 0:
#             continue
#         rate = to_number(cell(row, rate_index))
#         amount = to_number(cell(row, amount_index)) or qty * rate

#         items.append({
#             "item_name": item_name or item_code,
#             "item_code": item_code,
#             "description": str(
#                 cell(row, description_index, item_name or item_code)
#             ).strip(),
#             "qty": qty or 1,
#             "uom": str(cell(row, uom_index, "Nos")).strip() or "Nos",
#             "rate": rate,
#             "amount": amount,
#             "hsn_code": str(cell(row, hsn_index)).strip(),
#             "tax_rate": 0,
#         })

#     return items


# def extract_metadata_from_rows(rows):
#     """Extract parent Sales/Purchase document fields from exported rows."""
#     aliases = {
#         "customer_name": ("customer", "customer_name", "party_name"),
#         "supplier_name": ("supplier", "supplier_name"),
#         "document_date": (
#             "transaction_date", "posting_date", "date", "order_date"
#         ),
#         "due_date": ("delivery_date", "due_date", "schedule_date"),
#         "document_number": ("id", "name", "sales_order", "purchase_order"),
#         "currency": ("currency",),
#     }

#     for header_position, header_row in enumerate(rows):
#         headers = [normalize_header(cell) for cell in header_row]
#         indexes = {
#             field: find_header_index(headers, *field_aliases)
#             for field, field_aliases in aliases.items()
#         }
#         if indexes["customer_name"] is None and indexes["supplier_name"] is None:
#             continue

#         for data_row in rows[header_position + 1:]:
#             metadata = {}
#             for field, index in indexes.items():
#                 if index is not None and index < len(data_row):
#                     value = str(data_row[index]).strip()
#                     if value and normalize_header(value) not in aliases[field]:
#                         metadata[field] = value

#             if metadata.get("customer_name") or metadata.get("supplier_name"):
#                 return metadata

#     return {}


# def build_spreadsheet_result(file_path, items, metadata=None):
#     metadata = metadata or {}
#     file_name = os.path.basename(file_path).lower()
#     document_type = (
#         "Sales Invoice" if "sales invoice" in file_name
#         else "Purchase Invoice" if "purchase invoice" in file_name
#         else "Purchase Order" if "purchase order" in file_name
#         else "Sales Order"
#     )
#     grand_total = sum(item["amount"] for item in items)

#     return {
#         "document_type": document_type,
#         "customer_name": metadata.get("customer_name", ""),
#         "customer": metadata.get("customer_name", ""),
#         "supplier_name": metadata.get("supplier_name", ""),
#         "supplier": metadata.get("supplier_name", ""),
#         "document_date": metadata.get("document_date", ""),
#         "document_number": metadata.get("document_number", ""),
#         "due_date": metadata.get("due_date", ""),
#         "items": items,
#         "taxes": [],
#         "total_before_tax": grand_total,
#         "total_tax": 0,
#         "grand_total": grand_total,
#         "currency": metadata.get("currency") or "INR",
#         "payment_terms": "",
#         "notes": (
#             f"Extracted directly from {os.path.basename(file_path)}. "
#             + (
#                 "Customer is not present in the spreadsheet. Add a Customer "
#                 "column with its value before creating the Sales Order."
#                 if not metadata.get("customer_name")
#                 else ""
#             )
#         ).strip(),
#     }


# def extract_from_excel(file_path):

#     try:
#         import pandas as pd

#         # CSV SUPPORT
#         if file_path.lower().endswith(".csv"):

#             try:
#                 df = pd.read_csv(
#                     file_path,
#                     encoding="utf-8",
#                     sep=None,
#                     engine="python"
#                 )

#             except Exception:
#                 df = pd.read_csv(
#                     file_path,
#                     encoding="latin1",
#                     sep=None,
#                     engine="python"
#                 )

#             df = df.fillna("")

#             rows = [list(df.columns)] + df.values.tolist()
#             items = extract_items_from_rows(rows)
#             metadata = extract_metadata_from_rows(rows)

#             frappe.log_error(
#                 title="CSV DEBUG",
#                 message=json.dumps(items[:5], indent=2)
#             )

#             return build_spreadsheet_result(file_path, items, metadata)

#         # EXCEL SUPPORT
#         else:

#             text_output = ""

#             excel_data = pd.read_excel(
#                 file_path,
#                 sheet_name=None,
#                 header=None
#             )

#             for sheet_name, df in excel_data.items():

#                 text_output += f"\n\nSheet: {sheet_name}\n"

#                 df = df.fillna("")
#                 rows = df.values.tolist()
#                 items = extract_items_from_rows(rows)
#                 if items:
#                     metadata = extract_metadata_from_rows(rows)
#                     return build_spreadsheet_result(file_path, items, metadata)

#                 for _, row in df.iterrows():

#                     row_text = " | ".join(
#                         [
#                             str(cell).strip()
#                             for cell in row
#                             if str(cell).strip()
#                         ]
#                     )

#                     if row_text:
#                         text_output += row_text + "\n"

#             from ai_erpnext.claude_helper import (
#                 extract_from_email_text
#             )

#             extracted = extract_from_email_text(
#                 text_output
#             )

#             extracted["raw_text"] = text_output.strip()

#             return extracted

#     except Exception as e:

#         frappe.log_error(
#             title="Excel Extraction Error",
#             message=str(e)[:5000]
#         )

#         return None


# def enqueue_incoming_email(doc, method=None):
#     """Schedule processing only after Communication is saved."""

#     if doc.sent_or_received != "Received":
#         return

#     if doc.communication_type != "Communication":
#         return

#     try:
#         frappe.enqueue(
#             method="ai_erpnext.email_processor.process_committed_email",
#             queue="short",
#             enqueue_after_commit=True,
#             communication_name=doc.name,
#         )
#     except Exception:
#         # Never allow AI processing to stop Frappe from receiving an email.
#         frappe.log_error(
#             title="AI Email Enqueue Error",
#             message=frappe.get_traceback(),
#         )


# def process_file_attachment(doc, method=None):
#     """Process supported files after they are attached to a Communication."""
#     if (
#         doc.attached_to_doctype != "Communication"
#         or not doc.attached_to_name
#     ):
#         return

#     ext = (doc.file_name or "").rsplit(".", 1)[-1].lower()
#     if ext not in {"pdf", "jpg", "jpeg", "png", "webp", "xlsx", "xls", "csv"}:
#         return

#     frappe.enqueue(
#         method="ai_erpnext.email_processor.reprocess_communication_attachment",
#         queue="short",
#         enqueue_after_commit=True,
#         communication_name=doc.attached_to_name,
#     )


# def reprocess_communication_attachment(communication_name):
#     """Run attachment extraction after the File record is committed."""
#     if not frappe.db.exists("Communication", communication_name):
#         return

#     communication = frappe.get_doc("Communication", communication_name)
#     if frappe.db.exists(
#         "AI Email Queue", {"communication_link": communication_name}
#     ):
#         process_on_update(communication, "file_after_insert")
#     else:
#         process_incoming_email(communication, "file_after_insert")


# # def process_committed_email(communication_name, _retry=0):
# def process_committed_email(communication_name=None, _retry=0, **kwargs):
#     """Create AI queue record after Communication is committed.

#     Retries up to 3 times (with 5-second gaps) in case the worker
#     picks up the job before the DB transaction is fully visible.
#     """

#     MAX_RETRIES = 5
#     RETRY_DELAY = 10  # seconds
#     if not frappe.db.exists("Communication", communication_name):

#         if _retry < MAX_RETRIES:
#             frappe.log_error(
#                 title="AI Email Comm Not Found — Retrying",
#                 message=(
#                     f"Communication {communication_name} not found. "
#                     f"Retry {_retry + 1}/{MAX_RETRIES} in {RETRY_DELAY}s."
#                 ),
#             )
#             frappe.enqueue(
#                 method="ai_erpnext.email_processor.process_committed_email",
#                 queue="short",
#                 eta=RETRY_DELAY,
#                 communication_name=communication_name,
#                 _retry=_retry + 1,
#             )
#         else:
#             frappe.log_error(
#                 title="AI Email Communication Missing",
#                 message=(
#                     f"Communication {communication_name} not found "
#                     f"after {MAX_RETRIES} retries. Giving up."
#                 ),
#             )
#         return

#     if frappe.db.exists(
#         "AI Email Queue",
#         {"communication_link": communication_name},
#     ):
#         return

#     communication = frappe.get_doc("Communication", communication_name)
#     process_incoming_email(communication, "after_commit")


# def process_incoming_email(doc, method):

#     try:

#         frappe.log_error(
#             title="AI Hook Debug",
#             message=f"doc={doc.name} s_o_r={doc.sent_or_received} subject={doc.subject}"
#         )

#         if doc.sent_or_received != "Received":
#             return

#         if doc.communication_type != "Communication":
#             return

#         if frappe.db.exists(
#             "AI Email Queue",
#             {"communication_link": doc.name}
#         ):
#             return

#         body_lower = (doc.content or "").lower()

#         keywords = [
#             "quotation", "quote", "order", "invoice",
#             "quantity", "amount", "total", "price",
#             "rate", "item", "product", "service", "bill"
#         ]

#         keyword_hits = sum(
#             1 for k in keywords
#             if k in body_lower
#         )

#         attachments = frappe.get_all(
#             "File",
#             filters={
#                 "attached_to_doctype": "Communication",
#                 "attached_to_name": doc.name
#             },
#             fields=["file_url", "file_name"]
#         )

#         has_attachment = any(
#             att.file_name and
#             att.file_name.split(".")[-1].lower()
#             in [
#                 "pdf",
#                 "jpg",
#                 "jpeg",
#                 "png",
#                 "xlsx",
#                 "xls",
#                 "csv",
#                 "webp"
#             ]
#             for att in attachments
#         )

#         extracted = None
#         extraction_error = None

#         # Try attachment first
#         for att in attachments:

#             if not att.file_name:
#                 continue

#             ext = att.file_name.split(".")[-1].lower()

#             if ext not in [
#                 "pdf",
#                 "jpg",
#                 "jpeg",
#                 "png",
#                 "webp",
#                 "xlsx",
#                 "xls",
#                 "csv"
#             ]:
#                 continue

#             try:

#                 file_path = os.path.join(
#                     frappe.get_site_path(),
#                     "public",
#                     att.file_url.lstrip("/")
#                 )

#                 if not os.path.exists(file_path):
#                     file_path = os.path.join(
#                         frappe.get_site_path(),
#                         att.file_url.lstrip("/")
#                     )

#                 if not os.path.exists(file_path):
#                     continue

#                 from ai_erpnext.claude_helper import (
#                     extract_from_pdf,
#                     extract_from_image
#                 )

#                 mime_map = {
#                     "jpg": "image/jpeg",
#                     "jpeg": "image/jpeg",
#                     "png": "image/png",
#                     "webp": "image/webp"
#                 }

#                 if ext == "pdf":
#                     extracted = extract_from_pdf(file_path)

#                 elif ext in ["xlsx", "xls", "csv"]:
#                     extracted = extract_from_excel(file_path)

#                 else:
#                     extracted = extract_from_image(
#                         file_path,
#                         mime_map[ext]
#                     )

#                 break

#             except Exception as e:

#                 extraction_error = str(e)

#                 frappe.log_error(
#                     title="AI Attachment Extract Error",
#                     message=str(e)[:5000]
#                 )

#                 continue

#         # Always fallback to email body
#         if not extracted:
#             try:
#                 from ai_erpnext.claude_helper import (
#                     extract_from_email_text
#                 )
#                 extracted = extract_from_email_text(
#                     doc.content or ""
#                 )
#             except Exception as e:
#                 extraction_error = str(e)
#                 frappe.log_error(
#                     title="AI Email Body Error",
#                     message=str(e)[:5000]
#                 )

#         # Always save every email even if extraction failed
#         if not extracted:
#             extracted = {
#                 "items": [],
#                 "document_type": "General Email"
#             }

#         # Save queue
#         try:

#             queue_doc = frappe.get_doc({
#                 "doctype": "AI Email Queue",
#                 "email_subject": (
#                     doc.subject or "(No Subject)"
#                 )[:140],

#                 "from_email": (
#                     doc.sender or ""
#                 )[:140],

#                 "received_on": doc.communication_date or doc.creation,

#                 "source_type": "Email",

#                 "extracted_json": json.dumps(
#                     extracted or {},
#                     indent=2
#                 ),

#                 "suggested_doctype": (
#                     extracted or {}
#                 ).get(
#                     "document_type",
#                     "Pending Review"
#                 ),

#                 "status": "Pending",

#                 "communication_link": doc.name,

#                 "email_body": (
#                     doc.content or ""
#                 )[:5000]
#             })

#             queue_doc.insert(
#                 ignore_permissions=True
#             )

#             frappe.db.commit()

#         except Exception as e:

#             frappe.log_error(
#                 title="AI Queue Insert Error",
#                 message=str(e)[:5000]
#             )

#     except Exception as e:

#         frappe.log_error(
#             title="AI Hook Outer Error",
#             message=str(e)[:5000]
#         )


# def process_on_update(doc, method):

#     if doc.sent_or_received != "Received":
#         return

#     # Ensure Communication exists before processing
#     if not frappe.db.exists("Communication", doc.name):
#         return

#     queue = frappe.db.get_value(
#         "AI Email Queue",
#         {"communication_link": doc.name},
#         ["name", "extracted_json"],
#         as_dict=True
#     )

#     if not queue:
#         enqueue_incoming_email(doc, method)
#         return

#     try:
#         existing = json.loads(
#             queue.extracted_json or "{}"
#         )
#     except Exception:
#         existing = {}

#     if (
#         existing.get("items")
#         and len(existing.get("items")) > 0
#     ):
#         return

#     attachments = frappe.get_all(
#         "File",
#         filters={
#             "attached_to_doctype": "Communication",
#             "attached_to_name": doc.name
#         },
#         fields=[
#             "file_url",
#             "file_name",
#             "is_private"
#         ]
#     )

#     for att in attachments:

#         if not att.file_name:
#             continue

#         ext = att.file_name.split(".")[-1].lower()

#         if ext not in [
#             "pdf",
#             "jpg",
#             "jpeg",
#             "png",
#             "webp",
#             "xlsx",
#             "xls",
#             "csv"
#         ]:
#             continue

#         try:

#             file_path = os.path.join(
#                 frappe.get_site_path(),
#                 "public",
#                 att.file_url.lstrip("/")
#             )

#             if not os.path.exists(file_path):
#                 file_path = os.path.join(
#                     frappe.get_site_path(),
#                     att.file_url.lstrip("/")
#                 )

#             if not os.path.exists(file_path):
#                 continue

#             from ai_erpnext.claude_helper import (
#                 extract_from_pdf,
#                 extract_from_image
#             )

#             mime_map = {
#                 "jpg": "image/jpeg",
#                 "jpeg": "image/jpeg",
#                 "png": "image/png",
#                 "webp": "image/webp"
#             }

#             if ext == "pdf":
#                 extracted = extract_from_pdf(file_path)

#             elif ext in ["xlsx", "xls", "csv"]:
#                 extracted = extract_from_excel(file_path)

#             else:
#                 extracted = extract_from_image(
#                     file_path,
#                     mime_map[ext]
#                 )

#             if extracted:

#                 frappe.db.set_value(
#                     "AI Email Queue",
#                     queue.name,
#                     {
#                         "extracted_json": json.dumps(
#                             extracted,
#                             indent=2
#                         ),

#                         "suggested_doctype": extracted.get(
#                             "document_type",
#                             "Spreadsheet Document"
#                         ),

#                         "source_type": f"Attachment: {att.file_name}"
#                     }
#                 )

#                 frappe.db.commit()

#                 frappe.log_error(
#                     title="AI Hook Debug",
#                     message=f"Updated {queue.name} with attachment data from on_update"
#                 )

#             break

#         except Exception as e:

#             frappe.log_error(
#                 title="AI On Update Attachment Error",
#                 message=str(e)[:5000]
#             )


import frappe
import json
import os
import re


def normalize_header(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def header_matches(header, alias):
    return (
        header == alias
        or header.startswith(alias + "_")
        or header.endswith("_" + alias)
    )


def find_header_index(headers, *aliases):
    for alias in aliases:
        for index, header in enumerate(headers):
            if header_matches(header, alias):
                return index
    return None


def to_number(value):
    if value in (None, ""):
        return 0

    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(cleaned) if cleaned else 0
    except (TypeError, ValueError):
        return 0


def extract_items_from_rows(rows):
    """Find an item-table header in CSV/XLSX rows and parse its data rows."""
    item_aliases = ("item_name", "item_code", "item", "product", "description")
    qty_aliases = ("qty", "quantity", "stock_qty")
    rate_aliases = ("rate", "price", "unit_price")
    amount_aliases = ("amount", "total", "base_amount", "net_amount")

    header_index = None
    headers = []

    for index, row in enumerate(rows):
        normalized = [normalize_header(cell) for cell in row]
        has_item = find_header_index(normalized, *item_aliases) is not None
        has_value = any(
            find_header_index(normalized, *aliases) is not None
            for aliases in (qty_aliases, rate_aliases, amount_aliases)
        )
        if has_item and has_value:
            header_index = index
            headers = normalized
            break

    if header_index is None:
        return []

    item_name_index = find_header_index(
        headers, "item_name", "item", "product", "description", "item_code"
    )
    item_code_index = find_header_index(headers, "item_code", "code", "sku")
    description_index = find_header_index(headers, "description")
    qty_index = find_header_index(headers, *qty_aliases)
    rate_index = find_header_index(headers, *rate_aliases)
    amount_index = find_header_index(headers, *amount_aliases)
    uom_index = find_header_index(headers, "uom", "stock_uom", "unit")
    hsn_index = find_header_index(headers, "hsn_code", "hsn", "gst_hsn_code")

    def cell(row, index, default=""):
        return row[index] if index is not None and index < len(row) else default

    items = []
    for row in rows[header_index + 1:]:
        item_name = str(cell(row, item_name_index)).strip()
        item_code = str(cell(row, item_code_index)).strip()

        # ERPNext export templates sometimes include a second field-name row.
        if normalize_header(item_name) in item_aliases:
            continue
        if not item_name and not item_code:
            continue

        qty = to_number(cell(row, qty_index))
        rate = to_number(cell(row, rate_index))
        amount = to_number(cell(row, amount_index)) or qty * rate

        items.append({
            "item_name": item_name or item_code,
            "item_code": item_code,
            "description": str(
                cell(row, description_index, item_name or item_code)
            ).strip(),
            "qty": qty or 1,
            "uom": str(cell(row, uom_index, "Nos")).strip() or "Nos",
            "rate": rate,
            "amount": amount,
            "hsn_code": str(cell(row, hsn_index)).strip(),
            "tax_rate": 0,
        })

    return items


def extract_metadata_from_rows(rows):
    """Extract parent Sales/Purchase document fields from exported rows."""
    aliases = {
        "customer_name": ("customer", "customer_name", "party_name"),
        "supplier_name": ("supplier", "supplier_name"),
        "document_date": (
            "transaction_date", "posting_date", "date", "order_date"
        ),
        "due_date": ("delivery_date", "due_date", "schedule_date"),
        "document_number": ("id", "name", "sales_order", "purchase_order"),
        "currency": ("currency",),
    }

    for header_position, header_row in enumerate(rows):
        headers = [normalize_header(cell) for cell in header_row]
        indexes = {
            field: find_header_index(headers, *field_aliases)
            for field, field_aliases in aliases.items()
        }
        if indexes["customer_name"] is None and indexes["supplier_name"] is None:
            continue

        for data_row in rows[header_position + 1:]:
            metadata = {}
            for field, index in indexes.items():
                if index is not None and index < len(data_row):
                    value = str(data_row[index]).strip()
                    if value and normalize_header(value) not in aliases[field]:
                        metadata[field] = value

            if metadata.get("customer_name") or metadata.get("supplier_name"):
                return metadata

    return {}


def build_spreadsheet_result(file_path, items, metadata=None):
    metadata = metadata or {}
    file_name = os.path.basename(file_path).lower()
    document_type = (
        "Sales Invoice" if "sales invoice" in file_name
        else "Purchase Invoice" if "purchase invoice" in file_name
        else "Purchase Order" if "purchase order" in file_name
        else "Sales Order"
    )
    grand_total = sum(item["amount"] for item in items)

    return {
        "document_type": document_type,
        "customer_name": metadata.get("customer_name", ""),
        "customer": metadata.get("customer_name", ""),
        "supplier_name": metadata.get("supplier_name", ""),
        "supplier": metadata.get("supplier_name", ""),
        "document_date": metadata.get("document_date", ""),
        "document_number": metadata.get("document_number", ""),
        "due_date": metadata.get("due_date", ""),
        "items": items,
        "taxes": [],
        "total_before_tax": grand_total,
        "total_tax": 0,
        "grand_total": grand_total,
        "currency": metadata.get("currency") or "INR",
        "payment_terms": "",
        "notes": f"Extracted directly from {os.path.basename(file_path)}",
    }


def extract_from_excel(file_path):

    try:
        import pandas as pd

        # CSV SUPPORT
        if file_path.lower().endswith(".csv"):

            try:
                df = pd.read_csv(
                    file_path,
                    encoding="utf-8",
                    sep=None,
                    engine="python"
                )

            except Exception:
                df = pd.read_csv(
                    file_path,
                    encoding="latin1",
                    sep=None,
                    engine="python"
                )

            df = df.fillna("")

            rows = [list(df.columns)] + df.values.tolist()
            items = extract_items_from_rows(rows)
            metadata = extract_metadata_from_rows(rows)

            frappe.log_error(
                title="CSV DEBUG",
                message=json.dumps(items[:5], indent=2)
            )

            return build_spreadsheet_result(file_path, items, metadata)

        # EXCEL SUPPORT
        else:

            text_output = ""

            excel_data = pd.read_excel(
                file_path,
                sheet_name=None,
                header=None
            )

            for sheet_name, df in excel_data.items():

                text_output += f"\n\nSheet: {sheet_name}\n"

                df = df.fillna("")
                rows = df.values.tolist()
                items = extract_items_from_rows(rows)
                if items:
                    metadata = extract_metadata_from_rows(rows)
                    return build_spreadsheet_result(file_path, items, metadata)

                for _, row in df.iterrows():

                    row_text = " | ".join(
                        [
                            str(cell).strip()
                            for cell in row
                            if str(cell).strip()
                        ]
                    )

                    if row_text:
                        text_output += row_text + "\n"

            from ai_erpnext.claude_helper import (
                extract_from_email_text
            )

            extracted = extract_from_email_text(
                text_output
            )

            extracted["raw_text"] = text_output.strip()

            return extracted

    except Exception as e:

        frappe.log_error(
            title="Excel Extraction Error",
            message=str(e)[:5000]
        )

        return None


def enqueue_incoming_email(doc, method=None):
    """Schedule processing only after Communication is saved."""

    if doc.sent_or_received != "Received":
        return

    if doc.communication_type != "Communication":
        return

    try:
        frappe.enqueue(
            method="ai_erpnext.email_processor.process_committed_email",
            queue="short",
            enqueue_after_commit=True,
            communication_name=doc.name,
        )
    except Exception:
        # Never allow AI processing to stop Frappe from receiving an email.
        frappe.log_error(
            title="AI Email Enqueue Error",
            message=frappe.get_traceback(),
        )


def process_file_attachment(doc, method=None):
    """Process supported files after they are attached to a Communication."""
    if (
        doc.attached_to_doctype != "Communication"
        or not doc.attached_to_name
    ):
        return

    ext = (doc.file_name or "").rsplit(".", 1)[-1].lower()
    if ext not in {"pdf", "jpg", "jpeg", "png", "webp", "xlsx", "xls", "csv"}:
        return

    frappe.enqueue(
        method="ai_erpnext.email_processor.reprocess_communication_attachment",
        queue="short",
        enqueue_after_commit=True,
        communication_name=doc.attached_to_name,
    )


def reprocess_communication_attachment(communication_name):
    """Run attachment extraction after the File record is committed."""
    if not frappe.db.exists("Communication", communication_name):
        return

    communication = frappe.get_doc("Communication", communication_name)
    if frappe.db.exists(
        "AI Email Queue", {"communication_link": communication_name}
    ):
        process_on_update(communication, "file_after_insert")
    else:
        process_incoming_email(communication, "file_after_insert")


def get_email_duplicate_filters(doc):
    received_on = doc.communication_date or doc.creation
    return {
        "email_subject": (doc.subject or "(No Subject)")[:140],
        "from_email": (doc.sender or "")[:140],
        "received_on": received_on,
    }


def get_existing_queue_for_email(doc):
    duplicate_filters = get_email_duplicate_filters(doc)
    existing = frappe.db.get_value(
        "AI Email Queue",
        duplicate_filters,
        ["name", "communication_link"],
        as_dict=True,
    )
    if existing:
        return existing

    return frappe.db.get_value(
        "AI Email Queue",
        {"communication_link": doc.name},
        ["name", "communication_link"],
        as_dict=True,
    )


# def process_committed_email(communication_name, _retry=0):
def process_committed_email(communication_name=None, _retry=0, **kwargs):
    """Create AI queue record after Communication is committed.

    Retries up to 3 times (with 5-second gaps) in case the worker
    picks up the job before the DB transaction is fully visible.
    """

    MAX_RETRIES = 5
    RETRY_DELAY = 10  # seconds
    if not frappe.db.exists("Communication", communication_name):

        if _retry < MAX_RETRIES:
            frappe.log_error(
                title="AI Email Comm Not Found — Retrying",
                message=(
                    f"Communication {communication_name} not found. "
                    f"Retry {_retry + 1}/{MAX_RETRIES} in {RETRY_DELAY}s."
                ),
            )
            frappe.enqueue(
                method="ai_erpnext.email_processor.process_committed_email",
                queue="short",
                eta=RETRY_DELAY,
                communication_name=communication_name,
                _retry=_retry + 1,
            )
        else:
            frappe.log_error(
                title="AI Email Communication Missing",
                message=(
                    f"Communication {communication_name} not found "
                    f"after {MAX_RETRIES} retries. Giving up."
                ),
            )
        return

    communication = frappe.get_doc("Communication", communication_name)
    if get_existing_queue_for_email(communication):
        return

    process_incoming_email(communication, "after_commit")


def process_incoming_email(doc, method):

    try:

        frappe.log_error(
            title="AI Hook Debug",
            message=f"doc={doc.name} s_o_r={doc.sent_or_received} subject={doc.subject}"
        )

        if doc.sent_or_received != "Received":
            return

        if doc.communication_type != "Communication":
            return

        if get_existing_queue_for_email(doc):
            return

        body_lower = (doc.content or "").lower()

        keywords = [
            "quotation", "quote", "order", "invoice",
            "quantity", "amount", "total", "price",
            "rate", "item", "product", "service", "bill"
        ]

        keyword_hits = sum(
            1 for k in keywords
            if k in body_lower
        )

        attachments = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "Communication",
                "attached_to_name": doc.name
            },
            fields=["file_url", "file_name"]
        )

        has_attachment = any(
            att.file_name and
            att.file_name.split(".")[-1].lower()
            in [
                "pdf",
                "jpg",
                "jpeg",
                "png",
                "xlsx",
                "xls",
                "csv",
                "webp"
            ]
            for att in attachments
        )

        extracted = None
        extraction_error = None

        # Try attachment first
        for att in attachments:

            if not att.file_name:
                continue

            ext = att.file_name.split(".")[-1].lower()

            if ext not in [
                "pdf",
                "jpg",
                "jpeg",
                "png",
                "webp",
                "xlsx",
                "xls",
                "csv"
            ]:
                continue

            try:

                file_path = os.path.join(
                    frappe.get_site_path(),
                    "public",
                    att.file_url.lstrip("/")
                )

                if not os.path.exists(file_path):
                    file_path = os.path.join(
                        frappe.get_site_path(),
                        att.file_url.lstrip("/")
                    )

                if not os.path.exists(file_path):
                    continue

                from ai_erpnext.claude_helper import (
                    extract_from_pdf,
                    extract_from_image
                )

                mime_map = {
                    "jpg": "image/jpeg",
                    "jpeg": "image/jpeg",
                    "png": "image/png",
                    "webp": "image/webp"
                }

                if ext == "pdf":
                    extracted = extract_from_pdf(file_path)

                elif ext in ["xlsx", "xls", "csv"]:
                    extracted = extract_from_excel(file_path)

                else:
                    extracted = extract_from_image(
                        file_path,
                        mime_map[ext]
                    )

                break

            except Exception as e:

                extraction_error = str(e)

                frappe.log_error(
                    title="AI Attachment Extract Error",
                    message=str(e)[:5000]
                )

                continue

        # Always fallback to email body
        if not extracted:
            try:
                from ai_erpnext.claude_helper import (
                    extract_from_email_text
                )
                extracted = extract_from_email_text(
                    doc.content or ""
                )
            except Exception as e:
                extraction_error = str(e)
                frappe.log_error(
                    title="AI Email Body Error",
                    message=str(e)[:5000]
                )

        # Always save every email even if extraction failed
        if not extracted:
            extracted = {
                "items": [],
                "document_type": "General Email"
            }

        # Save queue
        try:

            duplicate_filters = get_email_duplicate_filters(doc)
            if frappe.db.exists("AI Email Queue", duplicate_filters):
                return

            queue_doc = frappe.get_doc({
                "doctype": "AI Email Queue",
                "email_subject": duplicate_filters["email_subject"],
                "from_email": duplicate_filters["from_email"],
                "received_on": duplicate_filters["received_on"],

                "source_type": "Email",

                "extracted_json": json.dumps(
                    extracted or {},
                    indent=2
                ),

                "suggested_doctype": (
                    extracted or {}
                ).get(
                    "document_type",
                    "Pending Review"
                ),

                "status": "Pending",

                "communication_link": doc.name,

                "email_body": (
                    doc.content or ""
                )[:5000]
            })

            queue_doc.insert(
                ignore_permissions=True
            )

            frappe.db.commit()

        except Exception as e:

            frappe.log_error(
                title="AI Queue Insert Error",
                message=str(e)[:5000]
            )

    except Exception as e:

        frappe.log_error(
            title="AI Hook Outer Error",
            message=str(e)[:5000]
        )


def process_on_update(doc, method):

    if doc.sent_or_received != "Received":
        return

    # Ensure Communication exists before processing
    if not frappe.db.exists("Communication", doc.name):
        return

    queue = frappe.db.get_value(
        "AI Email Queue",
        {"communication_link": doc.name},
        ["name", "extracted_json"],
        as_dict=True
    )

    if not queue:
        enqueue_incoming_email(doc, method)
        return

    try:
        existing = json.loads(
            queue.extracted_json or "{}"
        )
    except Exception:
        existing = {}

    if (
        existing.get("items")
        and len(existing.get("items")) > 0
    ):
        return

    attachments = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Communication",
            "attached_to_name": doc.name
        },
        fields=[
            "file_url",
            "file_name",
            "is_private"
        ]
    )

    for att in attachments:

        if not att.file_name:
            continue

        ext = att.file_name.split(".")[-1].lower()

        if ext not in [
            "pdf",
            "jpg",
            "jpeg",
            "png",
            "webp",
            "xlsx",
            "xls",
            "csv"
        ]:
            continue

        try:

            file_path = os.path.join(
                frappe.get_site_path(),
                "public",
                att.file_url.lstrip("/")
            )

            if not os.path.exists(file_path):
                file_path = os.path.join(
                    frappe.get_site_path(),
                    att.file_url.lstrip("/")
                )

            if not os.path.exists(file_path):
                continue

            from ai_erpnext.claude_helper import (
                extract_from_pdf,
                extract_from_image
            )

            mime_map = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "webp": "image/webp"
            }

            if ext == "pdf":
                extracted = extract_from_pdf(file_path)

            elif ext in ["xlsx", "xls", "csv"]:
                extracted = extract_from_excel(file_path)

            else:
                extracted = extract_from_image(
                    file_path,
                    mime_map[ext]
                )

            if extracted:

                frappe.db.set_value(
                    "AI Email Queue",
                    queue.name,
                    {
                        "extracted_json": json.dumps(
                            extracted,
                            indent=2
                        ),

                        "suggested_doctype": extracted.get(
                            "document_type",
                            "Spreadsheet Document"
                        ),

                        "source_type": f"Attachment: {att.file_name}"
                    }
                )

                frappe.db.commit()

                frappe.log_error(
                    title="AI Hook Debug",
                    message=f"Updated {queue.name} with attachment data from on_update"
                )

            break

        except Exception as e:

            frappe.log_error(
                title="AI On Update Attachment Error",
                message=str(e)[:5000]
            )
