"""
config.py
---------
Central place for all configuration: API keys, model names, business
details, and DB paths. Values are read from Streamlit secrets first
(recommended for Streamlit Cloud deployment), falling back to
environment variables for local development.
"""
import os

try:
    import streamlit as st
    _SECRETS = st.secrets
except Exception:
    _SECRETS = {}


def _get(key: str, default: str = "") -> str:
    """Read a config value from st.secrets, then env vars, then default."""
    try:
        if key in _SECRETS:
            return _SECRETS[key]
    except Exception:
        pass
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# LLM (Groq via LangChain)
# ---------------------------------------------------------------------------
GROQ_API_KEY = _get("GROQ_API_KEY", "")
# Check https://console.groq.com/docs/models for the latest available models.
GROQ_MODEL = _get("GROQ_MODEL", "llama-3.3-70b-versatile")

# ---------------------------------------------------------------------------
# Email (SMTP)
# ---------------------------------------------------------------------------
SMTP_HOST = _get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(_get("SMTP_PORT", "587"))
SMTP_USER = _get("SMTP_USER", "")          # e.g. your dummy Gmail address
SMTP_PASSWORD = _get("SMTP_PASSWORD", "")  # Gmail "App Password", not your real password
FROM_EMAIL = _get("FROM_EMAIL", SMTP_USER)

# ---------------------------------------------------------------------------
# Business / booking domain — customize this section for your use case
# ---------------------------------------------------------------------------
BUSINESS_NAME = _get("BUSINESS_NAME", "Soundwave Recording Studio")
BOOKING_LABEL = "studio session"   # used in prompts/messages
SERVICE_EXAMPLES = ["Vocal Recording", "Podcast Session", "Mixing & Mastering",
                     "Full Band Session", "Voiceover Booth", "Songwriting Session"]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DB_PATH = _get("DB_PATH", "bookings.db")

# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------
MAX_HISTORY_MESSAGES = 25

# ---------------------------------------------------------------------------
# RAG
# ---------------------------------------------------------------------------
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
RETRIEVAL_K = 4
