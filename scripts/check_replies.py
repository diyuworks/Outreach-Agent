"""
Automatic Reply Detection via Gmail API.

Polls the Gmail inbox for unread replies from known leads, classifies them
using the existing response_classifier, and triggers escalation when needed.

Tracks "last checked" timestamp in outreach.db so re-running doesn't
reprocess the same emails.

Run:  python check_replies.py

Prerequisites:
  - credentials.json from Google Cloud Console (see README.md)
  - Gmail API enabled on the Cloud project
  - First run will open a browser for OAuth consent
"""
import os
from dotenv import load_dotenv

load_dotenv()

from core.lead_source import CSVLeadSource
from core.state_store import StateStore
from core.escalation import process_reply
from providers.email_reader import fetch_replies


def line(char="-", n=70):
    print(char * n)


def run_reply_check():
    line("=")
    print("AUTOMATIC REPLY DETECTION — Gmail Inbox Scanner")
    line("=")

    store = StateStore(db_path="outreach.db")
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_actionable_leads()

    # Build lookup: email -> Lead object
    email_to_lead = {}
    for lead in leads:
        if lead.email:
            email_to_lead[lead.email.strip().lower()] = lead

    known_emails = set(email_to_lead.keys())

    if not known_emails:
        print("No lead email addresses found. Nothing to check.")
        return

    print(f"\nMonitoring replies from {len(known_emails)} lead email(s):")
    for email in sorted(known_emails):
        print(f"  - {email}")

    last_checked = store.get_last_reply_check()
    if last_checked:
        print(f"\nLast checked: {last_checked}")
    else:
        print("\nFirst run — checking recent unread messages.")

    print("\nFetching from Gmail inbox...")

    try:
        replies = fetch_replies(known_emails, after_timestamp=last_checked)
    except FileNotFoundError as e:
        print(f"\n  ERROR: {e}")
        print("  See README.md → 'Gmail API Setup' for setup instructions.")
        return
    except Exception as e:
        print(f"\n  ERROR connecting to Gmail API: {e}")
        print("  Check your credentials.json and internet connection.")
        return

    # Record that we've checked (even if no replies found)
    store.record_reply_check()

    if not replies:
        print("\n  No new replies detected from known leads.")
        line("=")
        print("CHECK COMPLETE. Run again anytime to poll for new replies.")
        line("=")
        return

    print(f"\n  Found {len(replies)} reply(ies) from known leads!\n")

    for reply in replies:
        sender = reply["sender"]
        lead = email_to_lead.get(sender)
        if not lead:
            continue

        line()
        print(f"REPLY DETECTED")
        print(f"  From: {lead.contact_name} <{sender}> ({lead.company})")
        print(f"  Subject: {reply['subject']}")
        print(f"  Received: {reply['received_at']}")
        print(f"  Body preview: {reply['body'][:200]}{'...' if len(reply['body']) > 200 else ''}")

        # Classify and handle (shared logic with demo.py)
        process_reply(lead, reply["body"], store, channel="email", received_at=reply.get("received_at"))

    line("=")
    print("CHECK COMPLETE. All classifications saved to outreach.db.")
    print("Run dashboard.py to see updated status.")
    line("=")


if __name__ == "__main__":
    run_reply_check()
