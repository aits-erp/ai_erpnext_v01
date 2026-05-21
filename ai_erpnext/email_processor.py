import frappe
import json
import os
import pandas as pd


def extract_from_excel(file_path):

    try:

        # CSV SUPPORT
        if file_path.endswith(".csv"):

            try:

                # Try UTF-8 first
                df = pd.read_csv(
                    file_path,
                    encoding="utf-8",
                    sep=None,
                    engine="python"
                )

            except Exception:

                # Fallback encoding
                df = pd.read_csv(
                    file_path,
                    encoding="latin1",
                    sep=None,
                    engine="python"
                )

            df = df.fillna("")

            items = []

            # normalize column names
            cols = {
                str(c).lower().strip(): c
                for c in df.columns
            }

            for _, row in df.iterrows():

                item = {
                    "item_name": "",
                    "item_code": "",
                    "description": "",
                    "qty": 0,
                    "uom": "Nos",
                    "rate": 0,
                    "amount": 0,
                    "hsn_code": "",
                    "tax_rate": 0
                }

                # detect item column
                item["item_name"] = str(
                    row.get(
                        cols.get("item")
                        or cols.get("item_name")
                        or cols.get("description")
                        or cols.get("product"),
                        ""
                    )
                ).strip()

                item["description"] = item["item_name"]

                # qty
                try:

                    item["qty"] = float(
                        row.get(
                            cols.get("qty")
                            or cols.get("quantity"),
                            0
                        ) or 0
                    )

                except Exception:

                    item["qty"] = 0

                # rate
                try:

                    item["rate"] = float(
                        row.get(
                            cols.get("rate")
                            or cols.get("price"),
                            0
                        ) or 0
                    )

                except Exception:

                    item["rate"] = 0

                # amount
                try:

                    item["amount"] = float(
                        row.get(
                            cols.get("amount")
                            or cols.get("total"),
                            0
                        ) or (
                            item["qty"] * item["rate"]
                        )
                    )

                except Exception:

                    item["amount"] = (
                        item["qty"] * item["rate"]
                    )

                # hsn
                item["hsn_code"] = str(
                    row.get(
                        cols.get("hsn")
                        or cols.get("hsn_code"),
                        ""
                    )
                ).strip()

                if item["item_name"]:

                    items.append(item)

            frappe.log_error(
                title="CSV DEBUG",
                message=json.dumps(items[:5], indent=2)
            )

            return {
                "document_type": "Sales Order",
                "customer_name": "",
                "supplier_name": "",
                "document_date": "",
                "document_number": "",
                "due_date": "",
                "items": items,
                "taxes": [],
                "total_before_tax": sum(
                    i["amount"] for i in items
                ),
                "total_tax": 0,
                "grand_total": sum(
                    i["amount"] for i in items
                ),
                "currency": "INR",
                "payment_terms": "",
                "notes": "Extracted from CSV"
            }

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

        if frappe.db.exists(
            "AI Email Queue",
            {"communication_link": doc.name}
        ):
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

                # Try private path if public missing
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

                # PDF
                if ext == "pdf":

                    extracted = extract_from_pdf(file_path)

                # Excel / CSV
                elif ext in ["xlsx", "xls", "csv"]:

                    extracted = extract_from_excel(file_path)

                # Images
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

        # Fallback to email body
        if not extracted and keyword_hits >= 2:

            try:

                from ai_erpnext.claude_helper import (
                    extract_from_email_text
                )

                extracted = extract_from_email_text(
                    doc.content
                )

            except Exception as e:

                extraction_error = str(e)

                frappe.log_error(
                    title="AI Email Body Error",
                    message=str(e)[:5000]
                )

        # Save queue
        try:

            queue_doc = frappe.get_doc({
                "doctype": "AI Email Queue",
                "email_subject": (
                    doc.subject or "(No Subject)"
                )[:140],

                "from_email": (
                    doc.sender or ""
                )[:140],

                "received_on": doc.creation,

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

    queue = frappe.db.get_value(
        "AI Email Queue",
        {"communication_link": doc.name},
        ["name", "extracted_json"],
        as_dict=True
    )

    if not queue:

        process_incoming_email(doc, method)

        return

    try:

        existing = json.loads(
            queue.extracted_json or "{}"
        )

    except Exception:

        existing = {}

    # Only skip if real extraction already exists
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

                extracted = extract_from_pdf(
                    file_path
                )

            elif ext in [
                "xlsx",
                "xls",
                "csv"
            ]:

                extracted = extract_from_excel(
                    file_path
                )

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