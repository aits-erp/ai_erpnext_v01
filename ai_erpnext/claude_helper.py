import base64
import json
import os
import frappe


# Separate constants
REQUEST_MAX_TOKENS = 4000
TOTAL_USAGE_LIMIT = 500000


def get_ai_settings():

    settings = frappe.get_single("Api Controller")

    return {
        "api_key": settings.get_password("api_key"),
        "status": settings.status,
        "model": settings.model_name_version or "claude-sonnet-4-6",
        "tokens_used": settings.tokens_used or 0
    }


def update_token_usage(message):

    try:

        used = (
            message.usage.input_tokens +
            message.usage.output_tokens
        )

        current = frappe.db.get_value(
            "Api Controller",
            "Api Controller",
            "tokens_used"
        ) or 0

        new_total = current + used

        frappe.db.set_value(
            "Api Controller",
            "Api Controller",
            "tokens_used",
            new_total
        )

        # Optional safety limit
        if new_total >= TOTAL_USAGE_LIMIT:

            frappe.db.set_value(
                "Api Controller",
                "Api Controller",
                "status",
                "Disabled"
            )

        frappe.db.commit()

    except Exception:

        pass


def get_claude_client():

    try:

        import anthropic as _anthropic

    except ImportError:

        frappe.throw(
            "anthropic package missing. Run: bench pip install anthropic"
        )

    settings = get_ai_settings()

    if settings["status"] == "Disabled":

        frappe.throw("AI service is currently disabled")

    api_key = settings["api_key"]

    if not api_key:

        frappe.throw("Claude API key not configured")

    return _anthropic.Anthropic(api_key=api_key)


EXTRACTION_PROMPT = """
You are an ERP document extraction engine.

Your job is to extract structured business document data from:
- PDFs
- Images
- CSV tables
- Email body text

Return ONLY valid JSON.

IMPORTANT:
- ALWAYS detect tabular line items
- NEVER leave items empty if table rows exist
- For CSVs/spreadsheets:
  - Every business row should become one item
  - Detect columns like:
    item, description, qty, quantity, rate, amount, total, price, gst, hsn
- Ignore blank rows
- Ignore summary rows unless totals
- If document type unclear, infer best match

Return format:

{
  "document_type": "",
  "customer_name": "",
  "supplier_name": "",
  "document_date": "",
  "document_number": "",
  "due_date": "",

  "items": [
    {
      "item_name": "",
      "item_code": "",
      "description": "",
      "qty": 0,
      "uom": "",
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

CRITICAL RULES:
- ALWAYS extract ALL line items
- NEVER return empty items if rows exist
- If CSV contains columns, map them into items
- Return ONLY valid JSON
"""


def extract_from_pdf(file_path):

    settings = get_ai_settings()

    client = get_claude_client()

    with open(file_path, "rb") as f:

        pdf_data = base64.standard_b64encode(
            f.read()
        ).decode("utf-8")

    message = client.messages.create(

        model=settings["model"],

        # SAFE but enough for PDFs
        max_tokens=REQUEST_MAX_TOKENS,

        messages=[{
            "role": "user",
            "content": [

                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_data
                    }
                },

                {
                    "type": "text",
                    "text": EXTRACTION_PROMPT
                }
            ]
        }]
    )

    update_token_usage(message)

    return _parse_claude_response(
        message.content[0].text
    )


def extract_from_image(
    file_path,
    mime_type="image/jpeg"
):

    settings = get_ai_settings()

    client = get_claude_client()

    with open(file_path, "rb") as f:

        img_data = base64.standard_b64encode(
            f.read()
        ).decode("utf-8")

    message = client.messages.create(

        model=settings["model"],

        max_tokens=REQUEST_MAX_TOKENS,

        messages=[{
            "role": "user",
            "content": [

                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": img_data
                    }
                },

                {
                    "type": "text",
                    "text": EXTRACTION_PROMPT
                }
            ]
        }]
    )

    update_token_usage(message)

    return _parse_claude_response(
        message.content[0].text
    )


def extract_from_email_text(email_body):

    settings = get_ai_settings()

    client = get_claude_client()

    # Prevent huge CSV/email prompts
    cleaned_body = email_body[:12000]

    message = client.messages.create(

        model=settings["model"],

        max_tokens=REQUEST_MAX_TOKENS,

        messages=[{
            "role": "user",
            "content":
                f"{EXTRACTION_PROMPT}\n\nEMAIL CONTENT:\n{cleaned_body}"
        }]
    )

    update_token_usage(message)

    return _parse_claude_response(
        message.content[0].text
    )


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