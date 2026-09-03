"""Talking to Njiwa over HTTP. Transport only.

Nothing in here decides when to message anybody. It reads the settings, makes
the call, and turns a refusal into an exception a Frappe user can read.
"""

from __future__ import annotations

from typing import Any

import frappe
import requests
from frappe import _

from njiwa_frappe import __version__

SETTINGS = "Njiwa Settings"
DEFAULT_BASE_URL = "https://njiwa.upeo.ai"

# Long enough for an upload on a slow line, short enough that a stuck request
# does not hold a worker for ever. `?wait=true` blocks for up to 15 seconds on
# Njiwa's side, so a waiting call needs a longer rope than an ordinary one or
# the timeout here would fire before the answer arrives.
TIMEOUT_SECONDS = 30
WAITING_TIMEOUT_SECONDS = 45


class NjiwaError(frappe.ValidationError):
    """Anything Njiwa refused, or could not be asked.

    `code` is the stable, machine readable reason and is the thing to branch
    on. The wording of the message can change; the code does not. `docs` is a
    page explaining that exact code.
    """

    def __init__(
        self,
        message: str,
        code: str = "unknown",
        status: int = 0,
        docs: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.docs = docs


def get_settings():
    """The single settings document. Cached, so this is cheap to call."""
    return frappe.get_cached_doc(SETTINGS)


def base_url(settings=None) -> str:
    settings = settings or get_settings()
    return (settings.base_url or DEFAULT_BASE_URL).rstrip("/")


def api_key(settings=None) -> str:
    settings = settings or get_settings()
    key = settings.get_password("api_key", raise_exception=False)
    if not key:
        frappe.throw(
            _("There is no API key in Njiwa Settings, so nothing can be sent."),
            title=_("Njiwa is not set up yet"),
        )
    return key


def request(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    waiting: bool = False,
) -> Any:
    settings = get_settings()
    address = base_url(settings)

    headers = {
        "Authorization": f"Bearer {api_key(settings)}",
        "User-Agent": f"njiwa-frappe/{__version__}",
    }
    # Sent on anything that must not happen twice. Njiwa honours it for 24
    # hours: the same key with the same body replays the first answer instead
    # of sending a second message.
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    try:
        response = requests.request(
            method,
            f"{address}{path}",
            headers=headers,
            json=json,
            data=data,
            files=files,
            params=params,
            timeout=WAITING_TIMEOUT_SECONDS if waiting else TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        # A network failure is not a send failure. The message was never
        # accepted, so it is safe to try again.
        raise NjiwaError(
            _("Could not reach Njiwa at {0}. {1}").format(address, exc),
            code="connection_failed",
        ) from exc

    if response.status_code == 204:
        return None

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code >= 400:
        error = payload.get("error") or {} if isinstance(payload, dict) else {}
        raise NjiwaError(
            error.get("message")
            or _("Njiwa answered with HTTP {0}.").format(response.status_code),
            code=error.get("code") or "unknown",
            status=response.status_code,
            docs=error.get("docs"),
        )

    return payload
