"""
models.py
---------
SQL schema definitions for the booking assistant.
Two tables, matching the assignment's minimum schema:

customers: customer_id (PK), name, email, phone
bookings:  id (PK), customer_id (FK), booking_type, date, time, status, created_at
"""

CREATE_CUSTOMERS_TABLE = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT
);
"""

CREATE_BOOKINGS_TABLE = """
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    booking_type TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed',
    created_at TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);
"""
