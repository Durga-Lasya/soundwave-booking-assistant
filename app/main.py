"""
main.py
-------
Streamlit entry point. Wires together:
  - Chat interface (st.chat_message / st.chat_input)
  - PDF upload -> RAG pipeline
  - Intent detection -> booking flow (slot filling -> confirm -> persist -> email)
  - Mandatory Admin Dashboard

Run with:  streamlit run app/main.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

from app import config
from app.chat_logic import get_llm, classify_and_extract, trim_memory
from app.booking_flow import (
    empty_state, update_state_with_extracted, missing_fields,
    next_question, build_summary, interpret_confirmation,
)
from app.tools import rag_tool, booking_persistence_tool, email_tool, build_confirmation_email
from app.rag_pipeline import build_vectorstore
from app.admin_dashboard import render_admin_dashboard
from db.database import init_db


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def cached_llm():
    return get_llm()


def init_session_state():
    defaults = {
        "messages": [],
        "booking_state": empty_state(),
        "awaiting_confirmation": False,
        "vectorstore": None,
        "vectorstore_files": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ---------------------------------------------------------------------------
# Core message handling
# ---------------------------------------------------------------------------
def handle_user_message(prompt: str) -> str:
    try:
        llm = cached_llm()
    except Exception as e:
        return f"⚠️ Configuration error: {e}"

    state = st.session_state.booking_state

    # --- Awaiting yes/no confirmation on a completed booking ---
    if st.session_state.awaiting_confirmation:
        confirmed = interpret_confirmation(prompt)

        if confirmed is True:
            success, booking_id, err = booking_persistence_tool(state)
            if not success:
                st.session_state.awaiting_confirmation = False
                return f"❌ Sorry, I couldn't save your booking: {err}"

            subject, body = build_confirmation_email(state, booking_id)
            email_ok, email_err = email_tool(state["email"], subject, body)

            response = f"🎉 Booking confirmed! Your booking ID is **{booking_id}**."
            if email_ok:
                response += " A confirmation email is on its way."
                st.success("✅ Booking saved and confirmation email sent.")
            else:
                response += f"\n\n_Email could not be sent, but your booking was saved._ ({email_err})"
                st.warning(f"Email could not be sent, but booking was saved. ({email_err})")

            st.session_state.booking_state = empty_state()
            st.session_state.awaiting_confirmation = False
            return response

        if confirmed is False:
            st.session_state.awaiting_confirmation = False
            return ("No problem — which detail would you like to change, and to what? "
                    "(e.g. \"change the date to 2026-09-20\")")

        return "Sorry, I didn't quite catch that — should I go ahead and confirm the booking? (yes/no)"

    # --- Classify intent + extract any mentioned booking fields ---
    result = classify_and_extract(llm, prompt, state)
    intent = result.get("intent", "general")
    booking_in_progress = any(state.values())

    if intent == "booking" or booking_in_progress:
        errors = update_state_with_extracted(state, result)
        for err in errors:
            st.warning(err)

        missing = missing_fields(state)
        if missing:
            return next_question(state)

        st.session_state.awaiting_confirmation = True
        return build_summary(state, config.BUSINESS_NAME)

    # --- General query: answer directly, or via RAG if PDFs are loaded ---
    history = trim_memory(st.session_state.messages)
    return rag_tool(llm, st.session_state.vectorstore, prompt, history)


# ---------------------------------------------------------------------------
# Chat page
# ---------------------------------------------------------------------------
def chat_page():
    st.title(f"🤖 {config.BUSINESS_NAME} — Booking Assistant")
    st.caption(f"Ask me anything, or say you'd like to book a {config.BOOKING_LABEL}.")

    with st.expander("📄 Upload reference PDFs (optional, powers document Q&A)"):
        uploaded_files = st.file_uploader(
            "Upload one or more PDFs", type=["pdf"], accept_multiple_files=True
        )
        if uploaded_files and st.button("Process PDFs"):
            with st.spinner("Extracting, chunking, and embedding your documents..."):
                try:
                    st.session_state.vectorstore = build_vectorstore(uploaded_files)
                    st.session_state.vectorstore_files = [f.name for f in uploaded_files]
                    st.success(
                        f"✅ Loaded {len(uploaded_files)} PDF(s) "
                        f"({st.session_state.vectorstore.engine} index)."
                    )
                except ValueError as e:
                    st.error(f"⚠️ {e}")
                except Exception as e:
                    st.error(f"⚠️ Unexpected error while processing PDFs: {e}")

        if st.session_state.vectorstore_files:
            st.caption("Currently loaded: " + ", ".join(st.session_state.vectorstore_files))

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Type your message here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = handle_user_message(prompt)
                except Exception as e:
                    response = f"⚠️ Something went wrong: {e}"
                st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.messages = trim_memory(st.session_state.messages)


# ---------------------------------------------------------------------------
# App shell
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title=f"{config.BUSINESS_NAME} — AI Booking Assistant",
        page_icon="🎙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    try:
        init_db()
    except Exception as e:
        st.error(f"Database initialization failed: {e}")

    init_session_state()

    with st.sidebar:
        st.title("Navigation")
        page = st.radio("Go to:", ["Chat", "Admin Dashboard"], index=0)
        st.divider()
        if page == "Chat" and st.button("🗑️ Clear Chat & Booking", use_container_width=True):
            st.session_state.messages = []
            st.session_state.booking_state = empty_state()
            st.session_state.awaiting_confirmation = False
            st.rerun()

    if page == "Chat":
        chat_page()
    else:
        render_admin_dashboard()


if __name__ == "__main__":
    main()
