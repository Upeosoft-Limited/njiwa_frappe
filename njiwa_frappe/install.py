"""Run when the app is installed on a site, and again on every migrate.

Two things happen here, and both exist because of something that would
otherwise be missing without anybody being told.

The first is the asset link. `bench get-app` runs `bench build` for you, and
`bench build` is what points `sites/assets/<app>` at the app's `public` folder.
An app copied into a bench by hand never gets that step, and nothing complains:
the install succeeds, the doctype appears, and the only symptom is a broken
image where the Njiwa icon should be on the /apps screen, because
`/assets/njiwa_frappe/images/njiwa-app-icon.svg` is a 404. So the app makes its
own link, and an install by any route ends up with the icon.

The second is the wording of the ready-made messages. Frappe fills a field's
default in when a document is first created, and Njiwa Settings on a site that
already had this app was created long before the message fields existed. Those
fields would arrive empty, and an empty message sends nothing, so a shop that
ticked an event would get silence and no reason for it. The defaults are copied
in here instead.
"""

from __future__ import annotations

import os

import frappe

APP = "njiwa_frappe"
SETTINGS = "Njiwa Settings"


def after_install() -> None:
    link_assets()
    seed_default_messages()


def after_migrate() -> None:
    """Both jobs, on every migrate.

    Neither one is a migration in its own right, so neither belongs in
    patches.txt: a patch runs once and is then marked done for ever, and both
    of these want running again after an upgrade adds a new event or a bench
    build is skipped.
    """
    link_assets()
    seed_default_messages()


def link_assets() -> str:
    """Point sites/assets/njiwa_frappe at this app's public folder.

    Safe to run again: an existing, correct link is left alone. Returns a line
    saying what it did, so this is worth running by hand when an icon has gone
    missing:

        bench --site yoursite.local execute njiwa_frappe.install.link_assets
    """
    source = frappe.get_app_path(APP, "public")
    target = os.path.join(frappe.local.sites_path, "assets", APP)

    if not os.path.isdir(source):
        return f"{source} does not exist, so there is nothing to link."

    os.makedirs(os.path.dirname(target), exist_ok=True)

    if os.path.islink(target):
        if os.path.realpath(target) == os.path.realpath(source):
            return f"{target} already points at {source}."
        # Ours to correct: a link of this name is only ever this app's.
        os.unlink(target)
    elif os.path.exists(target):
        # A real directory here was put there by something other than us.
        # Replacing it would throw away whatever that was.
        return f"{target} is a real directory, not a link, so it was left alone."

    try:
        os.symlink(source, target)
    except OSError as error:
        # A missing icon is a blemish. An install that dies half way through
        # because of one is a great deal worse, so this is reported, not raised.
        frappe.log_error(f"Could not link {target} to {source}: {error}", "Njiwa")
        return f"Could not link {target}. The Njiwa icon will not load until it is linked."

    return f"Linked {target} to {source}."


def seed_default_messages() -> str:
    """Put the standard wording in every message box that has never been set.

    Only ever writes a box that is missing altogether. A box somebody has
    edited keeps their words, and a box somebody has deliberately emptied
    stays empty, because emptying it is how a shop turns one message off
    without turning the event off. Once Njiwa Settings has been saved every
    box exists, so from that point on this does nothing at all.

    Safe to run again, and safe to run on a site where the events have not
    been switched on, which is every site until somebody switches one on.
    """
    from njiwa_frappe.templates import DEFAULTS

    try:
        saved = frappe.db.get_singles_dict(SETTINGS)
    except Exception as error:
        # A missing table means the doctype has not synced yet, which happens
        # if this is called before migrate rather than after it. Wording that
        # is not there yet is a blemish; an install that dies over one is a
        # great deal worse.
        frappe.log_error(title="Njiwa could not read its settings", message=str(error))
        return "Njiwa Settings could not be read, so no wording was written."

    missing = {
        f"message_{event}": wording
        for event, wording in DEFAULTS.items()
        if f"message_{event}" not in saved
    }
    if not missing:
        return "Every Njiwa message already has wording. Nothing was changed."

    # One call rather than one per field: set_single_value takes the whole
    # dictionary, and each call rewrites the modified stamp and clears the
    # document cache.
    frappe.db.set_single_value(SETTINGS, missing)
    return f"Wrote the standard wording into {len(missing)} Njiwa message(s): {', '.join(sorted(missing))}."
