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

from typing import Any

import frappe
from frappe import _
from frappe.utils import escape_html

from njiwa_frappe import client

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


def send(
    to: str,
    *,
    from_number: str | None = None,
    idempotency_key: str | None = None,
    **content: Any,
) -> dict[str, Any]:
    """Send one WhatsApp message. Returns Njiwa's answer, including the id.

    `to` may be written as 254712345678, +254 712 345 678, 0712345678 or a raw
    JID. A local number is read against the sending number's own country.

    Pass `idempotency_key` for anything that must not go twice, such as an
    invoice: sending the same key again within 24 hours replays the first
    answer instead of messaging the customer a second time.

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

    waiting = bool(settings.wait_for_result)
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
    before testing.
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
