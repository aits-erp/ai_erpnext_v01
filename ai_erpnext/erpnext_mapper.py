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
def _build_items(items, doctype):
    result = []
    for i in items:
        item_code = _get_or_create_item(i.get("item_name", "Unknown Item"))
        row = {
            "item_code": item_code,
            "item_name": i.get("item_name"),
            "description": i.get("description") or i.get("item_name"),
            "qty": float(i.get("qty") or 1),
            "rate": float(i.get("rate") or 0),
            "uom": i.get("uom") or "Nos",
            "gst_hsn_code": i.get("hsn_code") or "999999"
        }
        if doctype in ["Sales Order", "Purchase Order"]:
            row["delivery_date"] = today()
        if doctype == "Purchase Order":
            row["schedule_date"] = today()
        result.append(row)
    return result

def _build_taxes(taxes):
    result = []
    for t in taxes:
        result.append({
            "charge_type": "Actual",
            "description": t.get("tax_name", "Tax"),
            "tax_amount": float(t.get("tax_amount") or 0),
            "account_head": _get_default_tax_account()
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
    name = name.strip()
    if frappe.db.exists("Customer", {"customer_name": name}):
        return frappe.db.get_value("Customer", {"customer_name": name}, "name")
    existing = frappe.db.get_value("Customer",
        {"customer_name": ["like", f"%{name}%"]}, "name")
    if existing:
        return existing
    doc = frappe.get_doc({"doctype": "Customer", "customer_name": name, "customer_type": "Company"})
    doc.insert(ignore_permissions=True)
    return doc.name

def _get_or_create_supplier(name):
    name = name.strip()
    if frappe.db.exists("Supplier", {"supplier_name": name}):
        return frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
    existing = frappe.db.get_value("Supplier",
        {"supplier_name": ["like", f"%{name}%"]}, "name")
    if existing:
        return existing
    doc = frappe.get_doc({"doctype": "Supplier", "supplier_name": name, "supplier_type": "Company"})
    doc.insert(ignore_permissions=True)
    return doc.name

def _get_or_create_item(name):
    name = name.strip()
    if frappe.db.exists("Item", {"item_name": name}):
        return frappe.db.get_value("Item", {"item_name": name}, "name")
    existing = frappe.db.get_value("Item",
        {"item_name": ["like", f"%{name}%"]}, "name")
    if existing:
        return existing
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": name[:140],
        "item_name": name,
        "item_group": "All Item Groups",
        "is_stock_item": 0,
        "stock_uom": "Nos"
    })
    doc.insert(ignore_permissions=True)
    return doc.name

def _safe_date(date_str):
    if not date_str:
        return today()
    try:
        return str(getdate(date_str))
    except:
        return today()
    
# erpnext_mapper.py — add at bottom

def make_so_from_quotation(quotation_name):
    from erpnext.selling.doctype.quotation.quotation import make_sales_order
    so = make_sales_order(quotation_name)
    so.delivery_date = today()
    so.insert(ignore_permissions=True)
    return so.name

def make_si_from_so(so_name):
    from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
    si = make_sales_invoice(so_name)
    si.insert(ignore_permissions=True)
    return si.name

def make_pi_from_po(po_name):
    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice
    pi = make_purchase_invoice(po_name)
    pi.insert(ignore_permissions=True)
    return pi.name