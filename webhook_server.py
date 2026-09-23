"""
Twilio Inbound Webhook Listener — SMS & WhatsApp replies.

Twilio calls this URL (as a POST) whenever a lead replies to your Twilio
SMS number or WhatsApp Sandbox number. This script:
  1. Receives the reply (sender phone + message body)
  2. Matches the sender's phone number to a known lead (data/leads.csv)
  3. Classifies the reply using the EXISTING response_classifier.py
  4. Runs it through the EXISTING escalation.process_reply() — same
     dedup + notifier logic already used for email replies, reused as-is
  5. Replies to Twilio with an empty TwiML response (required by Twilio,
     means "don't auto-reply anything back")

Why a separate lightweight server instead of extending web_dashboard.py:
this keeps the existing dashboard untouched and lets you run this
independently on its own port. If preferred later, its handle_incoming()
logic can be moved into web_dashboard.py as one more route — the function
is written to be relocated easily.

IMPORTANT — Twilio needs a PUBLIC url to reach this, not localhost.
For a demo, use ngrok (free): https://ngrok.com/download
  1. Run this script:            python3 webhook_server.py
  2. In another terminal:        ngrok http 5001
  3. Copy the https://xxxx.ngrok-free.app URL ngrok gives you
  4. Set WEBHOOK_PUBLIC_URL in .env to https://xxxx.ngrok-free.app/webhook
  5. Paste it (+ "/webhook") into Twilio Console → Messaging →
     WhatsApp Sandbox Settings → "WHEN A MESSAGE COMES IN"
     (do the same under Phone Numbers → your SMS number, for SMS replies)
  6. Now when a lead replies on WhatsApp/SMS, it flows through this
     script live, in front of your sir.

Run:  python3 webhook_server.py
"""
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from lead_source import CSVLeadSource
from state_store import StateStore
from escalation import process_reply

PORT = int(os.getenv("WEBHOOK_PORT", "5001"))
WEBHOOK_PUBLIC_URL = os.getenv("WEBHOOK_PUBLIC_URL", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()


def normalize_phone(raw: str) -> str:
    """Strip Twilio's 'whatsapp:' prefix and whitespace for matching against leads.csv."""
    return raw.replace("whatsapp:", "").strip()


def build_phone_lookup():
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_actionable_leads()
    return {normalize_phone(lead.phone): lead for lead in leads if lead.phone}


class TwilioWebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep console output focused on our own logs, not raw HTTP noise
        pass

    def do_POST(self):
        if self.path.rstrip("/") != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        fields = {k: v[0] for k, v in parse_qs(raw_body).items()}

        # Twilio signature validation (if WEBHOOK_PUBLIC_URL is configured)
        if WEBHOOK_PUBLIC_URL and TWILIO_AUTH_TOKEN:
            try:
                from twilio.request_validator import RequestValidator
                validator = RequestValidator(TWILIO_AUTH_TOKEN)
                twilio_signature = self.headers.get("X-Twilio-Signature", "")
                is_valid = validator.validate(WEBHOOK_PUBLIC_URL, fields, twilio_signature)
                if not is_valid:
                    print(f"[WEBHOOK] Rejected — invalid Twilio signature.")
                    self.send_response(403)
                    self.end_headers()
                    return
            except ImportError:
                print("[WEBHOOK] Warning: twilio package not installed — signature validation skipped.")

        from_number = normalize_phone(fields.get("From", ""))
        body = fields.get("Body", "").strip()
        channel = "whatsapp" if "whatsapp" in fields.get("From", "") else "sms"

        print(f"\n[WEBHOOK] Inbound {channel.upper()} from {from_number}: \"{body}\"")

        phone_lookup = build_phone_lookup()
        lead = phone_lookup.get(from_number)

        if not lead:
            print(f"[WEBHOOK] No matching lead found for {from_number} — ignoring.")
        else:
            store = StateStore(db_path="outreach.db")
            received_at = datetime.now().isoformat(timespec="seconds")
            process_reply(lead, body, store, channel=channel, received_at=received_at)

        # Twilio requires a TwiML (XML) response, even if empty
        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.end_headers()
        self.wfile.write(b"<?xml version='1.0' encoding='UTF-8'?><Response></Response>")


def run():
    if not WEBHOOK_PUBLIC_URL:
        print("[!] WARNING: WEBHOOK_PUBLIC_URL not set in .env - Twilio signature")
        print("   validation is DISABLED. Do not expose this publicly without it.")
        print("   Set WEBHOOK_PUBLIC_URL=https://your-ngrok-url.ngrok-free.app/webhook\n")

    server = HTTPServer(("0.0.0.0", PORT), TwilioWebhookHandler)
    print(f"Twilio webhook listener running on http://localhost:{PORT}/webhook")
    print("Expose this publicly with ngrok before setting it in the Twilio console:")
    print(f"  ngrok http {PORT}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWebhook listener stopped.")


if __name__ == "__main__":
    run()
