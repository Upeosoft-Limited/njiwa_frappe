# Njiwa for Frappe

Ready-made moments to WhatsApp your customers on, and one call to send anything
else yourself.

The app watches four doctypes at two moments each - Sales Order, Sales Invoice,
Payment Entry and Delivery Note, on submit and on cancel - and turns them into
ten events you can switch on one at a time:

| Event | Sent when |
| --- | --- |
| Order confirmed | A Sales Order is submitted |
| Order cancelled | A Sales Order is cancelled |
| Invoice issued | A Sales Invoice is submitted |
| Invoice cancelled | A Sales Invoice is cancelled |
| Credit note issued | A Sales Invoice marked as a return is submitted |
| Payment received | A Payment Entry is submitted |
| Payment cancelled | A Payment Entry is cancelled |
| Goods on their way | A Delivery Note is submitted |
| Delivery cancelled | A Delivery Note is cancelled |
| Tell me about new orders | A Sales Order is submitted, to your own number |

**Every one of them is off until you turn it on**, so installing the app sends
nothing to anybody. Each has a box of wording you can edit, and clearing that
box turns one message off while leaving the event alone. Nothing is sent while
you import, migrate, patch or run tests.

There are still no scheduled jobs and no buttons added to your forms. For any
moment the ten do not cover, your own code sends it: one import and one call,
which belongs in a background job whenever somebody is waiting for a screen.

## Install

```bash
cd ~/frappe-bench
bench get-app https://github.com/Upeosoft-Limited/njiwa_frappe
bench --site yoursite.local install-app njiwa_frappe
```

The repository is private, so this works for a bench whose machine has a key
that can read it. Over anonymous HTTPS the same address answers 404, which
looks exactly like a repository that does not exist; if `bench get-app` gives
you that, the access is what to check, not the address.

This app is developed inside the Njiwa repository at `packages/njiwa-frappe`
and published to that repository. To install from a local copy of the folder
instead, do to it by hand what `bench get-app` does to a clone:

```bash
cd ~/frappe-bench
cp -r /path/to/njiwa/packages/njiwa-frappe apps/njiwa_frappe
./env/bin/pip install -e apps/njiwa_frappe
grep -qx njiwa_frappe sites/apps.txt || echo njiwa_frappe >> sites/apps.txt
bench build --app njiwa_frappe
bench --site yoursite.local install-app njiwa_frappe
bench --site yoursite.local clear-cache
```

`bench build` is the line a copied folder needs and a clone would have got for
free. It is what puts the app's images, the desk icon among them, under
`/assets/njiwa_frappe/`.

## Upgrade

A site that already has Njiwa does not install it again. Running `install-app`
there is not dangerous, but it does nothing whatever: Frappe answers `App
njiwa_frappe already installed` and stops, leaving the version you just copied
in unmigrated and the version you replaced still running. Use this instead:

```bash
cd ~/frappe-bench
rm -rf apps/njiwa_frappe/njiwa_frappe
cp -r /path/to/njiwa/packages/njiwa-frappe/. apps/njiwa_frappe/
bench --site yoursite.local migrate
bench --site yoursite.local clear-cache
bench restart
```

The `rm -rf` takes out only the Python package inside the app folder, so a file
that has gone away upstream goes away here too rather than lingering. The folder
itself stays, and with it the editable install `pip` made the first time. That
install points at the path and not at the files, so `pip` does not need to run
again unless the app has taken on a dependency, and this one has none. The
trailing `/.` in the `cp` line is what copies the contents in rather than
nesting the folder inside itself.

`bench migrate` is the line that applies the new version. It syncs the doctype,
so a field added or renamed since your last deploy reaches the database, and it
runs this app's `after_migrate` hook, which points `sites/assets/njiwa_frappe`
back at the app's `public` folder. That link is the icon, and an upgrade needs
it made again for the same reason a first install does.

If the icon is missing afterwards, that link is the thing to check, and either
of these makes it without reinstalling anything:

```bash
bench --site yoursite.local execute njiwa_frappe.install.link_assets
bench build --app njiwa_frappe
```

The first does only that one thing and says what it did. The second is the
ordinary route and makes the same link on its way past, but it also runs the
whole asset build through node and yarn, which is a good deal of work for one
symlink on a bench shared with other apps.

`clear-cache` is for what the desk has already cached about the app, the
workspace and the settings form among it. `bench restart` is because Python
that is loaded stays loaded: until the web and worker processes come back, they
are still running the code you replaced.

## Set it up

Njiwa has an icon on the **/apps** screen, and it opens the **Njiwa**
workspace at `/app/njiwa`. **Njiwa Settings** is a shortcut on that workspace,
and it is still in the awesome bar if you would rather type it. Both the icon
and the workspace are shown only to the role that can open Njiwa Settings,
which is System Manager. An icon that opens a page you are then refused is
worse than no icon.

Every field explains itself on the form; in short:

| Field | What it is for |
| --- | --- |
| Send messages through Njiwa | The off switch. Off means sends fail loudly, not silently. |
| API key | From console.upeo.ai → API keys. `sk_test_` delivers nothing, `sk_live_` sends for real. |
| Njiwa address | Leave it alone unless you were given your own. |
| Send from | Which of your numbers sends, when the code does not say. Digits only, like 254712345678. |
| Wait for the result | Off. Turn it on only in a script you are watching. |

Save, then confirm it twice. Both buttons read the saved settings, so save
first or they will tell you to.

**Test connection** proves the key. It reads the saved key and lists the
numbers the account actually has, so you find out now rather than at the
moment a customer should have been messaged. It asks a question and sends
nothing.

**Send test message** proves the rest of the way, as far as a phone in
somebody's hand. Give it a number written however you have it, be that
254712345678, +254 712 345 678 or 0712345678, and it sends one short fixed
message and waits for Njiwa to finish rather than answering "queued". What
comes back is the real outcome: the message id, the status, and which of your
numbers it went from. You cannot choose the wording, and the send carries no
idempotency key, so pressing Send twice sends twice.

The button takes digits and nothing else. Spaces, a leading plus, dashes and
brackets come off, and what is left has to be between 7 and 15 digits. A
leading zero is fine here, because a recipient is read against the sending
number's own country. A raw JID is the one thing this button refuses, where
`send()` still accepts one: a JID ending `@g.us` is a group, and a press meant
for one person would post to a group of hundreds.

With a key beginning `sk_live_` that is a real WhatsApp message. It reaches
the handset, the person holding it will read it, and it costs whatever a
message costs. Send it to your own number.

Start with a test key. Everything works, every message is stored, and nothing
reaches a real phone until you swap the key.

## Send

```python
from njiwa_frappe.api import send

send("254712345678", text="Your order is on the way")
```

`to` can be written however you have it: `254712345678`, `+254 712 345 678`,
`0712345678` or a raw JID. A local number is read against the sending number's
own country.

One content key per message. The key names the type:

```python
send(to, text="Hello")
send(to, image="https://example.com/photo.jpg", caption="Your item")
send(to, document=invoice_url, filename="INV-0001.pdf", caption="Your invoice")
send(to, location={"lat": -1.29, "lng": 36.82, "name": "UPEO.AI"})
```

An ERPNext attachment is already a URL, so it goes straight through:

```python
file_url = frappe.db.get_value("File", {"attached_to_name": doc.name}, "file_url")
send(customer_number, document=frappe.utils.get_url(file_url), filename="INV-0001.pdf")
```

Pass `wait=True` to hold the call until the message is sent or failed, or
`wait=False` to answer as soon as Njiwa has stored it. Left alone it does
whatever **Wait for the result** says in the settings, which is what you want
almost every time.

### From a document event

Send from a background job when somebody is waiting for a screen. Njiwa is
quick, but the internet is not, and a save should not depend on it:

```python
# hooks.py in your own app
doc_events = {
    "Sales Invoice": {"on_submit": "your_app.whatsapp.notify"}
}

# your_app/whatsapp.py
import frappe

def notify(doc, method=None):
    number = frappe.db.get_value("Customer", doc.customer, "mobile_no")
    if not number:
        return
    frappe.enqueue(
        "njiwa_frappe.api.send",
        queue="short",
        to=number,
        text=f"Invoice {doc.name} for {doc.grand_total} is ready.",
        idempotency_key=f"invoice-{doc.name}",
    )
```

That `idempotency_key` is the difference between a customer getting one
invoice and getting three. Njiwa honours it for 24 hours: the same key sent
again replays the first answer instead of sending a second message. Use it on
anything a retry could duplicate.

### When something goes wrong

```python
from njiwa_frappe.client import NjiwaError

try:
    send(number, text="...")
except NjiwaError as error:
    frappe.log_error(f"{error.code}: {error}", "Njiwa")
```

`error.code` is stable and worth branching on; the wording is not. Every code
has a page: https://docs.njiwa.upeo.ai/errors/

## What this app does not do

**It does not receive.** Incoming WhatsApp messages and delivery receipts
arrive as webhooks, and verifying one needs the signing secret for that
number. The console does not yet show that secret, so an honest receiving
feature is not something this app can ship today. When it does, it lands here.

**It does not store messages in Frappe.** Njiwa already keeps every message,
its status and its failure reason, visible in the console. A second copy in
your database is a second thing to keep in step.

---

Docs: https://docs.njiwa.upeo.ai · Console: https://console.upeo.ai
UPEO.AI · hello@upeo.ai · 0116888777 on WhatsApp
