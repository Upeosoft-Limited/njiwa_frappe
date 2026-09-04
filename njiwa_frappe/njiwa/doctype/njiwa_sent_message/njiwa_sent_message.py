"""One row per message this app has arranged.

It is a marker, not a copy. Njiwa already stores every message, its text, its
status and its failure reason, and a second copy in this database is a second
thing to keep in step. What is here is the fact that a message was arranged
for a particular document, event and recipient, which is the one thing Njiwa
cannot answer: it is what stops the same customer being told twice.

Rows are written by njiwa_frappe.events and by nothing else. Nobody creates
one by hand, which is why the doctype is marked in_create and every field is
read only.
"""

from __future__ import annotations

from frappe.model.document import Document


class NjiwaSentMessage(Document):
    pass
