app_name = "njiwa_frappe"
app_title = "Njiwa"
app_publisher = "UPEO.AI"
app_description = "WhatsApp messaging for Frappe and ERPNext, through Njiwa."
app_email = "hello@upeo.ai"
app_license = "MIT"

# Deliberately nothing else. No document events, no scheduled jobs, no
# overrides: this app holds the settings and gets out of the way. Anything
# that decides *when* to message a customer belongs in your own app or a
# server script, where you can read it later.
