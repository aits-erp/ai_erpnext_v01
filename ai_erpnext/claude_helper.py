import base64
import json
import os
import frappe

def get_claude_client():
    try:
        import anthropic as _anthropic
    except ImportError:
        frappe.throw("anthropic package missing. Run: bench pip install anthropic")
    
    api_key = (
        os.environ.get("CLAUDE_API_KEY") or
        frappe.conf.get("claude_api_key")
    )
    if not api_key:
        frappe.throw("Claude API key not configured")
    
    return _anthropic.Anthropic(api_key=api_key)

# def get_claude_client():
#     api_key = os.environ.get("CLAUDE_API_KEY") or frappe.conf.get("claude_api_key")
#     if not api_key:
#         frappe.throw("Claude API key not configured")
#     return anthropic.Anthropic(api_key=api_key)

EXTRACTION_PROMPT = """
You are a document data extractor. Extract ALL details from this document.
Return ONLY valid JSON — no explanation, no markdown.

{
  "document_type": "Sales Order or Purchase Order or Sales Invoice or Purchase Invoice or Quotation",
  "customer_name": "",
  "supplier_name": "",
  "document_date": "YYYY-MM-DD",
  "document_number": "",
  "due_date": "YYYY-MM-DD",
  "items": [
    {
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
  ],
  "taxes": [
    {
      "tax_name": "",
      "tax_amount": 0,
      "tax_rate": 0
    }
  ],
  "total_before_tax": 0,
  "total_tax": 0,
  "grand_total": 0,
  "currency": "INR",
  "payment_terms": "",
  "notes": ""
}

Rules:
- Extract HSN/SAC code for every item — look in HSN column or HSN/SAC table at bottom of doc
- If one HSN code applies to all items, use it for all
- If item_code present in doc, use it, else leave empty
- tax_rate = total GST % (CGST+SGST combined, e.g. 12 if 6+6)
- Return ONLY the JSON object
"""

def extract_from_pdf(file_path):
    client = get_claude_client()
    with open(file_path, "rb") as f:
        pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_data}
                },
                {"type": "text", "text": EXTRACTION_PROMPT}
            ]
        }]
    )
    return _parse_claude_response(message.content[0].text)

def extract_from_image(file_path, mime_type="image/jpeg"):
    client = get_claude_client()
    with open(file_path, "rb") as f:
        img_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": mime_type, "data": img_data}
                },
                {"type": "text", "text": EXTRACTION_PROMPT}
            ]
        }]
    )
    return _parse_claude_response(message.content[0].text)

def extract_from_email_text(email_body):
    client = get_claude_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"{EXTRACTION_PROMPT}\n\nEMAIL CONTENT:\n{email_body[:4000]}"
        }]
    )
    return _parse_claude_response(message.content[0].text)

def _parse_claude_response(text):
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break
    return json.loads(text)