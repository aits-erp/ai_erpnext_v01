import email
import imaplib
import ssl

import frappe
from frappe.utils import cint, get_datetime


SYNC_START_DATE = "01-Jan-2026"


def sync_account_from_2026(account_name):
    """
    Custom IMAP sync for AI Email.

    Only emails received since 01-Jan-2026 are considered.
    Standard Frappe files are not modified.
    """

    account = frappe.get_doc("Email Account", account_name)

    if not account.enable_incoming:
        return {
            "success": False,
            "message": "Incoming email is disabled",
        }

    if not account.use_imap:
        return {
            "success": False,
            "message": "This custom sync currently requires IMAP",
        }

    # ---------------------------------------------------------
    # Connect to IMAP
    # ---------------------------------------------------------

    if account.use_ssl:
        mail = imaplib.IMAP4_SSL(
            account.email_server,
            account.incoming_port or 993,
            ssl_context=ssl.create_default_context(),
        )
    else:
        mail = imaplib.IMAP4(
            account.email_server,
            account.incoming_port or 143,
        )

        if account.use_starttls:
            mail.starttls()

    try:
        username = account.login_id or account.email_id
        password = account.get_password()

        mail.login(username, password)

        # -----------------------------------------------------
        # Select INBOX
        # -----------------------------------------------------

        status, _ = mail.select("INBOX", readonly=True)

        if status != "OK":
            frappe.throw("Unable to select INBOX")

        # -----------------------------------------------------
        # IMPORTANT:
        # Search by DATE, not UID.
        #
        # This means:
        # 01-Jan-2026 onward
        # -----------------------------------------------------

        status, data = mail.uid(
            "search",
            None,
            f"SINCE {SYNC_START_DATE}",
        )

        if status != "OK":
            frappe.throw("Unable to search mailbox")

        uid_list = data[0].split() if data and data[0] else []

        processed = 0
        skipped = 0
        errors = []

        # -----------------------------------------------------
        # Process each matching email
        # -----------------------------------------------------

        for uid in uid_list:

            try:
                status, msg_data = mail.uid(
                    "fetch",
                    uid,
                    "(BODY.PEEK[] FLAGS)",
                )

                if status != "OK" or not msg_data:
                    skipped += 1
                    continue

                raw_email = None

                for part in msg_data:
                    if isinstance(part, tuple):
                        raw_email = part[1]
                        break

                if not raw_email:
                    skipped += 1
                    continue

                message = email.message_from_bytes(raw_email)

                # -------------------------------------------------
                # Get actual email date
                # -------------------------------------------------

                date_header = message.get("Date")

                if not date_header:
                    skipped += 1
                    continue

                email_date = email.utils.parsedate_to_datetime(date_header)

                if email_date.tzinfo:
                    email_date = email_date.astimezone().replace(tzinfo=None)

                # Safety check:
                # Gmail's SINCE search is date based, but we also
                # verify the actual Date header.
                if email_date < get_datetime("2026-01-01"):
                    skipped += 1
                    continue

                # -------------------------------------------------
                # Check whether this UID already exists
                # -------------------------------------------------

                existing = frappe.db.exists(
                    "Communication",
                    {
                        "email_account": account.name,
                        "uid": cint(uid),
                        "communication_medium": "Email",
                    },
                )

                if existing:
                    skipped += 1
                    continue

                # -------------------------------------------------
                # Use Frappe's existing InboundMail processing.
                # -------------------------------------------------

                from frappe.email.receive import InboundMail

                inbound_mail = InboundMail(
                    raw_email,
                    account,
                    frappe.safe_decode(uid),
                    None,
                    None,
                )

                communication = inbound_mail.process()

                if communication:
                    processed += 1

            except Exception:
                frappe.db.rollback()

                errors.append(
                    {
                        "uid": frappe.safe_decode(uid),
                        "error": frappe.get_traceback(),
                    }
                )

        frappe.db.commit()

        return {
            "success": True,
            "account": account_name,
            "start_date": SYNC_START_DATE,
            "found": len(uid_list),
            "processed": processed,
            "skipped": skipped,
            "errors": len(errors),
        }

    finally:
        try:
            mail.logout()
        except Exception:
            pass
