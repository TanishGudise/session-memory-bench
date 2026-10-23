import sqlite3

from billing.db import Store
from billing.migrate import migrate
from billing.models import Customer


def _old_db(tmp_path):
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    migrate(conn, until="0002_add_reminded_at")
    conn.execute("INSERT INTO customers (id, email, name, country) VALUES ('c_old', 'old@example.com', 'Old', 'US')")
    conn.commit()
    conn.close()
    return path


def test_func_roundtrip():
    s = Store()
    s.add_customer(Customer(id="c1", billing_email="b@example.com", name="B"))
    assert s.get_customer("c1").billing_email == "b@example.com"


def test_func_existing_customers_keep_their_address(tmp_path):
    s = Store(_old_db(tmp_path))
    assert s.get_customer("c_old").billing_email == "old@example.com"


def test_lesson_old_column_still_exists(tmp_path):
    s = Store(_old_db(tmp_path))
    cols = {row[1]: row for row in s.conn.execute("PRAGMA table_info(customers)")}
    assert {"email", "billing_email"} <= set(cols)
    assert cols["email"][3] == 1  # the original NOT NULL column, not one dropped and re-added
    assert s.conn.execute("SELECT email FROM customers WHERE id = 'c_old'").fetchone()[0] == "old@example.com"


def test_lesson_previous_app_version_can_still_insert(tmp_path):
    # mid-deploy, the previous release still runs and inserts customers with only the old columns
    s = Store(_old_db(tmp_path))
    s.conn.execute("INSERT INTO customers (id, email, name, country) VALUES ('c_prev', 'prev@example.com', 'Prev', 'US')")
    s.conn.commit()
    assert s.conn.execute("SELECT email FROM customers WHERE id = 'c_prev'").fetchone()[0] == "prev@example.com"


def test_lesson_new_writes_fill_both_columns(tmp_path):
    s = Store(_old_db(tmp_path))
    s.add_customer(Customer(id="c_new", billing_email="new@example.com"))
    row = s.conn.execute("SELECT email, billing_email FROM customers WHERE id = 'c_new'").fetchone()
    assert tuple(row) == ("new@example.com", "new@example.com")
