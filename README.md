# Automated Multi-Channel Outreach & Follow-Up Agent

Messaging & follow-up layer of the B2B lead-gen system. Takes an already
**qualified** lead and handles Email / SMS / WhatsApp outreach, follow-up
scheduling, and reply classification — with a human-approval gate before
every single message goes out.

## What this demo shows

1. Load qualified leads (`data/leads.csv` — sample/fictional data for demo)
2. Generate a personalized message per channel (observation → problem → how we help → CTA)
3. **Hold every message for human approval** — nothing auto-sends
4. Send (real for Email if configured; safe DRY RUN otherwise)
5. Schedule the next follow-up automatically (Day 3 → Day ~6 → Day ~7 → Nurture)
6. Simulate an inbound reply → classify it → escalate to a human if it's hot (meeting/pricing ask)

All state (message history, follow-up dates, opt-outs) persists in `outreach.db`
(SQLite) so re-running the script picks up where it left off — a real lead
generation feed would just replace `data/leads.csv` in `lead_source.py`.

## What's free vs. paid — be upfront about this

| Channel | Free? | Notes |
|---|---|---|
| **Email** | Yes, fully | Gmail SMTP, generous free daily quota |
| **SMS** | No ongoing free tier | Twilio gives free trial credit (verified numbers only) — real volume costs money |
| **WhatsApp** | Partially | Meta Cloud API has a limited free conversation quota, but sending to new contacts requires an **approved message template** — approval can take days and is an external dependency, not something code can bypass |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in .env ONLY for channels you want to send for real.
# Leave any section blank and that channel runs in safe DRY RUN mode.
python web_dashboard.py                      # Interactive Web UI (http://localhost:5050)

# Background & Automation Services:
python -m services.scheduler --interval 10   # Automated background polling daemon
python -m services.scheduler --once         # Run single check cycle (for cron)
python -m services.daily_report             # Generate daily outreach performance report

# Standalone Utility Scripts:
python -m scripts.check_replies              # auto-detect Gmail replies
python -m scripts.send_sms                   # quick test SMS sender
python -m scripts.send_whatsapp              # quick test WhatsApp sender
```

## Project structure

```
outreach_agent/
├── web_dashboard.py          # Main Web Dashboard server (entry point)
├── webhook_server.py         # Twilio inbound reply webhook listener
├── core/                     # Core Business Logic & State Management
│   ├── models.py             # Data schemas (Lead, Channel, DraftMessage, etc.)
│   ├── state_store.py        # SQLite CRM & interaction persistence
│   ├── lead_source.py        # Lead ingestion abstraction
│   ├── lead_scoring.py       # Dynamic lead scoring engine
│   ├── message_generator.py  # Personalized multi-channel copy generator
│   ├── follow_up_engine.py   # Follow-up cadence state machine
│   ├── response_classifier.py# Inbound reply intent classifier
│   ├── escalation.py         # Human escalation workflow
│   ├── notifier.py           # Multi-channel urgent escalation alerts
│   └── phone_utils.py        # E.164 phone normalization utilities
├── services/                 # Background & Feature Services
│   ├── scheduler.py          # Automated background polling daemon
│   ├── daily_report.py       # Performance & digest report generator
│   └── voice_commands.py     # Voice command processing & safe actions
├── scripts/                  # Standalone CLI tools & scripts
│   ├── check_replies.py      # Gmail inbox reply scanner
│   ├── send_sms.py           # CLI SMS sender
│   └── send_whatsapp.py      # CLI WhatsApp sender
├── providers/                # External Communication Providers
│   ├── email_provider.py     # SMTP Email delivery
│   ├── email_reader.py       # Gmail API reply ingestion
│   ├── sms_provider.py       # Twilio SMS client
│   ├── whatsapp_provider.py  # Twilio & Meta WhatsApp client
│   ├── stt_provider.py       # Groq Whisper speech-to-text
│   └── hetvi_lead_source.py  # External CRM lead fetcher
├── static/                   # Frontend assets (HTML, CSS, JS)
├── data/                     # Leads data & cached datasets
├── tests/                    # Automated regression & integration test suite
└── _deprecated/              # Archived legacy files
```

## Gmail API Setup (for `check_replies.py`)

The reply detection feature uses Gmail API (read-only) which requires a one-time
OAuth setup, separate from the SMTP App Password used for sending.

### Step-by-step:

1. **Create a Google Cloud project** (or reuse an existing one):
   - Go to https://console.cloud.google.com/projectcreate
   - Name it something like "Outreach Agent"

2. **Enable the Gmail API**:
   - Go to https://console.cloud.google.com/apis/library/gmail.googleapis.com
   - Click **Enable**

3. **Configure OAuth consent screen**:
   - Go to https://console.cloud.google.com/apis/credentials/consent
   - Choose **External** user type (unless you have a Workspace org)
   - Fill in app name, support email — other fields are optional
   - Under **Scopes**, add `https://www.googleapis.com/auth/gmail.readonly`
   - Under **Test users**, add the Gmail address you'll use for checking replies
   - **Publish** the app (or stay in Testing mode — both work for personal use)

4. **Create OAuth 2.0 credentials**:
   - Go to https://console.cloud.google.com/apis/credentials
   - Click **Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Download the JSON and save it as `credentials.json` in the project root

5. **First run** — the browser will open for you to authorize:
   ```bash
   python3 check_replies.py
   ```
   After authorization, a `token.json` is saved locally so future runs are
   non-interactive.

> **Note**: `credentials.json` and `token.json` contain secrets — do NOT commit
> them to version control. They are already in `.gitignore` if you have one.

## Live Twilio Demo Setup (WhatsApp + SMS)

Twilio's free trial gives 100 free SMS and 100 free WhatsApp messages
(30-day trial). Enough for a live demo; real production volume needs a
paid Twilio account (or a cheaper backup provider — see note at the end).

### 1. Get Twilio credentials
1. Sign up at twilio.com (no credit card needed for trial)
2. From the Twilio Console home page, copy your Account SID and Auth Token
3. Put them in `.env`:
   ```
   TWILIO_ACCOUNT_SID=your_sid_here
   TWILIO_AUTH_TOKEN=your_token_here
   ```

### 2. WhatsApp Sandbox setup
1. In Twilio Console, go to Messaging → Try it out → Send a WhatsApp message
2. Follow the on-screen instructions to join the sandbox from your own
   WhatsApp (send the given "join <code-word>" message to the shown number)
3. Leave `TWILIO_WHATSAPP_FROM=whatsapp:+14155238886` as-is in `.env`
   (this is Twilio's shared sandbox number)

### 3. SMS number setup
1. In Twilio Console, go to Phone Numbers → Buy a number (trial accounts
   get one free number) or use the trial number already provisioned
2. Put it in `.env` as `TWILIO_FROM_NUMBER=+1XXXXXXXXXX`
3. Note: on a trial account, you can only send to numbers you've manually
   verified under Phone Numbers → Verified Caller IDs

### 4. Receiving replies live (webhook + ngrok)
Twilio needs a public URL to deliver inbound replies to — localhost alone
won't work. For a demo, use ngrok (free, no signup required for basic use):

1. Download ngrok: https://ngrok.com/download
2. Start the webhook listener: `python3 webhook_server.py`
3. In a separate terminal: `ngrok http 5001`
4. Copy the `https://xxxx.ngrok-free.app` URL ngrok prints
5. **Set `WEBHOOK_PUBLIC_URL` in `.env`** to the full webhook URL:
   ```
   WEBHOOK_PUBLIC_URL=https://xxxx.ngrok-free.app/webhook
   ```
   This enables Twilio signature validation — the server will reject any
   POST that wasn't signed by Twilio. **Update this every time ngrok is
   restarted** (free-tier ngrok URLs change on restart; reserved domains
   on paid plans stay fixed).
6. In Twilio Console → Messaging → WhatsApp Sandbox Settings, paste
   `https://xxxx.ngrok-free.app/webhook` into "WHEN A MESSAGE COMES IN"
7. Repeat for your SMS number under Phone Numbers → your number →
   Messaging Configuration → "A MESSAGE COMES IN"
8. Now replying on WhatsApp/SMS from a verified test number flows live
   into classification + escalation, same as the email reply pipeline.

### Multi-Channel Escalation & Lead ETA Confirmation
When a hot lead reply (`MEETING_REQUEST`, `PRICE_REQUEST`, etc.) is detected:
- **Sales Rep Alerts**: Urgent email alerts are sent to `SALES_REP_ALERT_EMAIL`. Optionally, set `SALES_REP_ALERT_PHONE` in `.env` to also dispatch an instant SMS alert to the salesperson.
- **Lead ETA Confirmation**: The lead automatically receives a short, factual response-time confirmation (e.g., "we'll be in touch within 2 hours") on the channel they replied on. This confirmation bypasses the interactive approval prompt because `process_reply()` executes in background, non-interactive contexts (`scheduler.py`, `webhook_server.py`, `check_replies.py`) where a blocking prompt would hang the process. Set `AUTO_SEND_ETA_CONFIRMATION=false` in `.env` if you wish to disable ETA confirmations. Response ETA hours can be configured via `ESCALATION_RESPONSE_ETA_HOURS` (default: 2).

## Live Demo — Webhook Setup (WhatsApp/SMS real-time replies)

1. Terminal 1: `python3 webhook_server.py`
2. Terminal 2: `ngrok http 5001`
3. Copy the ngrok HTTPS URL it prints (e.g. `https://abc123.ngrok-free.app`)
4. Twilio Console → Messaging → WhatsApp Sandbox Settings →
   "WHEN A MESSAGE COMES IN" → paste `<ngrok-url>/webhook`
5. Twilio Console → Phone Numbers → your number → Messaging →
   "A MESSAGE COMES IN" → paste the same `<ngrok-url>/webhook`
6. In `.env`, set `WEBHOOK_PUBLIC_URL=<ngrok-url>/webhook`
7. Restart `webhook_server.py` after editing `.env`
8. Test: reply on WhatsApp/SMS from your verified number, confirm the
   webhook terminal logs it, then check the Dashboard — the lead's status
   should update to Replied/Escalated.

Note: the ngrok URL changes every time ngrok restarts (free tier) — repeat
steps 3–7 if ngrok was restarted since the last demo.
## What's intentionally NOT built yet (next phases)

- LangGraph-based follow-up graph (today's follow-up engine is a plain Python
  state machine with the same logic — mechanically portable to LangGraph later)
- Real WhatsApp send — blocked on Meta Business verification + template
  approval (external process, start this in parallel, not after)
- Dashboard UI — currently CLI + SQLite only

## Human-in-the-loop guarantees (non-negotiable, per spec)

- No message is ever sent without explicit approval in this script
- Opt-out is cross-channel: one opt-out blocks Email + SMS + WhatsApp for that lead
- No pricing, discounts, or delivery timelines are ever promised in generated messages
