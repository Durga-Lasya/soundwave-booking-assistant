"""
admin_dashboard.py
-------------------
Mandatory admin UI: view all stored bookings, with optional
filter/search by name, email, or date.
"""
import streamlit as st
import pandas as pd

from db import database


def render_admin_dashboard():
    st.title("📋 Admin Dashboard")
    st.caption("View and filter all bookings stored in the database.")

    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            name_filter = st.text_input("Filter by name")
        with col2:
            email_filter = st.text_input("Filter by email")
        with col3:
            date_filter = st.text_input("Filter by date (YYYY-MM-DD)")

    try:
        bookings = database.fetch_all_bookings(
            name=name_filter, email=email_filter, date=date_filter
        )
    except Exception as e:
        st.error(f"Could not load bookings: {e}")
        return

    if not bookings:
        st.info("No bookings found matching these filters.")
        return

    df = pd.DataFrame(bookings)
    df = df.rename(columns={
        "id": "Booking ID",
        "name": "Customer",
        "email": "Email",
        "phone": "Phone",
        "booking_type": "Session Type",
        "date": "Date",
        "time": "Time",
        "status": "Status",
        "created_at": "Created At",
    })
    column_order = ["Booking ID", "Customer", "Email", "Phone", "Service",
                     "Date", "Time", "Status", "Created At"]
    df = df[[c for c in column_order if c in df.columns]]

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Total bookings shown: {len(df)}")

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Export as CSV", data=csv, file_name="bookings_export.csv", mime="text/csv")
