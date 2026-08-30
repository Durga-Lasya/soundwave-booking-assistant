"""
chat_logic.py
-------------
- Initializes the Groq LLM.
- Classifies each user message as "booking" or "general" intent and
  extracts any booking fields mentioned, in a single structured call.
- Trims conversation history to the configured short-term memory window.
- Builds the general/RAG chat response.
"""
import json
import re

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app import config


def get_llm():
    """Initialize and return the Groq chat model."""
    if not config.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to .streamlit/secrets.toml "
            "or as an environment variable."
        )
    return ChatGroq(api_key=config.GROQ_API_KEY, model=config.GROQ_MODEL, temperature=0.2)


def trim_memory(messages: list) -> list:
    """Keep only the last N messages (short-term memory window)."""
    if len(messages) <= config.MAX_HISTORY_MESSAGES:
        return messages
    return messages[-config.MAX_HISTORY_MESSAGES:]


_CLASSIFY_SYSTEM_PROMPT = """You are an intent classifier and field extractor for a \
{booking_label} booking assistant called "{business_name}".

Given the latest user message (and the fields already collected so far), respond with \
ONLY a JSON object, no markdown, no extra text, in exactly this shape:

{{
  "intent": "booking" or "general",
  "name": string or null,
  "email": string or null,
  "phone": string or null,
  "service": string or null,
  "date": string or null,
  "time": string or null
}}

Rules:
- "intent" is "booking" if the user wants to schedule/book/reserve something, or if a \
booking is already in progress (fields already collected is non-empty). Otherwise "general".
- Only fill a field if the user's LATEST message actually mentions it. Leave others null.
- Normalize dates to YYYY-MM-DD if a date is mentioned (assume current year if omitted).
- Do not invent information the user didn't provide.
"""


def classify_and_extract(llm, user_message: str, current_state: dict) -> dict:
    """
    Single LLM call that both classifies intent and extracts any booking
    fields present in the latest message. Falls back to a safe default
    if the model output isn't valid JSON.
    """
    system = _CLASSIFY_SYSTEM_PROMPT.format(
        booking_label=config.BOOKING_LABEL,
        business_name=config.BUSINESS_NAME,
    )
    known = {k: v for k, v in current_state.items() if v}
    user_payload = f"Fields already collected: {json.dumps(known)}\nLatest user message: {user_message}"

    try:
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user_payload)])
        text = response.content.strip()
        # Strip markdown code fences if the model added them anyway.
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(text)
        if "intent" not in data:
            raise ValueError("missing intent")
        return data
    except Exception:
        # Safe fallback: simple keyword heuristic so the app still works
        # even if the LLM returns malformed output.
        keywords = ["book", "appointment", "schedule", "reserve", "slot", "booking"]
        intent = "booking" if any(k in user_message.lower() for k in keywords) else "general"
        return {"intent": intent, "name": None, "email": None, "phone": None,
                 "service": None, "date": None, "time": None}


_GENERAL_SYSTEM_PROMPT = """You are the friendly virtual assistant for {business_name}, \
a recording studio. You can answer questions about rates, equipment, session types, and \
policies (using any uploaded documents), and you can help book {booking_label}s. \
Answer the user's question helpfully and concisely.
If relevant context from uploaded documents is provided below, ground your answer in it \
and say so; if it doesn't contain the answer, say you're not sure rather than guessing.
If the user seems to want to book something, gently invite them to say so (e.g. \
"Say the word and I can help you book a session!").

Context from uploaded documents:
{context}
"""


def general_chat_response(llm, messages: list, retrieved_chunks: list) -> str:
    """Answer a general (non-booking) message, optionally grounded in RAG context."""
    context = "\n\n---\n\n".join(retrieved_chunks) if retrieved_chunks else "(no documents uploaded yet)"
    system = _GENERAL_SYSTEM_PROMPT.format(
        business_name=config.BUSINESS_NAME,
        booking_label=config.BOOKING_LABEL,
        context=context,
    )
    formatted = [SystemMessage(content=system)]
    for msg in messages:
        if msg["role"] == "user":
            formatted.append(HumanMessage(content=msg["content"]))
        else:
            formatted.append(AIMessage(content=msg["content"]))

    try:
        response = llm.invoke(formatted)
        return response.content
    except Exception as e:
        return f"Sorry, I ran into an error generating a response: {e}"
