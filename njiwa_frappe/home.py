"""The Njiwa page on the desk (/desk/njiwa): what it shows, and the one switch it flips.

The workspace holds a single Custom HTML Block, "Njiwa Home", whose markup,
style and script live beside this file in njiwa/home_block/. Frappe does not
sync a Custom HTML Block from an app's files the way it syncs the workspace,
so HomeBlock writes it on install and on every migrate, and an upgrade that
changes the page reaches every site with its next migrate.

The page asks `summary` for everything it shows in one call, and `set_event`
is the only thing it changes: one event on or off in Njiwa Settings.
Both are for System Managers only, the same people who can open the settings.
"""

from __future__ import annotations

import os
import re
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, now_datetime

from njiwa_frappe.events import CUSTOMER_EVENTS, OWNER_EVENT

SETTINGS = "Njiwa Settings"
SENT = "Njiwa Sent Message"
BLOCK = "Njiwa Home"
RECENT = 6

# The documents the events hang off, in the order a sale moves through them.
GROUPS = ("Sales Order", "Sales Invoice", "Payment Entry", "Delivery Note")


class NjiwaHome:
    """Reads what the page shows. Nothing here sends, and nothing here writes."""

    def __init__(self, settings=None, now=now_datetime):
        self.settings = settings or frappe.get_single(SETTINGS)
        self.now = now

    def summary(self) -> dict[str, Any]:
        key = self._key_kind()
        events = self._events()
        return {
            "logo": self._logo(),
            "enabled": bool(self.settings.enabled),
            "key": key,
            "send_from": self.settings.default_from or "",
            "events": events,
            "owner_event": self._owner_event(),
            "steps": self._steps(key, events),
            "counts": self._counts(),
            "recent": self._recent(),
        }

    # -- the parts -----------------------------------------------------------------
    def _key_kind(self) -> str:
        """"live", "test" or "none". Only the prefix is read; the key never leaves the server."""
        key = self.settings.get_password("api_key", raise_exception=False) or ""
        if key.startswith("sk_live_"):
            return "live"
        if key.startswith("sk_test_"):
            return "test"
        return "none"

    @staticmethod
    def _logo() -> str | None:
        """The site's own logo, so the page wears the shop's brand; None keeps the Njiwa mark.

        Frappe's and ERPNext's stock marks are not a brand the site chose, so
        they count as none.
        """
        logo = frappe.db.get_single_value("Website Settings", "app_logo") or ""
        if not logo or re.search(r"(frappe|erpnext)", logo, re.I):
            return None
        return logo

    def _label(self, fieldname: str, fallback: str) -> str:
        field = frappe.get_meta(SETTINGS).get_field(fieldname)
        return _(field.label) if field and field.label else fallback

    def _events(self) -> list[dict[str, Any]]:
        rows = []
        for key, spec in CUSTOMER_EVENTS.items():
            rows.append({
                "key": key,
                "label": self._label(f"event_{key}", spec["label"]),
                "group": spec["doctype"],
                "on": bool(self.settings.get(f"event_{key}")),
                "worded": bool((self.settings.get(f"message_{key}") or "").strip()),
            })
        return sorted(rows, key=lambda r: GROUPS.index(r["group"]) if r["group"] in GROUPS else len(GROUPS))

    def _owner_event(self) -> dict[str, Any]:
        numbers = [n for n in (self.settings.get("alert_numbers") or "").replace(",", "\n").splitlines() if n.strip()]
        return {
            "key": OWNER_EVENT,
            "label": self._label(f"event_{OWNER_EVENT}", "Tell me about new orders"),
            "on": bool(self.settings.get(f"event_{OWNER_EVENT}")),
            "numbers": len(numbers),
        }

    def _steps(self, key: str, events: list[dict]) -> list[dict[str, Any]]:
        sent = frappe.db.exists(SENT, {"status": "Sent"})
        return [
            {"key": "key", "done": key != "none", "title": _("Paste your API key"),
             "hint": _("From the Njiwa console. A key starting sk_test_ sends nothing real.")},
            {"key": "enable", "done": bool(self.settings.enabled), "title": _("Switch sending on"),
             "hint": _("Tick “Send messages through Njiwa” in the settings.")},
            {"key": "event", "done": any(e["on"] for e in events) or bool(self.settings.get(f"event_{OWNER_EVENT}")),
             "title": _("Choose what to send"), "hint": _("Turn on the moments below that your customers should hear about.")},
            {"key": "sent", "done": bool(sent), "title": _("Your first message goes out"),
             "hint": _("It appears under Recent messages once a customer has been sent one.")},
        ]

    def _counts(self) -> dict[str, int]:
        # One count per status rather than a GROUP BY: v16 refuses aggregate
        # strings in fields, and the older Frappe this app still runs on has no
        # dict syntax for them.
        since = add_days(self.now(), -7)

        def count(status: str) -> int:
            return frappe.db.count(SENT, {"status": status, "creation": [">=", since]})

        return {"sent": count("Sent"), "failed": count("Failed"), "queued": count("Queued")}

    def _recent(self) -> list[dict[str, Any]]:
        rows = frappe.get_all(
            SENT,
            fields=["name", "event", "status", "to_number", "reference_doctype", "reference_name", "creation",
                    "failure_reason"],
            order_by="creation desc",
            limit=RECENT,
        )
        labels = {e: self._label(f"event_{e}", e) for e in [*CUSTOMER_EVENTS, OWNER_EVENT]}
        return [{
            "name": r.name,
            "event": labels.get(r.event, r.event or ""),
            "status": r.status,
            "to": _masked(r.to_number),
            "doctype": r.reference_doctype,
            "docname": r.reference_name,
            "at": str(r.creation),
            "why": (r.failure_reason or "")[:160],
        } for r in rows]


def _masked(number: str | None) -> str:
    digits = "".join(ch for ch in (number or "") if ch.isdigit())
    return f"+{digits[:3]} ••• {digits[-3:]}" if len(digits) >= 7 else (number or "")


class HomeBlock:
    """Writes the "Njiwa Home" Custom HTML Block from the files in njiwa/home_block/."""

    FILES = {"html": "home.html", "style": "home.css", "script": "home.js"}

    def __init__(self, folder: str | None = None):
        self.folder = folder or frappe.get_app_path("njiwa_frappe", "njiwa", "home_block")

    def content(self) -> dict[str, str]:
        out = {}
        for field, name in self.FILES.items():
            with open(os.path.join(self.folder, name), encoding="utf-8") as handle:
                out[field] = handle.read()
        return out

    def write(self) -> str:
        """Create or refresh the block. Safe to run again: unchanged content writes nothing."""
        if not frappe.db.table_exists("Custom HTML Block"):
            return "This Frappe has no Custom HTML Block, so the Njiwa page keeps its plain layout."
        content = self.content()
        if frappe.db.exists("Custom HTML Block", BLOCK):
            doc = frappe.get_doc("Custom HTML Block", BLOCK)
            if all((doc.get(k) or "") == v for k, v in content.items()):
                return "The Njiwa page is already up to date."
            doc.update(content)
            doc.save(ignore_permissions=True)
            return "Refreshed the Njiwa page."
        doc = frappe.new_doc("Custom HTML Block")
        doc.update({"private": 0, **content})
        doc.append("roles", {"role": "System Manager"})
        doc.insert(ignore_permissions=True, set_name=BLOCK)
        return "Wrote the Njiwa page."


@frappe.whitelist()
def summary() -> dict[str, Any]:
    frappe.only_for("System Manager")
    return NjiwaHome().summary()


# POST only, for the reason send_test_message in api.py gives: a GET could be a
# link somebody else chose, and switching a customer message on is a send.
@frappe.whitelist(methods=["POST"])
def set_event(event: str, on: int | str | bool) -> dict[str, Any]:
    """Switch one event on or off.

    Only that one tick is written. Saving the whole settings document would
    refuse a shop that has not pasted its key yet (the key is mandatory), and
    none of the settings' own checks look at the events, so there is nothing a
    full save would add. Events send nothing while sending is off.
    """
    frappe.only_for("System Manager")
    if event not in CUSTOMER_EVENTS and event != OWNER_EVENT:
        frappe.throw(_("There is no Njiwa event called {0}.").format(frappe.bold(event)))
    frappe.db.set_single_value(SETTINGS, f"event_{event}", 1 if str(on).lower() in ("1", "true") else 0)
    frappe.clear_document_cache(SETTINGS, SETTINGS)
    return NjiwaHome().summary()
