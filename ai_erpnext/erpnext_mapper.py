# import frappe
# from frappe.utils import today, getdate

# def create_document(extracted_data):
#     """
#     Auto-detects document type and creates the right ERPNext doc
#     Returns: (doctype, docname)
#     """
#     doc_type = extracted_data.get("document_type", "Sales Order")

#     routes = {
#         "Sales Order":       create_sales_order,
#         "Quotation":         create_quotation,
#         "Sales Invoice":     create_sales_invoice,
#         "Purchase Order":    create_purchase_order,
#         "Purchase Invoice":  create_purchase_invoice,
#     }

#     handler = routes.get(doc_type, create_sales_order)
#     doc_name = handler(extracted_data)
#     return doc_type, doc_name

# # ─── SALES ORDER ───────────────────────────────────────────
# def create_sales_order(data):
#     customer_name = (
#         data.get("customer")
#         or data.get("customer_name")
#         or data.get("party")
#     )
#     if not customer_name:
#         frappe.throw("Customer missing in CSV data")
#     customer = _get_or_create_customer(customer_name)

#     doc = frappe.get_doc({
#         "doctype": "Sales Order",
#         "customer": customer,
#         "transaction_date": _safe_date(data.get("document_date")),
#         "delivery_date": _safe_date(data.get("due_date")) or today(),
#         "currency": data.get("currency", "INR"),
#         "po_no": data.get("document_number", ""),
#         "items": _build_items(data.get("items", []), "Sales Order"),
#         "taxes": _build_taxes(data.get("taxes", [])),
#     })
#     doc.insert(ignore_permissions=True)
#     return doc.name

# # ─── QUOTATION ─────────────────────────────────────────────
# def create_quotation(data):
#     customer_name = (
#         data.get("customer")
#         or data.get("customer_name")
#         or data.get("party")
#     )
#     if not customer_name:
#         frappe.throw("Customer missing in CSV data")
#     customer = _get_or_create_customer(customer_name)

#     doc = frappe.get_doc({
#         "doctype": "Quotation",
#         "quotation_to": "Customer",
#         "party_name": customer,
#         "transaction_date": _safe_date(data.get("document_date")),
#         "currency": data.get("currency", "INR"),
#         "items": _build_items(data.get("items", []), "Quotation"),
#         "taxes": _build_taxes(data.get("taxes", [])),
#     })
#     doc.insert(ignore_permissions=True)
#     return doc.name

# # ─── SALES INVOICE ─────────────────────────────────────────
# def create_sales_invoice(data):
#     customer_name = (
#         data.get("customer")
#         or data.get("customer_name")
#         or data.get("party")
#     )
#     if not customer_name:
#         frappe.throw("Customer missing in CSV data")
#     customer = _get_or_create_customer(customer_name)

#     doc = frappe.get_doc({
#         "doctype": "Sales Invoice",
#         "customer": customer,
#         "posting_date": _safe_date(data.get("document_date")),
#         "due_date": _safe_date(data.get("due_date")),
#         "currency": data.get("currency", "INR"),
#         "po_no": data.get("document_number", ""),
#         "items": _build_items(data.get("items", []), "Sales Invoice"),
#         "taxes": _build_taxes(data.get("taxes", [])),
#     })
#     doc.insert(ignore_permissions=True)
#     return doc.name

# # ─── PURCHASE ORDER ────────────────────────────────────────
# def create_purchase_order(data):
#     supplier = _get_or_create_supplier(data.get("supplier_name") or "Unknown Supplier")
#     doc = frappe.get_doc({
#         "doctype": "Purchase Order",
#         "supplier": supplier,
#         "transaction_date": _safe_date(data.get("document_date")),
#         "schedule_date": _safe_date(data.get("due_date")) or today(),
#         "currency": data.get("currency", "INR"),
#         "items": _build_items(data.get("items", []), "Purchase Order"),
#         "taxes": _build_taxes(data.get("taxes", [])),
#     })
#     doc.insert(ignore_permissions=True)
#     return doc.name

# # ─── PURCHASE INVOICE ──────────────────────────────────────
# def create_purchase_invoice(data):
#     supplier = _get_or_create_supplier(data.get("supplier_name") or "Unknown Supplier")
#     doc = frappe.get_doc({
#         "doctype": "Purchase Invoice",
#         "supplier": supplier,
#         "posting_date": _safe_date(data.get("document_date")),
#         "due_date": _safe_date(data.get("due_date")),
#         "bill_no": data.get("document_number", ""),
#         "currency": data.get("currency", "INR"),
#         "items": _build_items(data.get("items", []), "Purchase Invoice"),
#         "taxes": _build_taxes(data.get("taxes", [])),
#     })
#     doc.insert(ignore_permissions=True)
#     return doc.name

# # ─── HELPERS ───────────────────────────────────────────────
# DEFAULT_HSN_CODE = "999999"
# GST_DOCTYPES_WITH_HSN = {
#     "Sales Invoice",
#     "Purchase Invoice",
#     "Sales Order",
#     "Purchase Order",
#     "Quotation",
# }


# def _build_items(items, doctype):
#     result = []
#     for i in items:
#         try:
#             qty = float(i.get("qty") or 1)
#         except (TypeError, ValueError):
#             qty = 1.0

#         try:
#             rate = float(i.get("rate") or 0)
#         except (TypeError, ValueError):
#             rate = 0.0

#         hsn_code = _get_valid_hsn_code(i.get("hsn_code"), doctype)
#         item_code = _get_or_create_item(
#             i.get("item_name") or "Unknown Item",
#             i.get("item_code") or "",
#             hsn_code,
#             i.get("uom") or "Nos",
#             doctype
#         )
#         if rate <= 0:
#             rate = _get_item_rate(item_code) or 0.0
#         amount = qty * rate

#         row = {
#             "item_code": item_code,
#             "item_name": i.get("item_name") or item_code,
#             "description": i.get("description") or i.get("item_name") or item_code,
#             "qty": qty,
#             "rate": rate,
#             "uom": i.get("uom") or "Nos",
#         }
#         if hsn_code:
#             row["gst_hsn_code"] = hsn_code
#         if doctype in ["Sales Order", "Purchase Order"]:
#             row["delivery_date"] = _safe_date(i.get("delivery_date")) or today()
#         if doctype == "Purchase Order":
#             row["schedule_date"] = _safe_date(i.get("schedule_date") or i.get("delivery_date")) or today()

#         result.append(row)
#     return result


# def _get_item_rate(item_code):
#     try:
#         rate = frappe.db.get_value(
#             "Item Price",
#             {
#                 "item_code": item_code,
#                 "selling": 1,
#             },
#             "price_list_rate",
#             order_by="modified desc",
#         )
#         return float(rate or 0)
#     except Exception:
#         return 0.0


# def _get_or_create_item(name, item_code_hint="", hsn_code="", uom="Nos", doctype=""):
#     name = (name or "Unknown Item").strip()
#     hsn_code = _get_valid_hsn_code(hsn_code, doctype)
#     hsn_required = doctype in GST_DOCTYPES_WITH_HSN

#     if item_code_hint and frappe.db.exists("Item", item_code_hint.strip()):
#         existing = item_code_hint.strip()
#         current_hsn = frappe.db.get_value("Item", existing, "gst_hsn_code")
#         if current_hsn and not _hsn_exists(current_hsn):
#             frappe.db.set_value("Item", existing, "gst_hsn_code", "")
#             current_hsn = ""
#         if hsn_required and hsn_code and not current_hsn:
#             frappe.db.set_value("Item", existing, "gst_hsn_code", hsn_code)
#         return existing

#     existing = frappe.db.get_value("Item",
#         {"item_name": ["like", f"%{name}%"]}, "name")
#     if existing:
#         current_hsn = frappe.db.get_value("Item", existing, "gst_hsn_code")
#         if current_hsn and not _hsn_exists(current_hsn):
#             frappe.db.set_value("Item", existing, "gst_hsn_code", "")
#             current_hsn = ""
#         if hsn_required and hsn_code and not current_hsn:
#             frappe.db.set_value("Item", existing, "gst_hsn_code", hsn_code)
#         return existing

#     valuation_method = _get_default_valuation_method()
#     item_values = {
#         "doctype": "Item",
#         "item_code": (item_code_hint or name)[:140],
#         "item_name": name,
#         "item_group": "All Item Groups",
#         "is_stock_item": 0,
#         "is_sales_item": 1,
#         "is_purchase_item": 1,
#         "stock_uom": uom or "Nos",
#         "valuation_method": valuation_method,
#     }
#     if hsn_required and hsn_code:
#         item_values["gst_hsn_code"] = hsn_code

#     doc = frappe.get_doc(item_values)
#     if doc.meta.has_field("valuation_method") and not doc.valuation_method:
#         doc.valuation_method = valuation_method or "FIFO"
#     doc.insert(ignore_permissions=True)
#     if not hsn_required:
#         frappe.db.set_value(
#             "Item",
#             doc.name,
#             {"is_sales_item": 1, "is_purchase_item": 1},
#             update_modified=False,
#         )
#     return doc.name


# def _get_valid_hsn_code(hsn_code, doctype=""):
#     hsn_code = "".join(ch for ch in str(hsn_code or "") if ch.isdigit())
#     if len(hsn_code) not in {4, 6, 8}:
#         hsn_code = DEFAULT_HSN_CODE

#     if _ensure_hsn_code(hsn_code):
#         return hsn_code

#     existing_hsn = _get_existing_hsn_code()
#     if existing_hsn:
#         return existing_hsn

#     if doctype in ["Sales Order", "Purchase Order", "Quotation"]:
#         return ""

#     return hsn_code if _hsn_exists(hsn_code) else ""


# def _hsn_exists(hsn_code):
#     if not hsn_code:
#         return False
#     try:
#         if not frappe.db.exists("DocType", "GST HSN Code"):
#             return False
#         return bool(
#             frappe.db.exists("GST HSN Code", hsn_code)
#             or frappe.db.get_value("GST HSN Code", {"hsn_code": hsn_code}, "name")
#         )
#     except Exception:
#         return False


# def _ensure_hsn_code(hsn_code):
#     if not hsn_code:
#         return False
#     if _hsn_exists(hsn_code):
#         return True
#     try:
#         if not frappe.db.exists("DocType", "GST HSN Code"):
#             return False

#         meta = frappe.get_meta("GST HSN Code")
#         values = {"doctype": "GST HSN Code"}
#         if meta.has_field("hsn_code"):
#             values["hsn_code"] = hsn_code
#         if meta.has_field("gst_hsn_code"):
#             values["gst_hsn_code"] = hsn_code
#         if meta.has_field("description"):
#             values["description"] = "Other"

#         doc = frappe.get_doc(values)
#         if getattr(doc.meta, "autoname", "") == "Prompt":
#             doc.name = hsn_code
#         doc.insert(ignore_permissions=True)
#         return _hsn_exists(hsn_code)
#     except Exception:
#         frappe.log_error(
#             title="AI HSN Code Create Error",
#             message=frappe.get_traceback(),
#         )
#         return False


# def _get_existing_hsn_code():
#     try:
#         if not frappe.db.exists("DocType", "GST HSN Code"):
#             return ""
#         rows = frappe.get_all(
#             "GST HSN Code",
#             fields=["name", "hsn_code"],
#             limit=1,
#             order_by="modified desc",
#         )
#         if not rows:
#             return ""
#         return rows[0].get("hsn_code") or rows[0].get("name") or ""
#     except Exception:
#         return ""


# def _get_default_valuation_method():
#     try:
#         value = frappe.db.get_single_value("Stock Settings", "valuation_method")
#         return value if value in {"FIFO", "Moving Average", "LIFO"} else "FIFO"
#     except Exception:
#         return "FIFO"


# def _build_taxes(taxes):
#     result = []
#     default_account = _get_default_tax_account()
#     if not default_account:
#         return []
#     for t in taxes:
#         tax_amount = float(t.get("tax_amount") or 0)
#         if tax_amount == 0:
#             continue
#         result.append({
#             "charge_type": "Actual",
#             "description": (t.get("tax_name") or "Tax")[:140],
#             "tax_amount": tax_amount,
#             "account_head": default_account
#         })
#     return result


# def _get_default_tax_account():
#     accounts = frappe.get_all("Account",
#         filters={"account_type": "Tax", "is_group": 0},
#         fields=["name"], limit=1
#     )
#     return accounts[0].name if accounts else ""


# def _get_or_create_customer(name):
#     if not name or name.strip() == "":
#         frappe.throw("Customer not found in extracted CSV data")
#     name = name.strip()

#     if frappe.db.exists("Customer", name):
#         return name

#     exact = frappe.db.get_value("Customer", {"customer_name": name}, "name")
#     if exact:
#         return exact

#     words = [w for w in name.split() if len(w) > 3]
#     for word in words:
#         found = frappe.db.get_value("Customer",
#             {"customer_name": ["like", f"%{word}%"]}, "name")
#         if found:
#             frappe.log_error(f"AI: fuzzy matched '{name}' → '{found}'", "AI Customer Match")
#             return found

#     doc = frappe.get_doc({
#         "doctype": "Customer",
#         "customer_name": name,
#         "customer_type": "Company"
#     })
#     doc.insert(ignore_permissions=True)
#     frappe.log_error(f"AI: created new customer '{name}'", "AI Customer Match")
#     return doc.name


# def _get_or_create_supplier(name):
#     if not name or name.strip() == "":
#         name = "Unknown Supplier"
#     name = name.strip()

#     if frappe.db.exists("Supplier", name):
#         return name

#     exact = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
#     if exact:
#         return exact

#     words = [w for w in name.split() if len(w) > 3]
#     for word in words:
#         found = frappe.db.get_value("Supplier",
#             {"supplier_name": ["like", f"%{word}%"]}, "name")
#         if found:
#             return found

#     doc = frappe.get_doc({
#         "doctype": "Supplier",
#         "supplier_name": name,
#         "supplier_type": "Company"
#     })
#     doc.insert(ignore_permissions=True)
#     return doc.name


# def _safe_date(date_str):
#     if not date_str:
#         return today()
#     try:
#         return str(getdate(date_str))
#     except:
#         return today()


# def make_so_from_quotation(quotation_name):
#     quot_doc = frappe.get_doc("Quotation", quotation_name)

#     if quot_doc.docstatus == 0:
#         quot_doc.submit()
#     elif quot_doc.docstatus == 2:
#         frappe.throw(f"Quotation {quotation_name} is cancelled, cannot convert")

#     make_sales_order_fn = frappe.get_attr(
#         "erpnext.selling.doctype.quotation.quotation.make_sales_order"
#     )
#     so = make_sales_order_fn(quotation_name)
#     so.delivery_date = so.delivery_date or today()

#     for item in so.items:
#         if not item.delivery_date:
#             item.delivery_date = today()

#     so.insert(ignore_permissions=True)
#     return so.name


# def make_si_from_so(so_name):
#     so_doc = frappe.get_doc("Sales Order", so_name)
#     if so_doc.docstatus == 0:
#         so_doc.submit()
#     elif so_doc.docstatus == 2:
#         frappe.throw(f"Sales Order {so_name} is cancelled")

#     make_sales_invoice_fn = frappe.get_attr(
#         "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice"
#     )
#     si = make_sales_invoice_fn(so_name)

#     for item in si.items:
#         if not item.rate:
#             item.rate = 0
#             item.amount = 0

#     si.insert(ignore_permissions=True)
#     return si.name


# def make_pi_from_po(po_name):
#     po_doc = frappe.get_doc("Purchase Order", po_name)

#     if po_doc.docstatus == 0:
#         po_doc.submit()
#     elif po_doc.docstatus == 2:
#         frappe.throw(f"Purchase Order {po_name} is cancelled")

#     make_purchase_invoice_fn = frappe.get_attr(
#         "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice"
#     )
#     pi = make_purchase_invoice_fn(po_name)
#     pi.insert(ignore_permissions=True)
#     return pi.name

import frappe
from frappe.utils import today, getdate


def _get_default_company_code():
    """Fall back to the site's default Company when a row doesn't carry
    its own COMPANY_CODE from the sheet/email."""
    try:
        company = frappe.defaults.get_global_default("company")
        return company or ""
    except Exception:
        return ""


# ─── BILL OF MATERIALS ──────────────────────────────────────
# This mirrors the same "parent + child rows" shape your extractor already
# builds for Sales Order etc., so extract_documents_from_rows() in
# email_processor.py can feed this directly once a sheet has a real
# parent-item / component relationship.
def create_bom(data):
    parent_item_name = (
        data.get("item")
        or data.get("item_name")
        or data.get("parent_item")
        or data.get("finished_item")
    )
    if not parent_item_name:
        frappe.throw("Parent/Finished Item missing in BOM data")

    default_company_code = _get_default_company_code()

    parent_item_code = _get_or_create_item(
        name=parent_item_name,
        item_code_hint=data.get("item_code") or "",
        hsn_code="",
        uom=data.get("uom") or "Nos",
        doctype="Bill of Materials",
        company_code=data.get("company_code") or default_company_code,
        material_usage_code=data.get("material_usage_code") or "",
        item_group=data.get("material_group") or data.get("item_group") or "",
        subgroup=data.get("material_subgroup") or "",
        subsubgroup=data.get("material_subsubgroup") or "",
    )

    components = data.get("items", [])
    if not components:
        frappe.throw("No component/raw material rows found for BOM")

    bom_items = []
    for c in components:
        try:
            qty = float(c.get("qty") or 1)
        except (TypeError, ValueError):
            qty = 1.0
        try:
            rate = float(c.get("rate") or 0)
        except (TypeError, ValueError):
            rate = 0.0
        try:
            conversion_factor = float(c.get("conversion_factor") or 1)
        except (TypeError, ValueError):
            conversion_factor = 1.0

        component_company_code = c.get("company_code") or data.get("company_code") or default_company_code

        component_code = _get_or_create_item(
            name=c.get("item_name") or "Unknown Component",
            item_code_hint=c.get("item_code") or "",
            hsn_code=c.get("hsn_code") or "",
            uom=c.get("uom") or c.get("stocking_uom_code") or "Nos",
            doctype="Bill of Materials",
            company_code=component_company_code,
            material_usage_code=c.get("material_usage_code") or "",
            item_group=c.get("material_group") or "",
            subgroup=c.get("material_subgroup") or "",
            subsubgroup=c.get("material_subsubgroup") or "",
            purchase_uom_code=c.get("purchase_uom") or c.get("purchase_uom_code") or "",
            conversion_factor=conversion_factor,
        )

        row = {
            "item_code": component_code,
            "qty": qty,
            "uom": c.get("uom") or c.get("stocking_uom_code") or "Nos",
        }
        if rate > 0:
            row["rate"] = rate

        # ── Custom fields — mirror what _get_or_create_item wrote onto the Item ──
        bom_item_meta = frappe.get_meta("BOM Item")
        material_group = c.get("material_group") or ""
        subgroup = c.get("material_subgroup") or ""
        subsubgroup = c.get("material_subsubgroup") or ""
        purchase_uom = c.get("purchase_uom") or c.get("purchase_uom_code") or ""
        hsn = c.get("hsn_code") or ""
        material_usage_code = c.get("material_usage_code") or ""

        if component_company_code and bom_item_meta.has_field("custom_company_code"):
            row["custom_company_code"] = component_company_code
        if material_usage_code and bom_item_meta.has_field("custom_material_usage_code"):
            row["custom_material_usage_code"] = material_usage_code
        if material_group and bom_item_meta.has_field("custom_material_group"):
            row["custom_material_group"] = material_group
        if subgroup and bom_item_meta.has_field("custom_material_subgroup"):
            row["custom_material_subgroup"] = subgroup
        if subsubgroup and bom_item_meta.has_field("custom_material_subsubgroup"):
            row["custom_material_subsubgroup"] = subsubgroup
        if purchase_uom and bom_item_meta.has_field("custom_purchase_uom_code"):
            row["custom_purchase_uom_code"] = purchase_uom
        if hsn and bom_item_meta.has_field("custom_hsn_code"):
            row["custom_hsn_code"] = hsn
        if conversion_factor and bom_item_meta.has_field("custom_conversion_factor"):
            row["custom_conversion_factor"] = conversion_factor

        bom_items.append(row)

    try:
        quantity = float(data.get("quantity") or 1)
    except (TypeError, ValueError):
        quantity = 1.0

    doc = frappe.get_doc({
        "doctype": "BOM",
        "item": parent_item_code,
        "quantity": quantity,
        "uom": data.get("uom") or "Nos",
        "items": bom_items,
        "with_operations": 0,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


# ─── ITEM MASTER (bulk) ────────────────────────────────────
# For flat master sheets like the client's Tools_Master_Sheet.xlsx, where
# every row is an independent Item with no component/quantity relationship
# to any other row. This just creates/updates Items, it does NOT create a
# BOM (there's nothing to relate rows to). Returns a summary string.
def create_items_from_master(data):
    rows = data.get("items", [])
    if not rows:
        frappe.throw("No rows found to create Items from")

    default_company_code = _get_default_company_code()

    created, updated, skipped = [], [], []

    for r in rows:
        name = (r.get("item_name") or r.get("material_desc") or "").strip()
        if not name:
            skipped.append(r)
            continue

        item_group = _get_or_create_item_group(
            r.get("item_group") or r.get("material_group") or "Products"
        )

        uom = r.get("uom") or r.get("stocking_uom_code") or "Nos"
        purchase_uom = r.get("purchase_uom") or r.get("purchase_uom_code") or uom
        conversion_factor = r.get("conversion_factor") or 1
        hsn_code = _get_valid_hsn_code(r.get("hsn_code"), "Item Master")
        company_code = r.get("company_code") or default_company_code

        item_code_hint = r.get("item_code") or ""

        if item_code_hint and frappe.db.exists("Item", item_code_hint.strip()):
            updated.append(item_code_hint.strip())
            continue

        existing = frappe.db.get_value("Item", {"item_name": name}, "name")
        if existing:
            updated.append(existing)
            continue

        item_values = {
            "doctype": "Item",
            "item_code": (item_code_hint or name)[:140],
            "item_name": name,
            "item_group": item_group,
            "is_stock_item": 1,
            "is_sales_item": 1,
            "is_purchase_item": 1,
            "stock_uom": uom,
            "purchase_uom": purchase_uom,
            "valuation_method": _get_default_valuation_method(),
        }
        if hsn_code:
            item_values["gst_hsn_code"] = hsn_code

        # ── Custom fields from the material master sheet ──
        meta = frappe.get_meta("Item")
        if company_code and meta.has_field("custom_company_code"):
            item_values["custom_company_code"] = company_code
        if r.get("material_usage_code") and meta.has_field("custom_material_usage_code"):
            item_values["custom_material_usage_code"] = r.get("material_usage_code")
        if r.get("material_subgroup") and meta.has_field("custom_material_subgroup"):
            item_values["custom_material_subgroup"] = r.get("material_subgroup")
        if r.get("material_subsubgroup") and meta.has_field("custom_material_subsubgroup"):
            item_values["custom_material_subsubgroup"] = r.get("material_subsubgroup")
        if purchase_uom and meta.has_field("custom_purchase_uom_code"):
            item_values["custom_purchase_uom_code"] = purchase_uom

        doc = frappe.get_doc(item_values)
        doc.insert(ignore_permissions=True)

        # add a UOM conversion row if purchase UOM differs from stock UOM
        if purchase_uom and purchase_uom != uom and float(conversion_factor or 1) != 1:
            try:
                doc.append("uoms", {
                    "uom": purchase_uom,
                    "conversion_factor": float(conversion_factor),
                })
                doc.save(ignore_permissions=True)
            except Exception:
                frappe.log_error(
                    title="Item Master UOM Conversion Error",
                    message=frappe.get_traceback(),
                )

        created.append(doc.name)

    frappe.db.commit()
    return f"Created: {len(created)}, Already existed: {len(updated)}, Skipped: {len(skipped)}"


def _get_or_create_item_group(name):
    name = (name or "Products").strip().title()
    if frappe.db.exists("Item Group", name):
        return name
    doc = frappe.get_doc({
        "doctype": "Item Group",
        "item_group_name": name,
        "parent_item_group": "All Item Groups",
        "is_group": 0,
    })
    try:
        doc.insert(ignore_permissions=True)
        return doc.name
    except Exception:
        return "All Item Groups"


def _get_or_create_uom(uom_name):
    uom_name = (uom_name or "Nos").strip()
    if not uom_name:
        uom_name = "Nos"
    if frappe.db.exists("UOM", uom_name):
        return uom_name
    try:
        doc = frappe.get_doc({
            "doctype": "UOM",
            "uom_name": uom_name,
            "must_be_whole_number": 1,
        })
        doc.insert(ignore_permissions=True)
        return doc.name
    except Exception:
        frappe.log_error(title="UOM Auto-create Error", message=frappe.get_traceback())
        return "Nos"


# ─── HELPERS ───────────────────────────────────────────────
DEFAULT_HSN_CODE = "999999"
GST_DOCTYPES_WITH_HSN = {
    "Sales Invoice",
    "Purchase Invoice",
    "Sales Order",
    "Purchase Order",
    "Quotation",
    "Bill of Materials",
    "Item Master",
}


def _get_item_rate(item_code):
    try:
        rate = frappe.db.get_value(
            "Item Price",
            {
                "item_code": item_code,
                "selling": 1,
            },
            "price_list_rate",
            order_by="modified desc",
        )
        return float(rate or 0)
    except Exception:
        return 0.0


def _get_or_create_item(name, item_code_hint="", hsn_code="", uom="Nos", doctype="",
                         company_code="", material_usage_code="",
                         item_group="", subgroup="", subsubgroup="",
                         purchase_uom_code="", conversion_factor=1):
    name = (name or "Unknown Item").strip()
    hsn_code = _get_valid_hsn_code(hsn_code, doctype)
    hsn_required = doctype in GST_DOCTYPES_WITH_HSN

    resolved_group = _get_or_create_item_group(subsubgroup or subgroup or item_group or "Products")

    if item_code_hint and frappe.db.exists("Item", item_code_hint.strip()):
        existing = item_code_hint.strip()
        current_hsn = frappe.db.get_value("Item", existing, "gst_hsn_code")
        if current_hsn and not _hsn_exists(current_hsn):
            frappe.db.set_value("Item", existing, "gst_hsn_code", "")
            current_hsn = ""
        if hsn_required and hsn_code and not current_hsn:
            frappe.db.set_value("Item", existing, "gst_hsn_code", hsn_code)
        return existing

    existing = frappe.db.get_value("Item",
        {"item_name": ["like", f"%{name}%"]}, "name")
    if existing:
        current_hsn = frappe.db.get_value("Item", existing, "gst_hsn_code")
        if current_hsn and not _hsn_exists(current_hsn):
            frappe.db.set_value("Item", existing, "gst_hsn_code", "")
            current_hsn = ""
        if hsn_required and hsn_code and not current_hsn:
            frappe.db.set_value("Item", existing, "gst_hsn_code", hsn_code)
        return existing

    valuation_method = _get_default_valuation_method()
    item_values = {
        "doctype": "Item",
        "item_code": (item_code_hint or name)[:140],
        "item_name": name,
        "item_group": resolved_group,
        "is_stock_item": 1,
        "is_sales_item": 1,
        "is_purchase_item": 1,
        "stock_uom": _get_or_create_uom(uom),
        "valuation_method": valuation_method,
    }
    if hsn_required and hsn_code:
        item_values["gst_hsn_code"] = hsn_code

    # ── Custom fields from the material master sheet ──
    meta = frappe.get_meta("Item")
    if company_code and meta.has_field("custom_company_code"):
        item_values["custom_company_code"] = company_code
    if material_usage_code and meta.has_field("custom_material_usage_code"):
        item_values["custom_material_usage_code"] = material_usage_code
    if subgroup and meta.has_field("custom_material_subgroup"):
        item_values["custom_material_subgroup"] = subgroup
    if subsubgroup and meta.has_field("custom_material_subsubgroup"):
        item_values["custom_material_subsubgroup"] = subsubgroup
    if purchase_uom_code and meta.has_field("custom_purchase_uom_code"):
        item_values["custom_purchase_uom_code"] = purchase_uom_code

    doc = frappe.get_doc(item_values)
    if doc.meta.has_field("valuation_method") and not doc.valuation_method:
        doc.valuation_method = valuation_method or "FIFO"
    doc.insert(ignore_permissions=True)

    # Purchase UOM conversion row, if it differs from stock UOM
    if purchase_uom_code and purchase_uom_code != (uom or "Nos") and float(conversion_factor or 1) != 1:
        try:
            resolved_purchase_uom = _get_or_create_uom(purchase_uom_code)
            doc.purchase_uom = resolved_purchase_uom
            doc.append("uoms", {
                "uom": resolved_purchase_uom,
                "conversion_factor": float(conversion_factor),
            })
            doc.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(title="BOM Component UOM Conversion Error", message=frappe.get_traceback())

    if not hsn_required:
        frappe.db.set_value(
            "Item",
            doc.name,
            {"is_sales_item": 1, "is_purchase_item": 1},
            update_modified=False,
        )
    return doc.name


def _get_valid_hsn_code(hsn_code, doctype=""):
    hsn_code = "".join(ch for ch in str(hsn_code or "") if ch.isdigit())
    if len(hsn_code) not in {4, 6, 8}:
        hsn_code = DEFAULT_HSN_CODE

    if _ensure_hsn_code(hsn_code):
        return hsn_code

    existing_hsn = _get_existing_hsn_code()
    if existing_hsn:
        return existing_hsn

    if doctype in ["Sales Order", "Purchase Order", "Quotation", "Bill of Materials", "Item Master"]:
        return ""

    return hsn_code if _hsn_exists(hsn_code) else ""


def _hsn_exists(hsn_code):
    if not hsn_code:
        return False
    try:
        if not frappe.db.exists("DocType", "GST HSN Code"):
            return False
        return bool(
            frappe.db.exists("GST HSN Code", hsn_code)
            or frappe.db.get_value("GST HSN Code", {"hsn_code": hsn_code}, "name")
        )
    except Exception:
        return False


def _ensure_hsn_code(hsn_code):
    if not hsn_code:
        return False
    if _hsn_exists(hsn_code):
        return True
    try:
        if not frappe.db.exists("DocType", "GST HSN Code"):
            return False

        meta = frappe.get_meta("GST HSN Code")
        values = {"doctype": "GST HSN Code"}
        if meta.has_field("hsn_code"):
            values["hsn_code"] = hsn_code
        if meta.has_field("gst_hsn_code"):
            values["gst_hsn_code"] = hsn_code
        if meta.has_field("description"):
            values["description"] = "Other"

        doc = frappe.get_doc(values)
        if getattr(doc.meta, "autoname", "") == "Prompt":
            doc.name = hsn_code
        doc.insert(ignore_permissions=True)
        return _hsn_exists(hsn_code)
    except Exception:
        frappe.log_error(
            title="AI HSN Code Create Error",
            message=frappe.get_traceback(),
        )
        return False


def _get_existing_hsn_code():
    try:
        if not frappe.db.exists("DocType", "GST HSN Code"):
            return ""
        rows = frappe.get_all(
            "GST HSN Code",
            fields=["name", "hsn_code"],
            limit=1,
            order_by="modified desc",
        )
        if not rows:
            return ""
        return rows[0].get("hsn_code") or rows[0].get("name") or ""
    except Exception:
        return ""


def _get_default_valuation_method():
    try:
        value = frappe.db.get_single_value("Stock Settings", "valuation_method")
        return value if value in {"FIFO", "Moving Average", "LIFO"} else "FIFO"
    except Exception:
        return "FIFO"


def _safe_date(date_str):
    if not date_str:
        return today()
    try:
        return str(getdate(date_str))
    except:
        return today()