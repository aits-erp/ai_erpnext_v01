import frappe
from frappe.model.document import Document


class ApiController(Document):
    pass


@frappe.whitelist()
def test_ai_connection():
    try:
        from ai_erpnext.claude_helper import get_claude_client, get_ai_settings

        settings = get_ai_settings()

        if settings["status"] == "Disabled":
            return {
                "success": False,
                "message": "AI service is disabled"
            }

        client = get_claude_client()

        message = client.messages.create(
            model=settings["model"],
            max_tokens=10,
            messages=[
                {
                    "role": "user",
                    "content": "Reply with only: OK"
                }
            ]
        )

        return {
            "success": True,
            "message": "Connection successful",
            "response": message.content[0].text
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "AI Connection Test")

        return {
            "success": False,
            "message": str(e)
        }