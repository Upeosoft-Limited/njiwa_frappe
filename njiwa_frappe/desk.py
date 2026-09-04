"""What the desk asks before it shows this app.

Frappe calls the function named in `add_to_apps_screen` with no arguments,
once while it builds the /apps screen and again while it builds every desk
boot. The /apps call is wrapped in a try; the boot call is not. Anything
raised here would therefore stop the desk loading for everyone on the bench,
including the apps that have nothing to do with Njiwa, so this answers from
roles alone and touches nothing that can be missing.
"""

from __future__ import annotations

import frappe


def check_app_permission() -> bool:
    """True for the people who can open Njiwa Settings, and nobody else.

    Njiwa Settings gives read and write to System Manager and to no other
    role, so the icon follows the same rule. An icon that opens a page the
    person is then refused is worse than no icon at all.

    Administrator passes on its own name rather than through its roles,
    because a site is repaired from that account on the days when the roles
    are the thing that went wrong.
    """
    session = getattr(frappe.local, "session", None)
    user = session.user if session else None

    # No session at all, or the signed-out visitor Frappe calls Guest. The
    # apps screen is behind a login, but boot runs in more places than that.
    if not user or user == "Guest":
        return False

    if user == "Administrator":
        return True

    return "System Manager" in frappe.get_roles(user)
