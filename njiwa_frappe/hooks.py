app_name = "njiwa_frappe"
app_title = "Njiwa"
app_publisher = "UPEO.AI"
app_description = "WhatsApp messaging for Frappe and ERPNext, through Njiwa."
app_email = "hello@upeo.ai"
app_license = "MIT"

# The Njiwa icon on the /apps screen, and the workspace it opens. Frappe asks
# has_permission before it draws the icon and again while it builds every desk
# boot, so that function lives in its own module and answers from roles alone.
add_to_apps_screen = [
    {
        "name": app_name,
        "logo": "/assets/njiwa_frappe/images/njiwa-app-icon.svg",
        "title": app_title,
        "route": "/desk/njiwa",
        "has_permission": "njiwa_frappe.desk.check_app_permission",
    }
]

# The route has to be spelled /desk/njiwa, and not the /app/njiwa that frappe
# redirects to the very same workspace. Frappe picks where to send a user after
# login by testing every installed app's route against ^/desk(/.*)?$, and a
# single route that fails sends everyone to the /apps chooser instead of the
# desk they expect. On a bench this app shares with other apps, one careless
# spelling here is a regression in all of them, so leave this as /desk.

# app_logo_url is left unset on purpose. The logo above already stands in for
# it wherever the desk and the About dialog look for one, and setting the hook
# as well enters this app's mark in the running for the site's own navbar
# brand, which is not ours to take. app_icon is read nowhere in v16, and
# app_color only tints the letter the About dialog falls back to for an app
# that has no logo, which this one has.

# Both of these do one thing: point sites/assets/njiwa_frappe at this app's
# public folder, so the icon above resolves instead of 404ing. An app copied
# into a bench by hand never gets the `bench build` that would have made that
# link. after_install covers a site the app is installed on from here on;
# after_migrate covers the sites where it is installed already and install-app
# will never run again. Both also copy the standard wording into any message
# box that has never been set, because Frappe only fills a field's default in
# when the document is first created and Njiwa Settings on an existing site was
# created before those fields existed. The work is idempotent, and it leaves a
# real directory of that name and an edited message alone, so running it on
# every migrate is safe.
after_install = "njiwa_frappe.install.after_install"
after_migrate = "njiwa_frappe.install.after_migrate"

# The moments this app can message a customer about.
#
# These are ERPNext's own submit and cancel moments, and nothing else. There is
# deliberately no on_update or after_save anywhere below: those fire when
# somebody corrects an address, and a customer who gets a WhatsApp message
# because a clerk fixed a postcode learns to ignore all of them.
#
# Every one of these events is off until somebody turns it on in Njiwa
# Settings, and this file is not where that is decided. njiwa_frappe.events
# reads the settings, works out whether this particular moment is one anybody
# asked to be told about, and in almost every case answers no and returns. On a
# site that has switched nothing on, the only cost of these hooks is one cached
# settings read per submit.
#
# Nothing here can stop a document being submitted or cancelled. Everything
# events.py does at this moment is wrapped, the send itself happens on a
# background worker, and the job is only queued once the transaction has
# committed. A shop must never be unable to invoice because WhatsApp is slow.
#
# api.send is untouched by any of this. Code that would rather decide for
# itself when a customer hears from you still calls it and ignores every
# setting on the Events tab.
doc_events = {
    "Sales Order": {
        "on_submit": "njiwa_frappe.events.on_submit",
        "on_cancel": "njiwa_frappe.events.on_cancel",
    },
    "Sales Invoice": {
        "on_submit": "njiwa_frappe.events.on_submit",
        "on_cancel": "njiwa_frappe.events.on_cancel",
    },
    "Payment Entry": {
        "on_submit": "njiwa_frappe.events.on_submit",
        "on_cancel": "njiwa_frappe.events.on_cancel",
    },
    "Delivery Note": {
        "on_submit": "njiwa_frappe.events.on_submit",
        "on_cancel": "njiwa_frappe.events.on_cancel",
    },
}

# There are still no scheduled jobs and no overrides. This app watches four
# doctypes at two moments each, sends what the settings tell it to send, and
# touches nothing else in your data.
