"""
database.py
-----------
SQLite persistence layer. Handles connecting, initializing tables,
inserting customers/bookings, and fetching bookings for the admin
dashboard (with optional filters).

Note: on Streamlit Cloud, the SQLite file lives on ephemeral storage
and may reset when the app restarts/redeploys. That's acceptable for
this assignment (see problem statement, section 6.1). For real
persistence, swap this module for a Supabase client with the same
function signatures.
"""
import sqlite3
from datetime import datetime
from contextlib import contextmanager

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import config
from db.models import CREATE_CUSTOMERS_TABLE, CREATE_BOOKINGS_TABLE


@contextmanager
def get_connection():
    """Yield a SQLite connection with row access by column name."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create tables if they don't already exist. Safe to call every run."""
    with get_connection() as conn:
        conn.execute(CREATE_CUSTOMERS_TABLE)
        conn.execute(CREATE_BOOKINGS_TABLE)
        conn.commit()


def find_customer_by_email(email: str):
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM customers WHERE email = ?", (email,))
        row = cur.fetchone()
        return dict(row) if row else None


def insert_customer(name: str, email: str, phone: str) -> int:
    """Insert a customer, or reuse an existing record with the same email."""
    existing = find_customer_by_email(email)
    if existing:
        # Keep details fresh in case name/phone changed.
        with get_connection() as conn:
            conn.execute(
                "UPDATE customers SET name = ?, phone = ? WHERE customer_id = ?",
                (name, phone, existing["customer_id"]),
            )
            conn.commit()
        return existing["customer_id"]

    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO customers (name, email, phone) VALUES (?, ?, ?)",
            (name, email, phone),
        )
        conn.commit()
        return cur.lastrowid


def insert_booking(customer_id: int, booking_type: str, date: str, time: str,
                    status: str = "confirmed") -> int:
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO bookings (customer_id, booking_type, date, time, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (customer_id, booking_type, date, time, status, created_at),
        )
        conn.commit()
        return cur.lastrowid


def fetch_all_bookings(name: str = "", email: str = "", date: str = ""):
    """Return bookings joined with customer info, optionally filtered."""
    query = """
        SELECT b.id, b.booking_type, b.date, b.time, b.status, b.created_at,
               c.name, c.email, c.phone
        FROM bookings b
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE 1=1
    """
    params = []
    if name:
        query += " AND c.name LIKE ?"
        params.append(f"%{name}%")
    if email:
        query += " AND c.email LIKE ?"
        params.append(f"%{email}%")
    if date:
        query += " AND b.date = ?"
        params.append(date)
    query += " ORDER BY b.created_at DESC"

    with get_connection() as conn:
        cur = conn.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
