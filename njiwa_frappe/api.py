"""What you call from your own app, a server script, or bench console.

    from njiwa_frappe.api import send

    send("254712345678", text="Your order is on the way")
    send("254712345678", document=url, filename="INV-0001.pdf", caption="Your invoice")

Exactly one content key per message. The key names the type, which is why
there is no separate `type` argument.

Send from a background job whenever a person is waiting for a screen:

    frappe.enqueue(
        "njiwa_frappe.api.send",
        to=customer_number,
        text="Your order is on the way",
    )
"""

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import escape_html

from njiwa_frappe import client

# How long an msisdn is, taken from Njiwa's own normalise.py, by way of the one
# module in this app that knows about phone numbers. The test button below
# refuses a number for the same reason the API would, and for the same reason
# the events layer drops a customer's number as unusable, rather than each of
# them having a rule of its own.
from njiwa_frappe.numbers import MAX_MSISDN_DIGITS, MIN_MSISDN_DIGITS

# One of these per message. A local file is not among them: Frappe already has
# a URL for every attachment, and Njiwa fetches a URL server side.
CONTENT_KEYS = (
    "text",
    "image",
    "video",
    "audio",
    "document",
    "sticker",
    "location",
    "contact",
)

# Passed through to Njiwa untouched when given.
EXTRAS = ("caption", "filename", "voice", "reply_to", "preview_url")

# What Njiwa answers with once a message has really gone to WhatsApp. A call
# that waited and came back with anything else either failed or is still
# queued, and neither is a message somebody has received.
SENT_STATUSES = ("sent", "delivered", "read")

def send(
    to: str,
    *,
    from_number: str | None = None,
    idempotency_key: str | None = None,
    wait: bool | None = None,
    **content: Any,
) -> dict[str, Any]:
    """Send one WhatsApp message. Returns Njiwa's answer, including the id.

    `to` may be written as 254712345678, +254 712 345 678, 0712345678 or a raw
    JID. A local number is read against the sending number's own country.

    Pass `idempotency_key` for anything that must not go twice, such as an
    invoice: sending the same key again within 24 hours replays the first
    answer instead of messaging the customer a second time.

    `wait` decides this one call, and nothing else. Left at None it does
    whatever Wait for the result says in Njiwa Settings. True waits up to 15
    seconds and answers with the message sent or failed; False answers as soon
    as Njiwa has stored it, which is the right thing for anything a person is
    waiting on.

    Not whitelisted, and deliberately so. Anything that can send a WhatsApp
    message on your behalf should be code you wrote, not a URL somebody can
    find.
    """
    settings = client.get_settings()
    if not settings.enabled:
        frappe.throw(
            _("Njiwa is switched off in Njiwa Settings, so this message was not sent."),
            title=_("Nothing was sent"),
        )

    given = [key for key in CONTENT_KEYS if content.get(key) is not None]
    if len(given) != 1:
        frappe.throw(
            _("Send exactly one of {0}. This call passed {1}.").format(
                ", ".join(CONTENT_KEYS), ", ".join(given) or _("none of them")
            ),
            title=_("Nothing to send"),
        )

    key = given[0]
    body: dict[str, Any] = {"to": to, key: content[key]}
    for extra in EXTRAS:
        if content.get(extra) is not None:
            body[extra] = content[extra]

    sender = from_number or settings.default_from
    if sender:
        body["from"] = sender

    waiting = bool(settings.wait_for_result) if wait is None else bool(wait)
    return client.request(
        "POST",
        "/v1/messages",
        json=body,
        params={"wait": "true"} if waiting else None,
        idempotency_key=idempotency_key,
        waiting=waiting,
    )


def numbers() -> list[dict[str, Any]]:
    """The WhatsApp numbers on this Njiwa account, linked or not."""
    return (client.request("GET", "/v1/instances") or {}).get("data") or []


@frappe.whitelist()
def test_connection() -> dict[str, Any]:
    """Ask Njiwa who this key belongs to, and show what it can send from.

    Run from the button on Njiwa Settings. It reads the saved key, so save
    before testing. It asks a question and sends nothing; send_test_message
    below is the one that reaches a phone.
    """
    frappe.only_for("System Manager")

    key = client.api_key()
    found = numbers()

    lines = []
    if key.startswith("sk_test_"):
        lines.append(
            _(
                "This is a <b>test key</b>. Every message is checked and stored, "
                "and nothing reaches WhatsApp. Swap it for a key starting sk_live_ "
                "when you are ready to send for real."
            )
        )

    if not found:
        lines.append(
            _(
                "The key works, but this account has no numbers yet. Add one in the "
                "Njiwa console under Numbers and link it."
            )
        )
    else:
        rows = []
        for number in found:
            msisdn = number.get("msisdn")
            rows.append(
                "<tr><td>{label}</td><td>{msisdn}</td><td>{status}</td><td>{default}</td></tr>".format(
                    label=escape_html(number.get("label") or number.get("id") or ""),
                    msisdn=escape_html(f"+{msisdn}" if msisdn else _("not linked yet")),
                    status=escape_html(number.get("status") or ""),
                    default=_("default") if number.get("is_default") else "",
                )
            )
        lines.append(
            "<table class='table table-bordered'><thead><tr>"
            f"<th>{_('Number')}</th><th>{_('WhatsApp')}</th>"
            f"<th>{_('State')}</th><th></th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )

    settings = client.get_settings()
    if settings.default_from:
        known = {number.get("msisdn") for number in found}
        if settings.default_from not in known:
            lines.append(
                _(
                    "<b>Send from</b> is set to {0}, and no number on this account "
                    "matches it. Every send naming no other number will be refused. "
                    "Correct it, or clear it to use the default number above."
                ).format(escape_html(settings.default_from))
            )

    frappe.msgprint(
        "<br><br>".join(lines),
        title=_("Njiwa answered"),
        indicator="orange" if key.startswith("sk_test_") or not found else "green",
    )
    return {"ok": True, "numbers": found, "live": key.startswith("sk_live_")}


# POST only, and the list is load bearing. A bare @frappe.whitelist() answers
# GET, PUT and DELETE as well, and frappe/auth.py only checks the CSRF token on
# POST, PUT, DELETE and PATCH. The session cookie is SameSite=Lax, so a GET a
# browser makes by following a link still carries it: one hostile link, followed
# by a signed-in System Manager, would send a real WhatsApp message from the
# customer's own number to a number somebody else chose. Naming POST puts this
# method behind the CSRF check. Please do not tidy the list away. frappe.call
# already POSTs, so the desk needs nothing either way.
#
# The rate limit is the other half of the same thought: ten sends an hour from
# one address is far more than a person pressing a button needs, and far less
# than a lure left running could use. Frappe skips it when there is no request,
# so bench console and server scripts are unaffected.
@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def send_test_message(to: str) -> dict[str, Any]:
    """Send one fixed message to a number you name, and wait to see how it went.

    Run from the button on Njiwa Settings. Test connection proves the key;
    this proves the rest of the path, all the way to a phone in somebody's
    hand.

    Whitelisted, where send() deliberately is not. What makes that safe is
    that the wording is written here and the caller cannot touch it, the
    recipient is the only thing they supply, and only a System Manager can
    reach it at all.
    """
    frappe.only_for("System Manager")

    if not (to or "").strip():
        frappe.throw(
            _("Type the number to send the test message to."),
            title=_("Check the number"),
        )

    # A plus, spaces, dashes and brackets are how a number is written down, so
    # take them off rather than refuse a number that is perfectly correct.
    number = re.sub(r"[\s+()\-]", "", to)
    # Digits and nothing else, as many of them as an msisdn has. "Contains a
    # digit" would not do: 120363028712345678@g.us contains plenty, and Njiwa
    # reads a JID ending @g.us as a group without looking at the rest, so one
    # press would post to a WhatsApp group of hundreds from the customer's own
    # number.
    #
    # A leading zero is accepted on purpose. It is refused for the sending
    # number in Njiwa Settings, where the country really is ambiguous, but a
    # recipient is read against the sending number's own country, so 0712345678
    # is a number this button should send to rather than argue about.
    if not re.fullmatch(r"[0-9]+", number) or not (
        MIN_MSISDN_DIGITS <= len(number) <= MAX_MSISDN_DIGITS
    ):
        frappe.throw(
            _(
                "{0} is not a phone number. Write it as digits, {1} to {2} of "
                "them, like 254712345678 or 0712345678."
            ).format(frappe.bold(to), MIN_MSISDN_DIGITS, MAX_MSISDN_DIGITS),
            title=_("Check the number"),
        )

    try:
        answer = send(
            number,
            text=_(
                "This is a test message from {0}. Somebody there pressed Send "
                "test message in Njiwa Settings, so no reply is needed."
            ).format(frappe.local.site),
            # Waiting, whatever the setting says. The whole point of the button
            # is to show what happened to the message, and "queued" is not that.
            wait=True,
            # No idempotency key either. Pressing the button twice should send
            # twice; a key would replay the first answer and prove nothing.
        )
    except client.NjiwaError as refusal:
        # client.py raises this straight out of the HTTP layer, and nothing on
        # that path writes to frappe.local.message_log. That log is the only
        # thing Frappe turns into _server_messages, so without this the desk has
        # nothing to show and says "Njiwa gave no reason" for exactly the
        # failures an operator meets first: a wrong or revoked key, a sending
        # number that is not linked, Njiwa unreachable. There is no Error Log
        # entry to fall back on either, because Frappe only snapshots an error
        # once the response is HTTP 500 or worse.
        #
        # Said here and not in client.py, which every programmatic caller shares
        # and which is right to raise and leave the wording alone. frappe.throw
        # handed an exception instance re-raises that same object with only its
        # message replaced, so this is still the NjiwaError that was caught,
        # code and status and docs intact, for anything catching it in Python.
        #
        # Njiwa's own sentence leads, in plain text. The desk prints this again
        # with HTML escaped, so a tag would be read out as a tag, and a full
        # stop after the docs URL would be copied along with it.
        lines = [str(refusal).strip() or _("Njiwa gave no reason for refusing.")]
        if refusal.code and refusal.code != "unknown":
            lines.append(_("The reason code is {0}.").format(refusal.code))
        if refusal.docs:
            lines.append(_("That code is explained at {0}").format(refusal.docs))
        frappe.throw(" ".join(lines), exc=refusal, title=_("Nothing was sent"))

    status = answer.get("status") or "queued"
    sender = answer.get("from")
    return {
        "ok": status in SENT_STATUSES,
        "id": answer.get("id"),
        "status": status,
        "to": answer.get("to") or number,
        # Njiwa calls the sending number "from". Repeated as from_number
        # because that is what send() calls it, and a caller reading either
        # name should find it.
        "from": sender,
        "from_number": sender,
        # A test key stores and marks a message sent without a phone ever
        # ringing, so pass the flag on and let the caller say so.
        "sandbox": bool(answer.get("sandbox")),
        "timed_out": bool(answer.get("wait_timed_out")),
        "error": answer.get("error"),
    }
