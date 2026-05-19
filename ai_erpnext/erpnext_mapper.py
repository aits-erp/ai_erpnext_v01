import frappe
from frappe.utils import today, getdate

def create_document(extracted_data):
    """
    Auto-detects document type and creates the right ERPNext doc
    Returns: (doctype, docname)
    """
    doc_type = extracted_data.get("document_type", "Sales Order")

    routes = {
        "Sales Order":       create_sales_order,
        "Quotation":         create_quotation,
        "Sales Invoice":     create_sales_invoice,
        "Purchase Order":    create_purchase_order,
        "Purchase Invoice":  create_purchase_invoice,
    }

    handler = routes.get(doc_type, create_sales_order)
    doc_name = handler(extracted_data)
    return doc_type, doc_name

# ─── SALES ORDER ───────────────────────────────────────────
def create_sales_order(data):
    customer = _get_or_create_customer(data.get("customer_name") or "Unknown Customer")
    doc = frappe.get_doc({
        "doctype": "Sales Order",
        "customer": customer,
        "transaction_date": _safe_date(data.get("document_date")),
        "delivery_date": _safe_date(data.get("due_date")) or today(),
        "currency": data.get("currency", "INR"),
        "po_no": data.get("document_number", ""),
        "items": _build_items(data.get("items", []), "Sales Order"),
        "taxes": _build_taxes(data.get("taxes", [])),
    })
    doc.insert(ignore_permissions=True)
    return doc.name

# ─── QUOTATION ─────────────────────────────────────────────
def create_quotation(data):
    customer = _get_or_create_customer(data.get("customer_name") or "Unknown Customer")
    doc = frappe.get_doc({
        "doctype": "Quotation",
        "quotation_to": "Customer",
        "party_name": customer,
        "transaction_date": _safe_date(data.get("document_date")),
        "currency": data.get("currency", "INR"),
        "items": _build_items(data.get("items", []), "Quotation"),
        "taxes": _build_taxes(data.get("taxes", [])),
    })
    doc.insert(ignore_permissions=True)
    return doc.name

# ─── SALES INVOICE ─────────────────────────────────────────
def create_sales_invoice(data):
    customer = _get_or_create_customer(data.get("customer_name") or "Unknown Customer")
    doc = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": customer,
        "posting_date": _safe_date(data.get("document_date")),
        "due_date": _safe_date(data.get("due_date")),
        "currency": data.get("currency", "INR"),
        "po_no": data.get("document_number", ""),
        "items": _build_items(data.get("items", []), "Sales Invoice"),
        "taxes": _build_taxes(data.get("taxes", [])),
    })
    doc.insert(ignore_permissions=True)
    return doc.name

# ─── PURCHASE ORDER ────────────────────────────────────────
def create_purchase_order(data):
    supplier = _get_or_create_supplier(data.get("supplier_name") or "Unknown Supplier")
    doc = frappe.get_doc({
        "doctype": "Purchase Order",
        "supplier": supplier,
        "transaction_date": _safe_date(data.get("document_date")),
        "schedule_date": _safe_date(data.get("due_date")) or today(),
        "currency": data.get("currency", "INR"),
        "items": _build_items(data.get("items", []), "Purchase Order"),
        "taxes": _build_taxes(data.get("taxes", [])),
    })
    doc.insert(ignore_permissions=True)
    return doc.name

# ─── PURCHASE INVOICE ──────────────────────────────────────
def create_purchase_invoice(data):
    supplier = _get_or_create_supplier(data.get("supplier_name") or "Unknown Supplier")
    doc = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "supplier": supplier,
        "posting_date": _safe_date(data.get("document_date")),
        "due_date": _safe_date(data.get("due_date")),
        "bill_no": data.get("document_number", ""),
        "currency": data.get("currency", "INR"),
        "items": _build_items(data.get("items", []), "Purchase Invoice"),
        "taxes": _build_taxes(data.get("taxes", [])),
    })
    doc.insert(ignore_permissions=True)
    return doc.name

# ─── HELPERS ───────────────────────────────────────────────
# def _build_items(items, doctype):
#     result = []
#     for i in items:
#         item_code = _get_or_create_item(i.get("item_name", "Unknown Item"))
#         row = {
#             "item_code": item_code,
#             "item_name": i.get("item_name"),
#             "description": i.get("description") or i.get("item_name"),
#             "qty": float(i.get("qty") or 1),
#             "rate": float(i.get("rate") or 0),
#             "uom": i.get("uom") or "Nos",
#             "gst_hsn_code": i.get("hsn_code") or "999999"
#         }
#         if doctype in ["Sales Order", "Purchase Order"]:
#             row["delivery_date"] = today()
#         if doctype == "Purchase Order":
#             row["schedule_date"] = today()
#         result.append(row)
#     return result

def _build_items(items, doctype):
    result = []
    for i in items:
        # Safely convert everything — never trust Claude's types
        try:
            qty = float(i.get("qty") or 1)
        except (TypeError, ValueError):
            qty = 1.0

        try:
            rate = float(i.get("rate") or 0)
        except (TypeError, ValueError):
            rate = 0.0

        item_code = _get_or_create_item(
            i.get("item_name") or "Unknown Item",
            i.get("item_code") or "",
            i.get("hsn_code") or "",
            i.get("uom") or "Nos"
        )

        row = {
            "item_code": item_code,
            "item_name": i.get("item_name") or item_code,
            "description": i.get("description") or i.get("item_name") or item_code,
            "qty": qty,
            "rate": rate,
            "uom": i.get("uom") or "Nos",
        }
        if doctype in ["Sales Order", "Purchase Order"]:
            row["delivery_date"] = today()
        if doctype == "Purchase Order":
            row["schedule_date"] = today()

        result.append(row)
    return result

# CORRECT — replace the whole function
def _get_or_create_item(name, item_code_hint="", hsn_code="", uom="Nos"):
    name = (name or "Unknown Item").strip()

    # Try exact item_code match first
    if item_code_hint and frappe.db.exists("Item", item_code_hint.strip()):
        return item_code_hint.strip()

    # Try matching by item_name
    existing = frappe.db.get_value("Item",
        {"item_name": ["like", f"%{name}%"]}, "name")
    if existing:
        if hsn_code:
            current_hsn = frappe.db.get_value("Item", existing, "gst_hsn_code")
            if not current_hsn:
                frappe.db.set_value("Item", existing, "gst_hsn_code", hsn_code)
        return existing

    # Create new
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": (item_code_hint or name)[:140],
        "item_name": name,
        "item_group": "All Item Groups",
        "is_stock_item": 0,
        "stock_uom": uom or "Nos",
        "gst_hsn_code": hsn_code or ""
    })
    doc.insert(ignore_permissions=True)
    return doc.name

# def _build_taxes(taxes):
#     result = []
#     for t in taxes:
#         result.append({
#             "charge_type": "Actual",
#             "description": t.get("tax_name", "Tax"),
#             "tax_amount": float(t.get("tax_amount") or 0),
#             "account_head": _get_default_tax_account()
#         })
#     return result

def _build_taxes(taxes):
    result = []
    default_account = _get_default_tax_account()
    if not default_account:
        return []  # Skip taxes entirely rather than crash
    for t in taxes:
        tax_amount = float(t.get("tax_amount") or 0)
        if tax_amount == 0:
            continue  # Skip zero-amount tax rows
        result.append({
            "charge_type": "Actual",
            "description": (t.get("tax_name") or "Tax")[:140],
            "tax_amount": tax_amount,
            "account_head": default_account
        })
    return result

def _get_default_tax_account():
    # Adjust to your ERPNext company's tax account
    accounts = frappe.get_all("Account", 
        filters={"account_type": "Tax", "is_group": 0},
        fields=["name"], limit=1
    )
    return accounts[0].name if accounts else ""

def _get_or_create_customer(name):
    if not name or name.strip() == "":
        name = "Unknown Customer"
    name = name.strip()

    # Exact match first
    exact = frappe.db.get_value("Customer", {"customer_name": name}, "name")
    if exact:
        return exact

    # Fuzzy — split name into words, try matching any key word
    words = [w for w in name.split() if len(w) > 3]
    for word in words:
        found = frappe.db.get_value("Customer",
            {"customer_name": ["like", f"%{word}%"]}, "name")
        if found:
            frappe.log_error(f"AI: fuzzy matched '{name}' → '{found}'", "AI Customer Match")
            return found

    # Create new
    doc = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": name,
        "customer_type": "Company"
    })
    doc.insert(ignore_permissions=True)
    frappe.log_error(f"AI: created new customer '{name}'", "AI Customer Match")
    return doc.name


def _get_or_create_supplier(name):
    if not name or name.strip() == "":
        name = "Unknown Supplier"
    name = name.strip()

    exact = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
    if exact:
        return exact

    words = [w for w in name.split() if len(w) > 3]
    for word in words:
        found = frappe.db.get_value("Supplier",
            {"supplier_name": ["like", f"%{word}%"]}, "name")
        if found:
            return found

    doc = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": name,
        "supplier_type": "Company"
    })
    doc.insert(ignore_permissions=True)
    return doc.name

# def _get_or_create_item(name):
#     name = name.strip()
#     if frappe.db.exists("Item", {"item_name": name}):
#         return frappe.db.get_value("Item", {"item_name": name}, "name")
#     existing = frappe.db.get_value("Item",
#         {"item_name": ["like", f"%{name}%"]}, "name")
#     if existing:
#         return existing
#     doc = frappe.get_doc({
#         "doctype": "Item",
#         "item_code": name[:140],
#         "item_name": name,
#         "item_group": "All Item Groups",
#         "is_stock_item": 0,
#         "stock_uom": "Nos",
#         "hsn_code": "hsn"
#     })
#     doc.insert(ignore_permissions=True)
#     return doc.name

def _safe_date(date_str):
    if not date_str:
        return today()
    try:
        return str(getdate(date_str))
    except:
        return today()
    
def make_so_from_quotation(quotation_name):
    quot_doc = frappe.get_doc("Quotation", quotation_name)
    
    # Only submit if in draft
    if quot_doc.docstatus == 0:
        quot_doc.submit()
    elif quot_doc.docstatus == 2:
        frappe.throw(f"Quotation {quotation_name} is cancelled, cannot convert")
    # docstatus==1 means already submitted — that's fine, proceed

    make_sales_order_fn = frappe.get_attr(
        "erpnext.selling.doctype.quotation.quotation.make_sales_order"
    )
    so = make_sales_order_fn(quotation_name)
    so.delivery_date = so.delivery_date or today()
    
    # Ensure all items have delivery_date
    for item in so.items:
        if not item.delivery_date:
            item.delivery_date = today()
    
    so.insert(ignore_permissions=True)
    return so.name


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
    
#     # Handle zero amounts — ERPNext needs explicit flag
#     has_zero = any((item.rate or 0) == 0 for item in si.items)
#     if has_zero:
#         si.is_return = 0
#         for item in si.items:
#             if not item.rate:
#                 item.rate = 0
#                 item.amount = 0
    
#     si.insert(ignore_permissions=True)
#     return si.name

def make_si_from_so(so_name):
    so_doc = frappe.get_doc("Sales Order", so_name)
    if so_doc.docstatus == 0:
        so_doc.submit()
    elif so_doc.docstatus == 2:
        frappe.throw(f"Sales Order {so_name} is cancelled")

    make_sales_invoice_fn = frappe.get_attr(
        "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice"
    )
    si = make_sales_invoice_fn(so_name)  # unsaved doc object

    for item in si.items:
        if not item.rate:
            item.rate = 0
            item.amount = 0

    si.insert(ignore_permissions=True)
    return si.name  # NOW name is set after insert

def make_pi_from_po(po_name):
    po_doc = frappe.get_doc("Purchase Order", po_name)
    
    if po_doc.docstatus == 0:
        po_doc.submit()
    elif po_doc.docstatus == 2:
        frappe.throw(f"Purchase Order {po_name} is cancelled")

    make_purchase_invoice_fn = frappe.get_attr(
        "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice"
    )
    pi = make_purchase_invoice_fn(po_name)
    pi.insert(ignore_permissions=True)
    return pi.name