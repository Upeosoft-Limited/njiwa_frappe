"""When a message goes out, and to whom.

One rule runs the whole of this file: a document reaching a moment that is
really true sends the message for that moment, once. Nothing is sent while
somebody waits for a form to save, and nothing that fails here is ever allowed
to stop a document being submitted or cancelled.

Every event is off until somebody turns it on in Njiwa Settings. An app that
starts messaging customers the day it is installed is an app nobody installs
twice, and on a bench shared with other apps it would be somebody else's
customers as well.
"""

from __future__ import annotations

import hashlib

import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import get_default_contact

from njiwa_frappe import api, client, numbers, templates

# The doctype that remembers what has already been sent. It holds no message
# text: Njiwa keeps the messages, and a second copy is a second thing to keep
# in step.
MARKER = "Njiwa Sent Message"

# The short queue. A WhatsApp send is one HTTP call with a 30 second ceiling,
# which is exactly what the short queue is for, and putting it there keeps it
# away from the long jobs that a stock reposting can fill the default queue
# with.
QUEUE = "short"


def _not_a_return(doc) -> bool:
    """A credit note and a sales return are their own moments, handled below."""
    return not doc.get("is_return")


def _a_return(doc) -> bool:
    return bool(doc.get("is_return"))


def _money_from_a_customer(doc) -> bool:
    """Money coming in from a customer, and not a supplier payment or a transfer."""
    return doc.get("payment_type") == "Receive" and doc.get("party_type") == "Customer"


def _always(doc) -> bool:
    return True


# Every moment this app can message a customer about, keyed by the name that
# appears in the settings fieldnames: event_<key> is the toggle and
# message_<key> is the wording.
#
# These are ERPNext's own submit and cancel moments, one entry per document
# type rather than one "cancelled" entry for all of them. That is deliberate:
# cancelling in ERPNext cascades, so cancelling a Sales Invoice usually means
# cancelling its Delivery Note and its Payment Entry first. A single blanket
# "cancelled" event would send the same customer three messages about one
# cancellation.
CUSTOMER_EVENTS: dict[str, dict] = {
    "order_placed": {
        "doctype": "Sales Order",
        "when": "on_submit",
        "label": "Sales Order submitted",
        "applies": _always,
    },
    "order_cancelled": {
        "doctype": "Sales Order",
        "when": "on_cancel",
        "label": "Sales Order cancelled",
        "applies": _always,
    },
    "invoice_issued": {
        "doctype": "Sales Invoice",
        "when": "on_submit",
        "label": "Sales Invoice submitted",
        "applies": _not_a_return,
    },
    "invoice_cancelled": {
        "doctype": "Sales Invoice",
        "when": "on_cancel",
        "label": "Sales Invoice cancelled",
        "applies": _not_a_return,
    },
    "credit_note": {
        "doctype": "Sales Invoice",
        "when": "on_submit",
        "label": "Credit note submitted",
        "applies": _a_return,
    },
    "payment_received": {
        "doctype": "Payment Entry",
        "when": "on_submit",
        "label": "Payment received",
        "applies": _money_from_a_customer,
    },
    "payment_cancelled": {
        "doctype": "Payment Entry",
        "when": "on_cancel",
        "label": "Payment cancelled",
        "applies": _money_from_a_customer,
    },
    "delivery_sent": {
        "doctype": "Delivery Note",
        "when": "on_submit",
        "label": "Delivery Note submitted",
        "applies": _not_a_return,
    },
    "delivery_cancelled": {
        "doctype": "Delivery Note",
        "when": "on_cancel",
        "label": "Delivery Note cancelled",
        "applies": _not_a_return,
    },
}

# The one message that goes to the shop rather than to the customer. Which
# document counts as "an order came in" is a setting, because a shop that
# quotes and confirms works from Sales Orders and a shop that sells over a
# counter never makes one.
OWNER_EVENT = "new_order"
DEFAULT_ALERT_ON = "Sales Order"


# ---------------------------------------------------------------- the hooks


def on_submit(doc, method=None) -> None:
    handle(doc, "on_submit")


def on_cancel(doc, method=None) -> None:
    handle(doc, "on_cancel")


def handle(doc, when: str) -> None:
    """Work out what this moment is worth telling anybody, and queue it.

    Everything is inside one try. A document must never fail to submit, and a
    cancellation must never fail to go through, because a WhatsApp message
    could not be arranged: that would turn a messaging app into a reason the
    shop cannot invoice.
    """
    try:
        if quiet_time():
            return

        settings = client.get_settings()
        if not settings.enabled:
            # The master switch. It is checked here as well as in api.send so
            # that a switched-off site does not fill its queue with thousands
            # of jobs that will each fail loudly on arrival.
            return

        for event, moment in CUSTOMER_EVENTS.items():
            if moment["doctype"] != doc.doctype or moment["when"] != when:
                continue
            if not moment["applies"](doc):
                continue
            if not settings.get(f"event_{event}"):
                continue
            tell_the_customer(doc, event)

        tell_the_shop(doc, when, settings)
    except Exception:
        frappe.log_error(
            title="Njiwa could not queue a message",
            message=frappe.get_traceback(with_context=True),
            reference_doctype=doc.doctype,
            reference_name=doc.name,
        )


def quiet_time() -> bool:
    """Moments when submitting a document must not message anybody.

    A Data Import of five thousand historical invoices submits five thousand
    documents, and every one of them would be a real WhatsApp message to a
    real customer about an order they placed two years ago. The same goes for
    a patch, a fresh install and the setup wizard, all of which submit
    documents on a site nobody has finished setting up.

    Frappe's own notification layer makes the same checks for the same reason;
    this one is stricter, because an email that should not have gone out is
    embarrassing and a WhatsApp message that should not have gone out costs
    money and reaches a phone in somebody's hand.
    """
    flags = frappe.flags
    return bool(
        flags.in_import
        or flags.in_migrate
        or flags.in_patch
        or flags.in_install
        or flags.in_setup_wizard
        or flags.in_test
    )


def tell_the_customer(doc, event: str) -> None:
    number = customer_number(doc)
    if not number:
        # A customer with no number is normal, and it is not an error. It is
        # written on the document, though, because "I turned it on and nothing
        # happened" is the first thing anybody asks, and this is the answer,
        # sitting where they are already looking.
        note(
            doc.doctype,
            doc.name,
            _("Njiwa: no WhatsApp message, because there is no phone number for this customer."),
        )
        return

    marker = remember(doc, event, number)
    if marker:
        queue(marker)


def tell_the_shop(doc, when: str, settings) -> None:
    """One message to the shop when an order becomes real.

    Sent once per document, on submit, and never for a return: a credit note
    is not a new order and nobody wants to be woken up by one.
    """
    if when != "on_submit" or not settings.get(f"event_{OWNER_EVENT}"):
        return
    if doc.doctype != (settings.get("new_order_alert_on") or DEFAULT_ALERT_ON):
        return
    if doc.get("is_return"):
        return

    for number in numbers.parse_list(settings.get("alert_numbers")):
        marker = remember(doc, OWNER_EVENT, number)
        if marker:
            queue(marker)


# ------------------------------------------------------- the customer's number


def customer_number(doc) -> str:
    """The number to send to, or '' when this customer has none.

    The Customer's own Mobile No comes first. That is the number the shop
    maintains and the one it would ring, where the contact on a single
    document is often a storekeeper or a driver who happened to sign for that
    delivery. When the Customer has none, the document's own contact is a
    better answer than nothing, and the Contact record behind it is the last
    place worth looking.
    """
    customer = doc.get("customer")
    if not customer and doc.get("party_type") == "Customer":
        # A Payment Entry names the customer as the party, because the same
        # doctype is used to pay suppliers and employees.
        customer = doc.get("party")

    if customer:
        number = numbers.first_msisdn(
            frappe.db.get_value("Customer", customer, "mobile_no")
        )
        if number:
            return number

    # Sales Order, Sales Invoice and Delivery Note each carry this, fetched
    # from the contact chosen on the document. A Payment Entry does not have
    # the field at all, which .get() answers with None rather than raising.
    number = numbers.first_msisdn(doc.get("contact_mobile"))
    if number:
        return number

    contact = doc.get("contact_person")
    if not contact and customer:
        contact = get_default_contact("Customer", customer)
    if not contact:
        return ""

    try:
        person = frappe.get_cached_doc("Contact", contact)
    except frappe.DoesNotExistError:
        # The document still names a Contact that has since been deleted.
        # That is somebody else's tidying up, not a reason to raise here.
        return ""

    # Mobile No and Phone are the two boxes on the Contact form, and
    # phone_nos is where a Contact with more than one number keeps them,
    # because that child table is the only place the form lets you add a
    # second. The primary mobile comes first, then anything else, in the
    # order the Contact lists them.
    candidates = [person.get("mobile_no"), person.get("phone")]
    rows = person.get("phone_nos") or []
    candidates += [row.phone for row in rows if row.is_primary_mobile_no]
    candidates += [row.phone for row in rows if not row.is_primary_mobile_no]

    for candidate in candidates:
        number = numbers.first_msisdn(candidate)
        if number:
            return number

    return ""


# ------------------------------------------------------------- not twice, ever


def idempotency_key(doc, event: str, number: str) -> str:
    """One key per document, per event, per recipient.

    Njiwa honours it for 24 hours, so a job that runs twice, or a worker that
    is killed after the message was accepted and before the answer arrived,
    replays the first answer instead of messaging the customer again. The
    recipient is part of the key because one new-order alert goes to several
    of the shop's own numbers, and those must not collapse into one another.

    The site is in there too. Several sites on one bench can share one Njiwa
    account, and SINV-00001 exists on all of them.
    """
    site = _short_hash(frappe.local.site)
    recipient = _short_hash(number, length=6)
    key = f"frappe-{site}-{frappe.scrub(doc.doctype)}-{doc.name}-{event}-{recipient}"

    # The key is also this marker's document name, and a Frappe name stops at
    # 140 characters. A naming series long enough to reach that is unusual but
    # not impossible, and a key that gets silently truncated would collide.
    if len(key) > 140:
        key = f"frappe-{site}-{_short_hash(key, length=32)}"
    return key


def _short_hash(value: str, length: int = 8) -> str:
    # Not a security decision: this only has to be short and stable.
    return hashlib.md5(str(value).encode(), usedforsecurity=False).hexdigest()[:length]


def remember(doc, event: str, number: str) -> str | None:
    """Write down that this message is going, or answer None if it already did.

    The row is written inside the transaction that is submitting the document,
    so a submit that is rolled back afterwards takes the marker with it and
    the customer hears nothing about a document that does not exist. The job
    is queued after that same commit, for the same reason.

    This is the guard that outlives the idempotency key. Njiwa forgets a key
    after 24 hours; this row is how a document that somehow reaches the same
    moment twice, months apart, still only sends once.
    """
    key = idempotency_key(doc, event, number)
    if frappe.db.exists(MARKER, key):
        return None

    frappe.get_doc(
        {
            "doctype": MARKER,
            "idempotency_key": key,
            "reference_doctype": doc.doctype,
            "reference_name": doc.name,
            "event": event,
            "to_number": number,
            "status": "Queued",
        }
    ).insert(ignore_permissions=True)

    return key


def queue(marker: str) -> None:
    """Hand the send to a background worker, after the document is committed.

    enqueue_after_commit is the whole point of this function. Frappe throws
    the queued job away when the transaction rolls back, so a submit that
    fails validation further down the line cannot message a customer about a
    document that was never saved. It also means the marker row is certainly
    on disk by the time the worker looks for it.
    """
    frappe.enqueue(
        "njiwa_frappe.events.deliver",
        queue=QUEUE,
        enqueue_after_commit=True,
        marker=marker,
    )


# ----------------------------------------------------------------- the worker


def deliver(marker: str) -> None:
    """Send one message. Runs on a worker, long after the form was saved.

    Nothing raises out of here. A failure is written on the document's
    timeline and on the marker, where the shop will find it, and the job is
    not retried: Njiwa retries a message it has accepted, and a message it
    never accepted going out twice is worse than one that did not go at all.
    """
    row = frappe.db.get_value(
        MARKER,
        marker,
        ["reference_doctype", "reference_name", "event", "to_number", "status"],
        as_dict=True,
    )
    if not row:
        return
    if row.status != "Queued":
        # Already dealt with. A worker that is restarted mid-job must not send
        # a second time.
        return

    try:
        answer = attempt(marker, row)
    except Exception as refusal:
        # Everything from here is caught, not only Njiwa's refusals: a missing
        # document, a template that will not render, a settings document that
        # cannot be read. The marker must end up saying what happened whatever
        # went wrong, because a row left saying Queued for ever is the one
        # state nobody can act on.
        failed(marker, row, str(refusal) or _("Njiwa gave no reason."))
        frappe.log_error(
            title=f"Njiwa could not send a message for {row.reference_name}",
            message=frappe.get_traceback(with_context=True),
            reference_doctype=row.reference_doctype,
            reference_name=row.reference_name,
        )
        return

    if answer is not None:
        sent(marker, row, answer)


def attempt(marker: str, row) -> dict | None:
    """Render the message and hand it to Njiwa. Raises, and deliver() catches.

    Answers None when there was nothing to send and the marker has already
    been told why, which is a different thing from a failure to send.
    """
    try:
        doc = frappe.get_doc(row.reference_doctype, row.reference_name)
    except frappe.DoesNotExistError:
        failed(marker, row, _("The document was deleted before the message went out."))
        return None

    settings = client.get_settings()

    # The default matters: a site that ticked an event and never opened the
    # wording box still has something to say. An empty box is different, and
    # deliberate: clearing it is how a shop turns one message off without
    # turning the event off.
    wording = settings.get(f"message_{row.event}")
    if wording is None:
        wording = templates.default_for(row.event)

    message = templates.render(wording, doc)
    if not message:
        failed(
            marker,
            row,
            _("The wording for this event is empty, so there was nothing to send."),
        )
        return None

    return api.send(
        row.to_number,
        text=message,
        idempotency_key=marker,
        # Never waiting, whatever Wait for the result says. Nobody is watching
        # this send, and holding a worker for fifteen seconds to learn
        # something Njiwa will do anyway is fifteen seconds the next message
        # spends in the queue.
        wait=False,
    )


def sent(marker: str, row, answer: dict) -> None:
    message_id = answer.get("id") or "?"
    frappe.db.set_value(
        MARKER,
        marker,
        {"status": "Sent", "message_id": message_id, "failure_reason": None},
    )

    text = _("Njiwa: WhatsApp sent to +{0} ({1}).").format(row.to_number, message_id)
    if answer.get("sandbox"):
        text += " " + _("That was a test key, so nothing reached WhatsApp.")
    note(row.reference_doctype, row.reference_name, text)


def failed(marker: str, row, reason: str) -> None:
    frappe.db.set_value(MARKER, marker, {"status": "Failed", "failure_reason": reason})
    note(
        row.reference_doctype,
        row.reference_name,
        _("Njiwa: could not WhatsApp +{0}. {1}").format(row.to_number, reason),
    )


def note(reference_doctype: str, reference_name: str, text: str) -> None:
    """Write a line on the document's timeline, the way an order note reads.

    Wrapped, because this is the record of what happened and not the thing
    that happened. A comment that cannot be written must not turn a message
    that was sent into an exception saying it was not.
    """
    try:
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "comment_email": frappe.session.user,
                "comment_by": "Njiwa",
                "content": text,
            }
        ).insert(ignore_permissions=True)
    except Exception:
        frappe.logger("njiwa").warning(
            f"Could not write a Njiwa note on {reference_doctype} {reference_name}: {text}"
        )
