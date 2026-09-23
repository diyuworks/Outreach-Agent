"""
LIVE DEMO SCRIPT — run this in front of your sir.

Walks through the full pipeline end-to-end:
  1. Load qualified leads (from lead_source.py, currently CSV)
  2. Generate personalized messages per channel
  3. Hold each message for human approval (no auto-send, per spec Section 10)
  4. "Send" (real for email if configured, DRY RUN otherwise)
  5. Schedule follow-ups
  6. Simulate an inbound reply and show classification + escalation

Run:  python3 demo.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

from lead_source import CSVLeadSource
from message_generator import generate_all_channels
from state_store import StateStore
from follow_up_engine import next_action, FollowUpAction
from response_classifier import classify_reply, needs_human_escalation
from escalation import process_reply
from providers.email_provider import EmailProvider
from providers.sms_provider import SMSProvider
from providers.whatsapp_provider import WhatsAppProvider

APPROVER_NAME = "Demo User"  # in a real run, whoever is approving today


def line(char="-", n=70):
    print(char * n)


def get_provider(channel: str):
    return {
        "email": EmailProvider(),
        "sms": SMSProvider(),
        "whatsapp": WhatsAppProvider(),
    }[channel]


def run_demo():
    line("=")
    print("AUTOMATED MULTI-CHANNEL OUTREACH & FOLLOW-UP AGENT — LIVE DEMO")
    line("=")

    store = StateStore(db_path="outreach.db")
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_actionable_leads()

    print(f"\nSTEP 1: Loaded {len(leads)} actionable (QUALIFIED/FOLLOW_UP) leads from the lead source.\n")
    for l in leads:
        print(f"  - [{l.lead_id}] {l.company} | {l.contact_name} ({l.designation}) "
              f"| Score: {l.lead_score} | Service: {l.primary_service}")

    for lead in leads:
        line()
        print(f"LEAD: {lead.company} ({lead.lead_id})")
        line()

        if store.is_opted_out(lead.lead_id):
            print("  -> Skipping: lead is on the opt-out list (cross-channel).")
            continue

        drafts = generate_all_channels(lead)

        for draft in drafts:
            channel = draft.channel.value
            action = next_action(store, lead.lead_id, channel)

            print(f"\n  Channel: {channel.upper()}  |  Follow-up engine says: {action.value}")

            if action in (FollowUpAction.STOPPED_REPLIED, FollowUpAction.MOVE_TO_NURTURE):
                print(f"  -> No message needed right now.")
                continue
            if action == FollowUpAction.WAIT:
                print(f"  -> Not due yet, will check again later.")
                continue

            # SEND_INITIAL or SEND_FOLLOW_UP: draft -> approval -> send
            print(f"  Draft message ({channel}):")
            if draft.subject:
                print(f"    Subject: {draft.subject}")
            print(f"    Body: {draft.body[:200]}{'...' if len(draft.body) > 200 else ''}")

            msg_id = store.queue_for_approval(draft)
            approve = input(f"\n  Approve and send this {channel} message to {lead.contact_name}? [y/N]: ").strip().lower()

            if approve != "y":
                print("  -> Skipped (not approved). Message stays in the pending queue.")
                continue

            store.approve_message(msg_id, approved_by=APPROVER_NAME)

            provider = get_provider(channel)
            target = lead.email if channel == "email" else lead.phone
            if channel == "email":
                ok = provider.send(target, draft.subject, draft.body)
            else:
                ok = provider.send(target, draft.body)

            if ok:
                store.mark_sent(msg_id)
                if action == FollowUpAction.SEND_INITIAL:
                    store.record_initial_send(lead.lead_id, channel)
                else:
                    state = store.get_follow_up_state(lead.lead_id, channel)
                    store.record_follow_up_sent(lead.lead_id, channel, state["follow_up_count"] + 1)
                print(f"  -> Follow-up scheduled per cadence (3 / 6 / 7 business days).")

    # ---- Simulate an inbound reply to show classification + escalation ----
    line("=")
    print("STEP 2: SIMULATE AN INBOUND REPLY (to show classification + escalation)")
    line("=")
    sample_lead = leads[0] if leads else None
    if sample_lead:
        reply_text = input(
            f"\nType a sample reply as if you were {sample_lead.contact_name} "
            f"(e.g. 'Can we schedule a call?'): "
        ).strip()
        if reply_text:
            process_reply(sample_lead, reply_text, store, channel="email")

    line("=")
    print("DEMO COMPLETE. All state is saved in outreach.db (SQLite) — rerun anytime to see")
    print("follow-up scheduling pick up where it left off.")
    line("=")


if __name__ == "__main__":
    run_demo()
