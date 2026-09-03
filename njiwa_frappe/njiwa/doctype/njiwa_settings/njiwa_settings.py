"""The settings document.

Everything checked here is checked without a network call, so a Njiwa outage
can never stop somebody saving their own settings. Whether the key actually
works is what Test connection is for.
"""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document

from njiwa_frappe.client import DEFAULT_BASE_URL

VALID_KEY_PREFIXES = ("sk_live_", "sk_test_")


class NjiwaSettings(Document):
    def validate(self) -> None:
        self.tidy_address()
        self.tidy_sending_number()
        self.check_key_looks_like_a_key()

    def tidy_address(self) -> None:
        self.base_url = (self.base_url or DEFAULT_BASE_URL).strip().rstrip("/")
        if not self.base_url.startswith(("https://", "http://")):
            frappe.throw(
                _("The Njiwa address must start with https://. It is currently {0}.").format(
                    frappe.bold(self.base_url)
                ),
                title=_("That address will not work"),
            )

    def tidy_sending_number(self) -> None:
        """A msisdn, digits only.

        People paste +254 712 345 678 because that is how a number is written
        down. Njiwa matches the sending number exactly, so the spaces and the
        plus have to come off, and taking them off silently is kinder than
        refusing a number that is perfectly correct.
        """
        if not self.default_from:
            return

        digits = re.sub(r"\D", "", self.default_from)
        if not digits:
            frappe.throw(
                _("{0} does not contain a phone number.").format(frappe.bold(self.default_from)),
                title=_("Check the sending number"),
            )
        if digits.startswith("0"):
            frappe.throw(
                _(
                    "Write the sending number in full international form, digits only, "
                    "like 254712345678. A number beginning 0 is a local number, and "
                    "which country it belongs to depends on who is reading it."
                ),
                title=_("Check the sending number"),
            )
        self.default_from = digits

    def check_key_looks_like_a_key(self) -> None:
        """Catch the paste that went wrong, not the key that is merely wrong.

        Frappe replaces a saved Password field with a row of asterisks once it
        has been stored, so a document saved without touching the key arrives
        here holding asterisks rather than the key. Checking those would fail
        every second save.
        """
        key = (self.api_key or "").strip()
        if not key or set(key) == {"*"}:
            return

        self.api_key = key
        if not key.startswith(VALID_KEY_PREFIXES):
            frappe.throw(
                _(
                    "A Njiwa API key starts with sk_live_ or sk_test_. This one starts "
                    "with {0}, which usually means a webhook secret or a console "
                    "password was pasted by mistake."
                ).format(frappe.bold(key[:8])),
                title=_("That does not look like an API key"),
            )
