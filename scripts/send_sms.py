"""
Send SMS Outreach Message.

Sends personalized cold outreach SMS messages to qualified leads.
Supports:
  - Twilio SMS (Default using trial credits)
  - Fast2SMS (Indian SMS Gateway)
  - Safe Dry-Run fallback

Usage:  python send_sms.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

from core.lead_source import CSVLeadSource
from core.message_generator import generate_sms
from core.state_store import StateStore
from providers.sms_provider import SMSProvider


def run_send_sms():
    store = StateStore(db_path="outreach.db")
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_actionable_leads()

    if not leads:
        print("No actionable leads found in data/leads.csv.")
        return

    print("\n=======================================================")
    print("SEND SMS OUTREACH MESSAGE")
    print("=======================================================\n")

    provider = SMSProvider()
    if provider.use_fast2sms:
        print("Mode: [LIVE] Fast2SMS Gateway Connected!")
    elif provider.use_twilio:
        print("Mode: [LIVE] Twilio SMS Connected! (From: " + str(provider.from_number) + ")")
    else:
        print("Mode: [DRY RUN] Safe Demo Mode")

    print()

    for lead in leads:
        if not lead.phone:
            continue

        if store.is_opted_out(lead.lead_id):
            print(f"Skipping {lead.company} ({lead.contact_name}) — Opted out.")
            continue

        draft = generate_sms(lead)

        print(f"LEAD: {lead.company} | Contact: {lead.contact_name} ({lead.phone})")
        print(f"Message preview:\n\"{draft.body}\"\n")

        approve = input(f"Approve and SEND SMS to {lead.contact_name} ({lead.phone})? [y/N]: ").strip().lower()
        if approve != "y":
            print("-> Skipped (not approved).\n")
            continue

        ok = provider.send(lead.phone, draft.body)
        if ok:
            msg_id = store.queue_for_approval(draft)
            store.approve_message(msg_id, approved_by="Human Operator")
            store.mark_sent(msg_id)
            store.record_initial_send(lead.lead_id, "sms")
            print(f"-> SUCCESS: SMS dispatched to {lead.phone}!\n")
        else:
            print(f"-> FAILED to dispatch SMS to {lead.phone}.\n")

    print("=======================================================")
    print("SMS OUTREACH COMPLETE.")
    print("=======================================================\n")


if __name__ == "__main__":
    run_send_sms()
