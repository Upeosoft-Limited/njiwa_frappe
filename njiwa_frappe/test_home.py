"""The /desk/njiwa page: what it reads, the one switch it flips, and the block it is drawn with.

No network: the page never calls Njiwa itself. The buttons that do
(test connection, send a test message) are api.py's and tested there.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from njiwa_frappe.events import CUSTOMER_EVENTS, OWNER_EVENT
from njiwa_frappe.home import BLOCK, HomeBlock, NjiwaHome, set_event, summary


class TestNjiwaHome(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.before = frappe.db.get_singles_dict("Njiwa Settings")
        self.addCleanup(self._restore)

    def _restore(self):
        frappe.set_user("Administrator")
        keep = {f"event_{e}": self.before.get(f"event_{e}") or 0 for e in [*CUSTOMER_EVENTS, OWNER_EVENT]}
        frappe.db.set_single_value("Njiwa Settings", keep)

    def test_the_summary_has_every_event_grouped_by_document(self):
        s = summary()
        self.assertEqual({e["key"] for e in s["events"]}, set(CUSTOMER_EVENTS))
        groups = [e["group"] for e in s["events"]]
        self.assertEqual(groups, sorted(groups, key=["Sales Order", "Sales Invoice", "Payment Entry", "Delivery Note"].index))
        self.assertEqual(s["owner_event"]["key"], OWNER_EVENT)
        self.assertEqual(len(s["steps"]), 4)
        self.assertIn(s["key"], ("live", "test", "none"))

    def test_the_key_itself_never_leaves_the_server(self):
        settings = frappe.get_single("Njiwa Settings")
        settings.get_password = lambda *a, **k: "sk_live_secret123"
        s = NjiwaHome(settings).summary()
        self.assertEqual(s["key"], "live")
        self.assertNotIn("secret123", frappe.as_json(s))

    def test_an_event_is_switched_through_the_settings(self):
        s = set_event("invoice_issued", 1)
        self.assertTrue(next(e for e in s["events"] if e["key"] == "invoice_issued")["on"])
        self.assertEqual(frappe.db.get_single_value("Njiwa Settings", "event_invoice_issued"), 1)
        s = set_event("invoice_issued", "0")
        self.assertFalse(next(e for e in s["events"] if e["key"] == "invoice_issued")["on"])

    def test_an_unknown_event_is_refused(self):
        self.assertRaises(frappe.ValidationError, set_event, "launch_rockets", 1)

    def test_only_a_system_manager_may_read_or_switch(self):
        frappe.set_user("Guest")
        self.assertRaises(frappe.PermissionError, summary)
        self.assertRaises(frappe.PermissionError, set_event, "invoice_issued", 1)

    def test_the_block_is_written_from_the_files_and_left_alone_when_unchanged(self):
        HomeBlock().write()
        doc = frappe.get_doc("Custom HTML Block", BLOCK)
        self.assertEqual(doc.script, HomeBlock().content()["script"])
        self.assertEqual([r.role for r in doc.roles], ["System Manager"])
        self.assertEqual(HomeBlock().write(), "The Njiwa page is already up to date.")
        workspace = frappe.get_doc("Workspace", "Njiwa")
        self.assertIn(BLOCK, [b.custom_block_name for b in workspace.custom_blocks])
