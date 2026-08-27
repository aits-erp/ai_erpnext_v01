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
from zipfile import ZipFile
from xml.etree import ElementTree as ET

SUPPORTED_ATTACHMENT_EXTENSIONS = {
    "pdf", "jpg", "jpeg", "png", "webp", "xlsx", "xls", "csv"
}


def get_communication_message_id(doc):
    message_id = str(getattr(doc, "message_id", None) or "").strip()
    return message_id[:140]


def get_communication_email_uid(doc):
    uid = str(getattr(doc, "uid", None) or "").strip()
    email_account = str(getattr(doc, "email_account", None) or "").strip()
    if uid and email_account:
        return f"{email_account}:{uid}"[:140]
    return uid[:140]


def ai_email_queue_has_column(fieldname):
    try:
        return bool(
            frappe.db.sql(
                "show columns from `tabAI Email Queue` like %s",
                fieldname,
            )
        )
    except Exception:
        return False


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


def find_items_header_index(headers, *aliases):
    for alias in aliases:
        exact = f"{alias}_items"
        for index, header in enumerate(headers):
            if header == exact:
                return index

        for index, header in enumerate(headers):
            if header.endswith("_items") and header_matches(header[:-6], alias):
                return index

    return find_header_index(headers, *aliases)


def row_has_header_set(headers, *aliases):
    return all(find_items_header_index(headers, alias) is not None for alias in aliases)


def to_number(value):
    if value in (None, ""):
        return 0

    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(cleaned) if cleaned else 0
    except (TypeError, ValueError):
        return 0


def split_item_code_label(value):
    text = str(value or "").strip()
    if ":" not in text:
        return text, ""

    code, label = text.split(":", 1)
    return code.strip(), label.strip()


def clean_hsn_code(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return re.sub(r"[^0-9]", "", text)


def extract_items_from_rows(rows):
    """Find an item-table header in CSV/XLSX rows and parse its data rows."""
    item_aliases = (
        "item_name", "item_code", "sku", "item", "product",
        "product_name", "product_title", "name", "description"
    )
    qty_aliases = (
        "qty", "quantity", "stock_qty", "order_qty", "order_quantity",
        "total_order_ctns_pcs", "total_order_ctn_pcs",
        "total_order_ctns", "order_ctns_pcs", "ctns_pcs"
    )
    rate_aliases = ("rate", "price", "unit_price")
    amount_aliases = ("amount", "total", "base_amount", "net_amount")

    header_index = None
    headers = []

    for index, row in enumerate(rows):
        normalized = [normalize_header(cell) for cell in row]
        # ERPNext exports contain many parent-field rows before the Items grid.
        # Prefer the actual child table header: Item Code + Quantity + Rate/Amount.
        if (
            find_items_header_index(normalized, "item_code", "sku") is not None
            and find_items_header_index(normalized, *qty_aliases) is not None
            and (
                find_items_header_index(normalized, "rate") is not None
                or find_items_header_index(normalized, "amount") is not None
                or find_items_header_index(normalized, *qty_aliases) is not None
            )
        ):
            header_index = index
            headers = normalized
            break

        has_item = find_header_index(normalized, *item_aliases) is not None
        has_value = any(
            find_header_index(normalized, *aliases) is not None
            for aliases in (qty_aliases, rate_aliases, amount_aliases)
        )
        if has_item and has_value and normalize_header(row[0] if row else "") in {
            "no",
            "idx",
            "item",
            "item_code",
        }:
            header_index = index
            headers = normalized
            break

    if header_index is None:
        return []

    item_name_index = find_items_header_index(
        headers, "item_name", "item", "product", "description", "item_code"
    )
    item_code_index = find_items_header_index(headers, "item_code", "code", "sku")
    description_index = find_items_header_index(headers, "description")
    qty_index = find_items_header_index(headers, *qty_aliases)
    rate_index = find_items_header_index(headers, "rate", "price", "unit_price")
    amount_index = find_items_header_index(headers, "amount", "net_amount")
    uom_index = find_items_header_index(headers, "uom", "stock_uom", "unit")
    hsn_index = find_items_header_index(
        headers, "hsn_sac", "hsn_code", "hsn", "gst_hsn_code"
    )
    capacity_index = find_items_header_index(headers, "capacity", "capacity_size", "size")

    def cell(row, index, default=""):
        return row[index] if index is not None and index < len(row) else default

    items = []
    last_item_name = ""
    for row in rows[header_index + 1:]:
        item_name = str(cell(row, item_name_index)).strip()
        item_code = str(cell(row, item_code_index)).strip()
        capacity = str(cell(row, capacity_index)).strip()
        if item_name:
            last_item_name = item_name
        elif item_code and last_item_name:
            item_name = last_item_name
        if item_code and not item_name:
            parsed_code, parsed_name = split_item_code_label(item_code)
            item_code = parsed_code
            item_name = parsed_name or parsed_code
        elif item_code and item_code == item_name:
            parsed_code, parsed_name = split_item_code_label(item_code)
            item_code = parsed_code
            item_name = parsed_name or parsed_code
        first_cell = normalize_header(cell(row, 0))

        # ERPNext export templates sometimes include a second field-name row.
        if normalize_header(item_name) in item_aliases:
            continue
        if first_cell in {
            "total_quantity",
            "total",
            "taxes",
            "sales_taxes_and_charges",
            "totals",
            "comments",
            "activity",
            "additional_discount",
            "tax_breakup",
        }:
            break
        if not item_name and not item_code:
            if items:
                break
            continue

        qty = to_number(cell(row, qty_index))
        rate = to_number(cell(row, rate_index))
        amount = to_number(cell(row, amount_index)) or qty * rate
        if qty <= 0 and amount <= 0:
            if items:
                break
            continue

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
            "hsn_code": clean_hsn_code(cell(row, hsn_index)),
            "tax_rate": 0,
        })
        if capacity and capacity.lower() not in (item_name or "").lower():
            items[-1]["description"] = (
                f"{items[-1]['description']} - {capacity}"
                if items[-1]["description"] else capacity
            )

    return items


def extract_documents_from_rows(rows, document_type=None):
    """Parse flat ERPNext export rows into separate document payloads."""
    if not rows:
        return []

    headers = [normalize_header(cell) for cell in rows[0]]

    def index(*aliases):
        return find_header_index(headers, *aliases)

    def item_index(*aliases):
        return find_items_header_index(headers, *aliases)

    customer_index = index("customer", "customer_name", "party_name")
    supplier_index = index("supplier", "supplier_name")
    date_index = index("date", "transaction_date", "posting_date", "order_date")
    due_date_index = index("delivery_date", "due_date", "schedule_date")
    number_index = index("id", "name", "sales_order", "purchase_order")
    currency_index = index("currency")

    item_name_index = item_index(
        "item_name", "item", "product", "product_name", "product_title",
        "name", "description", "item_code"
    )
    item_code_index = item_index("item_code", "code", "sku")
    description_index = item_index("description")
    qty_index = item_index(
        "quantity", "qty", "stock_qty", "order_qty", "order_quantity",
        "total_order_ctns_pcs", "total_order_ctn_pcs",
        "total_order_ctns", "order_ctns_pcs", "ctns_pcs"
    )
    rate_index = item_index("rate", "price", "unit_price")
    amount_index = item_index("amount", "net_amount")
    uom_index = item_index("uom", "stock_uom", "unit")
    hsn_index = item_index("hsn_sac", "hsn_code", "hsn", "gst_hsn_code")
    item_due_date_index = item_index("delivery_date", "schedule_date", "due_date")

    if item_name_index is None and item_code_index is None:
        return []

    def cell(row, cell_index, default=""):
        if cell_index is None or cell_index >= len(row):
            return default
        return str(row[cell_index] or "").strip()

    documents = []
    by_key = {}
    active_key = None

    for row in rows[1:]:
        item_name = cell(row, item_name_index)
        item_code = cell(row, item_code_index)
        if item_code and (not item_name or item_code == item_name):
            parsed_code, parsed_name = split_item_code_label(item_code)
            item_code = parsed_code
            item_name = parsed_name or parsed_code

        qty = to_number(cell(row, qty_index))
        rate = to_number(cell(row, rate_index))
        amount = to_number(cell(row, amount_index)) or qty * rate
        has_item = bool(item_name or item_code) and (qty > 0 or amount > 0)

        customer_name = cell(row, customer_index)
        supplier_name = cell(row, supplier_index)
        document_number = cell(row, number_index)
        document_date = cell(row, date_index)
        due_date = cell(row, item_due_date_index) or cell(row, due_date_index)
        currency = cell(row, currency_index, "INR") or "INR"

        starts_new_document = bool(
            document_number or customer_name or supplier_name
        )
        if starts_new_document:
            key = (
                document_number
                or "|".join(
                    [
                        customer_name or supplier_name,
                        document_date,
                        due_date,
                        str(len(documents) + 1),
                    ]
                )
            )
            if key not in by_key:
                doc = {
                    "document_type": document_type or "Sales Order",
                    "customer_name": customer_name,
                    "customer": customer_name,
                    "supplier_name": supplier_name,
                    "supplier": supplier_name,
                    "document_date": document_date,
                    "document_number": document_number,
                    "due_date": due_date,
                    "currency": currency,
                    "items": [],
                    "taxes": [],
                    "payment_terms": "",
                }
                by_key[key] = doc
                documents.append(doc)
            else:
                doc = by_key[key]
                if due_date and not doc.get("due_date"):
                    doc["due_date"] = due_date
            active_key = key
        elif active_key:
            doc = by_key[active_key]
        else:
            continue

        if not has_item:
            continue

        item = {
            "item_name": item_name or item_code,
            "item_code": item_code,
            "description": cell(row, description_index, item_name or item_code),
            "qty": qty or 1,
            "uom": cell(row, uom_index, "Nos") or "Nos",
            "rate": rate,
            "amount": amount,
            "hsn_code": clean_hsn_code(cell(row, hsn_index)),
            "tax_rate": 0,
        }
        if due_date:
            item["delivery_date"] = due_date
        doc["items"].append(item)

    result = []
    for doc in documents:
        if not doc.get("items"):
            continue
        grand_total = sum(item.get("amount") or 0 for item in doc["items"])
        doc["total_before_tax"] = grand_total
        doc["total_tax"] = 0
        doc["grand_total"] = grand_total
        result.append(doc)

    return result


def extract_metadata_from_rows(rows):
    """Extract parent Sales/Purchase document fields from exported rows."""
    key_value_aliases = {
        "customer_name": ("customer", "customer_name", "party_name"),
        "supplier_name": ("supplier", "supplier_name"),
        "document_date": (
            "transaction_date", "posting_date", "date", "order_date"
        ),
        "due_date": ("delivery_date", "due_date", "payment_due_date", "schedule_date"),
        "document_number": ("po_no", "customer_s_purchase_order", "id", "name"),
        "currency": ("currency",),
    }

    metadata = {}
    aliases = {
        "customer_name": ("customer", "customer_name", "party_name"),
        "supplier_name": ("supplier", "supplier_name"),
        "document_date": (
            "transaction_date", "posting_date", "date", "order_date"
        ),
        "due_date": ("delivery_date", "due_date", "payment_due_date", "schedule_date"),
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

    for row in rows:
        if len(row) > 20:
            continue
        normalized = [normalize_header(cell) for cell in row]
        values = [str(cell).strip() for cell in row]
        for field, field_aliases in key_value_aliases.items():
            if metadata.get(field):
                continue
            for index, header in enumerate(normalized):
                if not any(header_matches(header, alias) for alias in field_aliases):
                    continue
                for value in values[index + 1:]:
                    if value and normalize_header(value) not in field_aliases:
                        metadata[field] = value
                        break
                break

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
    documents = metadata.pop("documents", []) if metadata else []
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
        "documents": documents,
    }


def excel_column_to_index(cell_ref):
    letters = re.sub(r"[^A-Z]", "", str(cell_ref or "").upper())
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return index - 1


def read_xlsx_rows(file_path):
    """Read XLSX rows with stdlib only, used when pandas/openpyxl is unavailable."""
    namespace = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }

    with ZipFile(file_path) as workbook:
        shared_strings = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            shared_root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for shared_item in shared_root.findall("a:si", namespace):
                parts = [
                    text_node.text or ""
                    for text_node in shared_item.findall(".//a:t", namespace)
                ]
                shared_strings.append("".join(parts))

        workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
        rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
        rels = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_root
        }

        sheets = []
        for sheet in workbook_root.findall(".//a:sheet", namespace):
            relation_id = sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            target = rels.get(relation_id)
            if not target:
                continue
            sheet_path = target if target.startswith("xl/") else f"xl/{target.lstrip('/')}"
            sheet_root = ET.fromstring(workbook.read(sheet_path))
            rows = []
            for row in sheet_root.findall(".//a:sheetData/a:row", namespace):
                values = []
                for cell in row.findall("a:c", namespace):
                    cell_ref = cell.attrib.get("r", "")
                    column_index = excel_column_to_index(cell_ref)
                    while len(values) <= column_index:
                        values.append("")

                    value_node = cell.find("a:v", namespace)
                    value = "" if value_node is None else (value_node.text or "")
                    if cell.attrib.get("t") == "s" and value:
                        value = shared_strings[int(value)]
                    elif cell.attrib.get("t") == "inlineStr":
                        value = "".join(
                            text_node.text or ""
                            for text_node in cell.findall(".//a:t", namespace)
                        )
                    values[column_index] = value
                rows.append(values)
            sheets.append((sheet.attrib.get("name", ""), rows))

        return sheets


def extract_spreadsheet_rows(file_path, document_type, rows_by_sheet):
    all_items = []
    first_metadata = {}

    for _sheet_name, rows in rows_by_sheet:
        if not rows:
            continue
        documents = extract_documents_from_rows(rows, document_type)
        sheet_items = [item for doc in documents for item in doc.get("items", [])]
        if not sheet_items:
            sheet_items = extract_items_from_rows(rows)

        if sheet_items:
            all_items.extend(sheet_items)
            if not first_metadata:
                first_metadata = extract_metadata_from_rows(rows)

    if not first_metadata:
        first_metadata = {}

    document = dict(
        first_metadata,
        document_type=document_type,
        items=all_items,
        documents=[],
    )
    if all_items:
        document["documents"] = [dict(document, documents=[])]

    return build_spreadsheet_result(file_path, all_items, document)


def extract_from_excel(file_path):

    try:
        try:
            import pandas as pd
        except Exception:
            pd = None

        file_name = os.path.basename(file_path).lower()
        document_type = (
            "Sales Invoice" if "sales invoice" in file_name
            else "Purchase Invoice" if "purchase invoice" in file_name
            else "Purchase Order" if "purchase order" in file_name
            else "Sales Order"
        )

        # CSV SUPPORT
        if file_path.lower().endswith(".csv"):

            if pd:
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
            else:
                import csv
                try:
                    csv_file = open(file_path, newline="", encoding="utf-8-sig")
                    rows = list(csv.reader(csv_file))
                    csv_file.close()
                except Exception:
                    csv_file = open(file_path, newline="", encoding="latin1")
                    rows = list(csv.reader(csv_file))
                    csv_file.close()

            documents = extract_documents_from_rows(rows, document_type)
            items = [item for doc in documents for item in doc.get("items", [])]
            if not items:
                items = extract_items_from_rows(rows)
            metadata = extract_metadata_from_rows(rows)
            if documents:
                metadata = dict(documents[0], documents=documents)

            frappe.log_error(
                title="CSV DEBUG",
                message=json.dumps(
                    {
                        "document_count": len(documents),
                        "items": items[:5],
                    },
                    indent=2
                )
            )

            return build_spreadsheet_result(file_path, items, metadata)

        # EXCEL SUPPORT
        else:

            text_output = ""

            if not pd:
                return extract_spreadsheet_rows(
                    file_path,
                    document_type,
                    read_xlsx_rows(file_path)
                )

            try:
                excel_data = pd.read_excel(
                    file_path,
                    sheet_name=None,
                    header=None
                )
            except Exception:
                return extract_spreadsheet_rows(
                    file_path,
                    document_type,
                    read_xlsx_rows(file_path)
                )

            rows_by_sheet = []
            for sheet_name, df in excel_data.items():

                text_output += f"\n\nSheet: {sheet_name}\n"

                df = df.fillna("")
                rows = df.values.tolist()
                rows_by_sheet.append((sheet_name, rows))

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

            spreadsheet_result = extract_spreadsheet_rows(
                file_path,
                document_type,
                rows_by_sheet
            )
            if spreadsheet_result.get("items"):
                return spreadsheet_result

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
    fields = ["name", "communication_link", "extracted_json"]

    message_id = get_communication_message_id(doc)
    if message_id and ai_email_queue_has_column("message_id"):
        existing = frappe.db.get_value(
            "AI Email Queue",
            {"message_id": message_id},
            fields,
            as_dict=True,
        )
        if existing:
            return existing

    email_uid = get_communication_email_uid(doc)
    if email_uid and ai_email_queue_has_column("email_uid"):
        existing = frappe.db.get_value(
            "AI Email Queue",
            {"email_uid": email_uid},
            fields,
            as_dict=True,
        )
        if existing:
            return existing

    existing = frappe.db.get_value(
        "AI Email Queue",
        {"communication_link": doc.name},
        fields,
        as_dict=True,
    )
    if existing:
        return existing

    duplicate_filters = get_email_duplicate_filters(doc)
    return frappe.db.get_value(
        "AI Email Queue",
        duplicate_filters,
        fields,
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
    existing_queue = get_existing_queue_for_email(communication)
    if existing_queue:
        try:
            existing_extracted = json.loads(
                existing_queue.extracted_json or "{}"
            )
        except Exception:
            existing_extracted = {}
        if existing_extracted.get("items") and existing_extracted.get("documents"):
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

        existing_queue = get_existing_queue_for_email(doc)
        if existing_queue:
            try:
                existing_extracted = json.loads(
                    existing_queue.extracted_json or "{}"
                )
            except Exception:
                existing_extracted = {}
            if existing_extracted.get("items") and existing_extracted.get("documents"):
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
            message_id = get_communication_message_id(doc)
            email_uid = get_communication_email_uid(doc)

            queue_values = {
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
            }

            if ai_email_queue_has_column("message_id"):
                queue_values["message_id"] = message_id
            if ai_email_queue_has_column("email_uid"):
                queue_values["email_uid"] = email_uid

            if existing_queue:
                frappe.db.set_value(
                    "AI Email Queue",
                    existing_queue.name,
                    queue_values,
                    update_modified=True,
                )
            else:
                queue_doc = frappe.get_doc({
                    "doctype": "AI Email Queue",
                    **queue_values,
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
