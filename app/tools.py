"""
tools.py
--------
The three required tools, each with a clear input -> output contract:

1. rag_tool(query)            -> retrieved answer (str)
2. booking_persistence_tool() -> (success, booking_id, error)
3. email_tool()                -> (success, error)

Keeping these as standalone functions makes it easy to route them
through an agent framework (LangChain tools / CrewAI) later if desired.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import config
from app.chat_logic import general_chat_response
from app.rag_pipeline import get_relevant_chunks
from db import database


def rag_tool(llm, vectorstore, query: str, history_messages: list) -> str:
    """Input: query (+ short-term memory). Output: retrieved/blended answer."""
    chunks = get_relevant_chunks(vectorstore, query) if vectorstore else []
    return general_chat_response(llm, history_messages, chunks)


def booking_persistence_tool(payload: dict):
    """
    Input: structured booking payload (name, email, phone, service, date, time).
    Output: (success: bool, booking_id: int|None, error: str|None)
    """
    try:
        customer_id = database.insert_customer(
            name=payload["name"], email=payload["email"], phone=payload["phone"]
        )
        booking_id = database.insert_booking(
            customer_id=customer_id,
            booking_type=payload["service"],
            date=payload["date"],
            time=payload["time"],
        )
        return True, booking_id, None
    except Exception as e:
        return False, None, f"Could not save booking to the database: {e}"


def email_tool(to_email: str, subject: str, body: str):
    """
    Input: to_email, subject, body.
    Output: (success: bool, error: str|None)
    """
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        return False, "Email is not configured (missing SMTP credentials)."

    try:
        msg = MIMEMultipart()
        msg["From"] = config.FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        return True, None
    except Exception as e:
        return False, f"Email delivery failed: {e}"


def build_confirmation_email(booking_state: dict, booking_id: int) -> tuple:
    """Build (subject, body) for the booking confirmation email."""
    subject = f"Booking Confirmed – {config.BUSINESS_NAME} (#{booking_id})"
    body = (
        f"Hi {booking_state['name']},\n\n"
        f"Your session at {config.BUSINESS_NAME} is confirmed!\n\n"
        f"Booking ID: {booking_id}\n"
        f"Session Type: {booking_state['service']}\n"
        f"Date: {booking_state['date']}\n"
        f"Time: {booking_state['time']}\n\n"
        f"Phone on file: {booking_state['phone']}\n\n"
        f"We look forward to seeing you in the studio!\n"
        f"— {config.BUSINESS_NAME}"
    )
    return subject, body
