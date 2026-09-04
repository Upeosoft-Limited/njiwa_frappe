"""The message itself.

A template is plain text with placeholders in braces. The list of placeholders
is the same one every Njiwa plugin uses, so a shop owner who has set one of
these up on another platform already knows what to type. What each one is
filled in with here is an ERPNext field, and PLACEHOLDERS below is both the
substitution table and the documentation, so the two cannot drift apart.
"""

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, formatdate, get_url, get_url_to_form

# WhatsApp takes 4096 characters. Stopping short leaves room for a footer.
MAX_LENGTH = 4000

# How many lines {items} prints before it starts counting instead. An ERPNext
# invoice can carry two hundred rows, and a WhatsApp message that long is not
# read by anybody.
MAX_ITEMS = 10

# Where a customer with a portal login can see the document. These are
# ERPNext's own website routes, from its hooks.py, and there is no entry for
# Payment Entry because ERPNext gives it no portal page.
PORTAL_ROUTES = {
    "Sales Order": "orders",
    "Sales Invoice": "invoices",
    "Delivery Note": "shipments",
}


def placeholders() -> dict[str, str]:
    """Placeholder, and what it is replaced with, in the shop's own words."""
    return {
        "{first_name}": _("The first word of the customer's name, or 'there' if there is none."),
        "{last_name}": _("The rest of the customer's name."),
        "{customer_name}": _("The customer's name as ERPNext holds it."),
        "{order_number}": _("The name of the document that caused the message, such as SINV-00042."),
        "{order_total}": _("The document total, with your currency symbol."),
        "{order_date}": _("The posting date, or the order date on a Sales Order."),
        "{order_status}": _("The document's ERPNext status, such as 'To Deliver and Bill'."),
        "{payment_method}": _("The mode of payment, where the document has one."),
        "{items}": _("One line per row, as '2 x Blue shirt'."),
        "{item_count}": _("How many items in total."),
        "{shop_name}": _("The company on the document."),
        "{order_url}": _(
            "A link to the document on your website. It only opens for a customer who has a "
            "portal login, so leave it out unless yours do."
        ),
        "{admin_url}": _(
            "A link that opens the document in your desk. Only put this in the message to "
            "yourself: a customer cannot open it."
        ),
    }


def default_for(event: str) -> str:
    """What each message says before anybody edits it.

    These live in Python rather than only in the doctype, because the settings
    form is not what sends a message: a background worker is, and it must have
    something sensible to say on a site whose settings page has been opened
    exactly once. install.py copies them into the settings on install and on
    migrate, so the wording is also there to be read and edited on the form.

    They are deliberately short. A WhatsApp message that reads like an email
    gets read like an email, which is to say not at all.
    """
    return DEFAULTS.get(event, "")


DEFAULTS = {
    "order_placed": (
        "Hi {first_name}, we have your order {order_number} for {order_total}. "
        "We will let you know as it moves along.\n\n{items}\n\n{shop_name}"
    ),
    "order_cancelled": (
        "Hi {first_name}, order {order_number} has been cancelled. If that is not what you "
        "expected, reply to this message and we will look into it.\n\n{shop_name}"
    ),
    "invoice_issued": (
        "Hi {first_name}, here is invoice {order_number}, dated {order_date}, "
        "for {order_total}.\n\n{items}\n\n{shop_name}"
    ),
    "invoice_cancelled": (
        "Hi {first_name}, invoice {order_number} has been cancelled, so there is nothing to pay "
        "on it. If you have already paid it, reply to this message and we will sort it "
        "out.\n\n{shop_name}"
    ),
    "credit_note": (
        "Hi {first_name}, we have credited {order_total} back to you on {order_number}. "
        "Where money is going back to a bank account, it takes a few days to show.\n\n{shop_name}"
    ),
    "payment_received": (
        "Hi {first_name}, thank you. We have received {order_total} from you and put it against "
        "your account. Our reference is {order_number}.\n\n{shop_name}"
    ),
    "payment_cancelled": (
        "Hi {first_name}, the payment we recorded as {order_number} for {order_total} has been "
        "reversed in our books. If you have paid, reply to this message and we will check "
        "it.\n\n{shop_name}"
    ),
    "delivery_sent": (
        "Hi {first_name}, your goods are on the way. Our delivery note is "
        "{order_number}.\n\n{items}\n\n{shop_name}"
    ),
    "delivery_cancelled": (
        "Hi {first_name}, delivery {order_number} has been cancelled, so nothing on it is on its "
        "way. Reply to this message if you were expecting it today.\n\n{shop_name}"
    ),
    "new_order": (
        "New order {order_number} on {shop_name}.\n\n{customer_name}\n"
        "{item_count} item(s), {order_total}\n\n{admin_url}"
    ),
}


def render(template: str | None, doc) -> str:
    """Fill a template in from a document. Returns '' for an empty template.

    An empty template is how a shop turns one message off without turning the
    event off, so it is a legitimate answer and not a fault.
    """
    template = (template or "").strip()
    if not template:
        return ""

    values = values_for(doc)

    # Anything in braces that is not a placeholder is a typo, usually
    # {order_no} for {order_number}. It is found in the template rather than in
    # the finished message, because a message can quite legitimately contain
    # braces once an item name has been substituted in, and a shop should not
    # have an item renamed out from under it.
    unknown = sorted(set(re.findall(r"\{[a-z_]+\}", template)) - set(values))
    if unknown:
        frappe.logger("njiwa").warning(
            f"Unknown placeholder {', '.join(unknown)} in a Njiwa message template. "
            "It was removed before sending."
        )
        for token in unknown:
            template = template.replace(token, "")

    # One pass, so a value that happens to contain braces is left alone rather
    # than substituted again.
    message = re.sub(r"\{[a-z_]+\}", lambda found: values.get(found.group(0), ""), template)

    message = re.sub(r"\n{3,}", "\n\n", message).strip()

    if len(message) > MAX_LENGTH:
        message = message[: MAX_LENGTH - 1] + "…"

    return message


def values_for(doc) -> dict[str, str]:
    """Every placeholder, filled in from the document.

    `doc` is a Sales Order, Sales Invoice, Payment Entry or Delivery Note.
    They do not share a field for any of this, which is why every value below
    is asked for with .get() and falls back to an empty string: a placeholder
    that has no answer on this document comes out as nothing rather than as
    the literal brace.
    """
    amount, currency = money(doc)
    name = customer_name(doc)
    first, _sep, last = name.partition(" ")

    return {
        # ERPNext keeps one name where WooCommerce keeps two, so this is the
        # first word of it. For a company customer that is the first word of
        # the company name, which reads better than nothing and better than
        # "Dear Sir".
        "{first_name}": first or _("there"),
        "{last_name}": last,
        "{customer_name}": name,
        "{order_number}": doc.name or "",
        "{order_total}": fmt_money(amount, currency=currency) if amount is not None else "",
        "{order_date}": formatdate(doc.get("posting_date") or doc.get("transaction_date")),
        "{order_status}": _(doc.get("status")) if doc.get("status") else "",
        "{payment_method}": payment_method(doc),
        "{items}": items(doc),
        "{item_count}": item_count(doc),
        # The Company doctype is named after the company itself, so the link
        # value on the document already is the shop's name.
        "{shop_name}": doc.get("company") or "",
        "{order_url}": portal_url(doc),
        "{admin_url}": get_url_to_form(doc.doctype, doc.name),
    }


def customer_name(doc) -> str:
    """Who the document is for, however this doctype spells it."""
    return (
        doc.get("customer_name")
        or doc.get("party_name")
        or doc.get("customer")
        or doc.get("party")
        or ""
    )


def money(doc) -> tuple[float | None, str | None]:
    """The number a customer would recognise, and the currency it is in.

    A Payment Entry has no grand total: what the customer parted with is
    paid_amount, in the currency of the account it was paid from, and the
    received_amount beside it is the same money in the company's currency.

    Everywhere else the rounded total is preferred when there is one, because
    that is the figure printed on the document the customer is holding. Being
    told 1,200.40 for an invoice that says 1,200 starts a conversation nobody
    wanted.
    """
    if doc.doctype == "Payment Entry":
        return flt(doc.get("paid_amount")), doc.get("paid_from_account_currency")

    total = doc.get("grand_total")
    if doc.get("rounded_total") and not doc.get("disable_rounded_total"):
        total = doc.get("rounded_total")

    if total is None:
        return None, None
    return flt(total), doc.get("currency")


def payment_method(doc) -> str:
    """The mode of payment, where the document carries one.

    A Payment Entry names it outright. A Sales Invoice only has one when it
    was paid at the counter, and then it is in the payments table, which can
    hold several. A Sales Order or a Delivery Note has none at all.
    """
    if doc.get("mode_of_payment"):
        return doc.get("mode_of_payment")

    modes = []
    for row in doc.get("payments") or []:
        mode = row.get("mode_of_payment")
        if mode and mode not in modes:
            modes.append(mode)
    return ", ".join(modes)


def items(doc) -> str:
    """One line per row, as "2 x Blue shirt"."""
    lines: list[str] = []
    more = 0

    for row in doc.get("items") or []:
        if len(lines) >= MAX_ITEMS:
            more += 1
            continue
        lines.append(f"{quantity(row.get('qty'))} x {row.get('item_name') or row.get('item_code')}")

    if more:
        lines.append(_("and {0} more").format(more))

    return "\n".join(lines)


def item_count(doc) -> str:
    """How many things are on the document, counting quantities."""
    total = doc.get("total_qty")
    if total is None:
        total = sum(flt(row.get("qty")) for row in doc.get("items") or [])
    return quantity(total)


def quantity(value: Any) -> str:
    """A quantity as a person would write it.

    ERPNext keeps quantities as floats, so two shirts are 2.0 shirts. Nobody
    writes that, and a customer reading it wonders what the .0 means. A
    fractional quantity, which is real for anything sold by weight or length,
    keeps its decimals and loses the trailing zeros.
    """
    number = flt(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.3f}".rstrip("0").rstrip(".")


def portal_url(doc) -> str:
    """Where the customer can see this on your website, if they can at all.

    ERPNext's portal is behind a login: the link only opens for a customer who
    has a website user linked to their Contact. Most shops have none, which is
    why the field description tells them to leave {order_url} out.
    """
    route = PORTAL_ROUTES.get(doc.doctype)
    if not route:
        return ""
    return get_url(f"/{route}/{doc.name}")
