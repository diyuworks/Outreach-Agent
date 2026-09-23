"""
Send WhatsApp Outreach Message.

Sends the initial personalized WhatsApp pitch to leads.
Supports:
  - Twilio WhatsApp Sandbox (Free live developer test)
  - Meta Cloud API (Official Enterprise)
  - Safe Dry-Run (Demo mode when credentials not set)

Run:  python send_whatsapp.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

from lead_source import CSVLeadSource
from message_generator import generate_whatsapp
from state_store import StateStore
from providers.whatsapp_provider import WhatsAppProvider


def run_send_whatsapp():
    store = StateStore(db_path="outreach.db")
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_actionable_leads()

    if not leads:
        print("No actionable leads found in data/leads.csv.")
        return

    print("\n=======================================================")
    print("SEND WHATSAPP OUTREACH MESSAGE")
    print("=======================================================\n")

    provider = WhatsAppProvider()
    if provider.use_twilio:
        print("Mode: [LIVE] Twilio WhatsApp Sandbox Connected!")
    elif provider.use_meta:
        print("Mode: [LIVE] Meta Cloud API Connected!")
    else:
        print("Mode: [DRY RUN] Safe Demo Mode (Add TWILIO credentials in .env for real phone delivery)")

    print()

    for lead in leads:
        if not lead.phone:
            continue

        if store.is_opted_out(lead.lead_id):
            print(f"Skipping {lead.company} ({lead.contact_name}) — Opted out.")
            continue

        draft = generate_whatsapp(lead)

        print(f"LEAD: {lead.company} | Contact: {lead.contact_name} ({lead.phone})")
        print(f"Message preview:\n\"{draft.body}\"\n")

        approve = input(f"Approve and SEND WhatsApp message to {lead.contact_name} ({lead.phone})? [y/N]: ").strip().lower()
        if approve != "y":
            print("-> Skipped (not approved).\n")
            continue

        ok = provider.send(lead.phone, draft.body)
        if ok:
            msg_id = store.queue_for_approval(draft)
            store.approve_message(msg_id, approved_by="Human Operator")
            store.mark_sent(msg_id)
            store.record_initial_send(lead.lead_id, "whatsapp")
            print(f"-> SUCCESS: WhatsApp message dispatched to {lead.phone}!\n")
        else:
            print(f"-> FAILED to dispatch WhatsApp message to {lead.phone}.\n")

    print("=======================================================")
    print("WHATSAPP OUTREACH COMPLETE.")
    print("=======================================================\n")


if __name__ == "__main__":
    run_send_whatsapp()
