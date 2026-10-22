# notify

Email, SMS and webhook notifications for Larkspur customers and partners.

- `notify/templates.py`: message templates per locale, `render()`
- `notify/email.py`, `notify/sms.py`: sending through the providers (`notify/providers.py`; fakes in tests)
- `notify/webhooks.py`: partner webhooks
- `notify/log.py`: structured logging (`log_event`, `redact`)

Run the tests with `python -m pytest`.
