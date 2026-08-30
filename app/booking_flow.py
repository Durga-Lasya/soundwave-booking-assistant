"""
booking_flow.py
----------------
Slot-filling state machine for the conversational booking flow:
  1. Track which required fields are known.
  2. Validate each field as it comes in (friendly error messages).
  3. Ask only for missing fields.
  4. Once complete: summarize + ask for explicit confirmation.
  5. Only the caller (chat_logic/main) persists to DB after "yes".
"""
import re
from datetime import datetime

REQUIRED_FIELDS = ["name", "email", "phone", "service", "date", "time"]

FIELD_QUESTIONS = {
    "name": "What name should I book this under?",
    "email": "What's the best email address for the confirmation?",
    "phone": "What's a good phone number to reach you?",
    "service": "Which type of session would you like to book (e.g. Vocal Recording, Podcast, Mixing & Mastering)?",
    "date": "What date works for you? (please use YYYY-MM-DD)",
    "time": "What time would you prefer? (e.g. 14:30 or 2:30 PM)",
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PHONE_RE = re.compile(r"^\+?[0-9\s\-()]{7,15}$")


def empty_state() -> dict:
    return {field: None for field in REQUIRED_FIELDS}


def missing_fields(state: dict) -> list:
    return [f for f in REQUIRED_FIELDS if not state.get(f)]


def validate_field(field: str, value: str):
    """Return (is_valid, cleaned_value_or_error_message)."""
    if value is None or str(value).strip() == "":
        return False, None

    value = str(value).strip()

    if field == "email":
        if not EMAIL_RE.match(value):
            return False, "That doesn't look like a valid email. Could you double-check it?"
        return True, value

    if field == "date":
        if not DATE_RE.match(value):
            return False, "Please enter the date as YYYY-MM-DD (e.g. 2026-09-15)."
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return False, "That date doesn't seem valid. Please use YYYY-MM-DD."
        if parsed.date() < datetime.now().date():
            return False, "That date is in the past — could you pick an upcoming date?"
        return True, value

    if field == "phone":
        if not PHONE_RE.match(value):
            return False, "That phone number doesn't look right. Please include 7-15 digits."
        return True, value

    # name, service, time — light validation only
    if len(value) < 1:
        return False, f"Could you provide your {field}?"
    return True, value


def update_state_with_extracted(state: dict, extracted: dict) -> list:
    """
    Merge freshly-extracted fields into the booking state.
    Returns a list of error messages for any invalid fields
    (those fields are left blank so the user is re-asked).
    """
    errors = []
    for field in REQUIRED_FIELDS:
        raw_value = extracted.get(field)
        if raw_value:
            is_valid, result = validate_field(field, raw_value)
            if is_valid:
                state[field] = result
            else:
                errors.append(result)
    return errors


def next_question(state: dict) -> str:
    missing = missing_fields(state)
    if not missing:
        return ""
    field = missing[0]
    return FIELD_QUESTIONS[field]


def build_summary(state: dict, business_name: str) -> str:
    return (
        f"Here's what I have for your booking at **{business_name}**:\n\n"
        f"- **Name:** {state['name']}\n"
        f"- **Email:** {state['email']}\n"
        f"- **Phone:** {state['phone']}\n"
        f"- **Session Type:** {state['service']}\n"
        f"- **Date:** {state['date']}\n"
        f"- **Time:** {state['time']}\n\n"
        f"Shall I go ahead and confirm this booking? (yes/no)"
    )


_POSITIVE = {"yes", "yeah", "yep", "yup", "confirm", "correct", "sure", "go ahead", "sounds good", "ok", "okay"}
_NEGATIVE = {"no", "nope", "not", "wrong", "change", "cancel", "incorrect"}


def interpret_confirmation(message: str):
    """Return True/False/None (unclear) for a yes/no confirmation message."""
    text = message.strip().lower()
    if any(word in text for word in _NEGATIVE):
        return False
    if any(word in text for word in _POSITIVE):
        return True
    return None
