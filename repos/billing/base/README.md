# billing

Invoices, payments and refunds for Larkspur subscriptions. Money is integer cents.

- `billing/db.py`: SQLite store (`Store`), schema in `billing/migrations/`
- `billing/gateway.py`: card gateway client (`FakeGateway` in tests)
- `billing/payments.py`: collecting invoices
- `billing/tax.py`, `billing/settlement.py`, `billing/reports.py`

Run the tests with `python -m pytest`.
