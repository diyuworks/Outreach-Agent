"""
Send Initial Outreach Email.

Sends the first initial outreach email to qualified leads.
Run:  python send_initial.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

from lead_source import CSVLeadSource
from message_generator import generate_email
from state_store import StateStore
from providers.email_provider import EmailProvider

def run_send_initial():
    store = StateStore(db_path="outreach.db")
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_actionable_leads()

    if not leads:
        print("No actionable leads found in data/leads.csv.")
        return

    print("\n=======================================================")
    print("SEND INITIAL OUTREACH EMAIL")
    print("=======================================================\n")

    for lead in leads:
        if not lead.email:
            continue

        if store.is_opted_out(lead.lead_id):
            print(f"Skipping {lead.company} ({lead.contact_name}) — Opted out.")
            continue

        state = store.get_follow_up_state(lead.lead_id, "email")
        if state is not None:
            print(f"Notice: {lead.company} ({lead.contact_name}) already has initial email sent on {state['last_message_at'][:10] if state['last_message_at'] else 'earlier'}.")

        draft = generate_email(lead, follow_up_count=0)

        print(f"LEAD: {lead.company} | Contact: {lead.contact_name} <{lead.email}>")
        print(f"Subject: {draft.subject}")
        print(f"Body preview:\n{draft.body[:220]}...\n")

        approve = input(f"Approve and SEND initial email to {lead.contact_name} ({lead.email})? [y/N]: ").strip().lower()
        if approve != "y":
            print("-> Skipped (not approved).\n")
            continue

        provider = EmailProvider()
        ok = provider.send(lead.email, draft.subject, draft.body)
        if ok:
            msg_id = store.queue_for_approval(draft)
            store.approve_message(msg_id, approved_by="Human Operator")
            store.mark_sent(msg_id)
            store.record_initial_send(lead.lead_id, "email")
            print(f"-> SUCCESS: Initial email delivered to {lead.email}!")
            print("-> Next follow-up (Follow-Up #1) scheduled in 3 business days.\n")
        else:
            print(f"-> FAILED to deliver to {lead.email}.\n")

    print("=======================================================")
    print("INITIAL OUTREACH COMPLETE.")
    print("=======================================================\n")

if __name__ == "__main__":
    run_send_initial()
