"""What saving the settings is allowed to change, and what it must refuse.

These run without a network, because everything they cover is checked without
one. Whether the key works is Test connection's job.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestNjiwaSettings(FrappeTestCase):
    def settings(self, **values):
        doc = frappe.get_single("Njiwa Settings")
        doc.update({"base_url": "https://njiwa.upeo.ai", "api_key": "sk_test_abc", **values})
        return doc

    def test_a_written_down_number_is_tidied_rather_than_refused(self):
        doc = self.settings(default_from="+254 712 345 678")
        doc.validate()
        self.assertEqual(doc.default_from, "254712345678")

    def test_a_local_number_is_refused_because_it_names_no_country(self):
        doc = self.settings(default_from="0712345678")
        self.assertRaises(frappe.ValidationError, doc.validate)

    def test_a_trailing_slash_never_reaches_a_url(self):
        doc = self.settings(base_url="https://njiwa.upeo.ai/")
        doc.validate()
        self.assertEqual(doc.base_url, "https://njiwa.upeo.ai")

    def test_an_address_that_is_not_a_url_is_refused(self):
        doc = self.settings(base_url="njiwa.upeo.ai")
        self.assertRaises(frappe.ValidationError, doc.validate)

    def test_something_that_is_not_an_api_key_is_refused(self):
        doc = self.settings(api_key="whsec_or_a_password")
        self.assertRaises(frappe.ValidationError, doc.validate)

    def test_saving_without_touching_the_key_still_works(self):
        # Frappe hands back asterisks for a stored Password field. Checking
        # those as if they were a key would fail every second save.
        doc = self.settings(api_key="**********")
        doc.validate()

    def test_both_key_kinds_are_accepted(self):
        for key in ("sk_live_abc", "sk_test_abc"):
            with self.subTest(key=key):
                self.settings(api_key=key).validate()
