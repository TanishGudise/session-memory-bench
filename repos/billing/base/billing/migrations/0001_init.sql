CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT 'US'
);

CREATE TABLE invoices (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    issued TEXT NOT NULL,
    due TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    paid_cents INTEGER NOT NULL DEFAULT 0,
    plan TEXT NOT NULL DEFAULT ''
);

CREATE TABLE lines (
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    position INTEGER NOT NULL,
    description TEXT NOT NULL,
    cents INTEGER NOT NULL
);

CREATE TABLE payments (
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    cents INTEGER NOT NULL,
    charge_id TEXT NOT NULL
);

CREATE TABLE refunds (
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    cents INTEGER NOT NULL,
    refund_id TEXT NOT NULL
);
