# Njiwa for Frappe

Settings, and one call to send a WhatsApp message. That is the whole app.

It adds no document events, no scheduled jobs and no buttons to your forms.
Deciding *when* a customer gets a message belongs in your own code, where you
can read it later and change it without waiting for us.

## Install

```bash
cd ~/frappe-bench
bench get-app https://github.com/Upeosoft-Limited/njiwa_frappe
bench --site yoursite.local install-app njiwa_frappe
```

This app is developed inside the Njiwa repository, at `packages/njiwa-frappe`,
and published here. To install from a local copy of that folder instead, do by
hand what `bench get-app` does with a clone:

```bash
cd ~/frappe-bench
cp -r /path/to/njiwa/packages/njiwa-frappe apps/njiwa_frappe
./env/bin/pip install -e apps/njiwa_frappe
grep -qx njiwa_frappe sites/apps.txt || echo njiwa_frappe >> sites/apps.txt
bench --site yoursite.local install-app njiwa_frappe
bench --site yoursite.local clear-cache
```

## Set it up

Open **Njiwa Settings** (type it in the search bar). Every field explains
itself on the form; in short:

| Field | What it is for |
| --- | --- |
| Send messages through Njiwa | The off switch. Off means sends fail loudly, not silently. |
| API key | From console.upeo.ai → API keys. `sk_test_` delivers nothing, `sk_live_` sends for real. |
| Njiwa address | Leave it alone unless you were given your own. |
| Send from | Which of your numbers sends, when the code does not say. Digits only, like 254712345678. |
| Wait for the result | Off. Turn it on only in a script you are watching. |

Save, then press **Test connection**. It reads the saved key and lists the
numbers the account actually has, so you find out now rather than at the
moment a customer should have been messaged.

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
