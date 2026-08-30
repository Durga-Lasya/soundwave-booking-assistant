# AI Booking Assistant — Soundwave Recording Studio

A chat-based AI assistant for a recording studio that:
- Answers questions from user-uploaded PDFs (RAG) — e.g. a rate card, equipment list, or booking policy
- Detects booking intent and collects details via multi-turn conversation (name, email, phone, session type, date, time)
- Confirms details before saving to a database
- Sends an email confirmation after booking
- Includes an admin dashboard to view all bookings

**Domain is fully configurable** — everything studio-specific lives in `app/config.py`
(`BUSINESS_NAME`, `BOOKING_LABEL`, `SERVICE_EXAMPLES`). Swap those three values to
retarget the whole app to a doctor's office, hotel, salon, events, or classes without
touching any other file.

## Architecture

```
app/main.py            Streamlit entry point, chat UI, orchestration
app/chat_logic.py       LLM setup, intent detection + field extraction, memory
app/booking_flow.py     Slot-filling state machine, validation, confirmation
app/rag_pipeline.py     PDF ingestion, chunking, embeddings, vector search
app/tools.py            RAG tool, booking persistence tool, email tool
app/admin_dashboard.py  Admin UI (view/filter/export bookings)
app/config.py           Central configuration (secrets, business settings)
db/database.py          SQLite connection + CRUD
db/models.py            Table schema (customers, bookings)
```

**LLM:** Groq (via LangChain) — fast, free-tier friendly.
**Embeddings/Vector store:** FAISS + `sentence-transformers/all-MiniLM-L6-v2`,
with an automatic TF-IDF fallback if the embedding model can't be downloaded.
**Database:** SQLite (swap `db/database.py` for a Supabase client to persist
across restarts — same function signatures).
**Email:** SMTP (Gmail App Password) — swappable for SendGrid.

## Booking flow

1. Detect booking intent from the user's message.
2. Extract any known details already mentioned.
3. Ask only for the fields still missing (name, email, phone, service, date, time).
4. Validate each field (email format, date as `YYYY-MM-DD`, phone length).
5. Once complete, summarize and ask for explicit "yes/no" confirmation.
6. On "yes": save to DB, send confirmation email, reply with the booking ID.
7. On "no": ask what to correct, without losing the fields already collected.

## Local setup

```bash
git clone <your-repo-url>
cd AI_Booking_Assistant
python -m venv venv && source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit .streamlit/secrets.toml with your real GROQ_API_KEY and SMTP credentials

streamlit run app/main.py
```

### Getting a Groq API key
Visit https://console.groq.com/keys, create a key, and check
https://console.groq.com/docs/models for the current list of available
model names (update `GROQ_MODEL` in secrets if needed).

### Getting a Gmail App Password
1. Enable 2-Step Verification on the Gmail account.
2. Go to https://myaccount.google.com/apppasswords and generate an app password.
3. Use that (not your real password) as `SMTP_PASSWORD`.

## Deploying to Streamlit Community Cloud

1. Push this repo to a **public** GitHub repository.
2. Go to https://share.streamlit.io, "New app", pick your repo/branch.
3. Set the main file path to `app/main.py`.
4. Under **Advanced settings → Secrets**, paste the contents of your
   `secrets.toml` (same key = value format).
5. Deploy. The first PDF upload may take a little longer as the embedding
   model downloads and caches.

## Testing checklist (per assignment spec)

- [ ] PDF upload & RAG responses
- [ ] Booking flow + confirmation
- [ ] DB storage (check Admin Dashboard)
- [ ] Email delivery (and graceful fallback if it fails)
- [ ] Admin dashboard filters
- [ ] Input validation (bad email/date/phone)
- [ ] Error handling (invalid PDFs, DB errors, unexpected exceptions)

## Known limitations / future improvements

- SQLite resets on Streamlit Cloud redeploys — acceptable for this
  assignment; swap in Supabase for real persistence.
- Intent/field extraction relies on a single LLM call with a JSON-only
  prompt; a malformed response falls back to keyword matching.
- Bonus ideas not yet implemented: STT/TTS, user-side booking retrieval,
  admin edit/cancel, avatars/typing indicators.
