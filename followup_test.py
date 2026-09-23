"""
Follow-up Time-Travel / Fast-Forward Test Mode.

Simulates a future date to show what follow-up actions WOULD be due,
without changing the real system clock or sending anything automatically.

Usage:
    python followup_test.py --simulate-days-forward 4
    python followup_test.py --simulate-days-forward 10
    python followup_test.py --simulate-days-forward 30
"""
import argparse
import os
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

from lead_source import CSVLeadSource
from message_generator import generate_all_channels
from state_store import StateStore
from follow_up_engine import next_action, FollowUpAction
from providers.email_provider import EmailProvider
from providers.sms_provider import SMSProvider
from providers.whatsapp_provider import WhatsAppProvider

APPROVER_NAME = "Demo User"


def line(char="-", n=70):
    print(char * n)


def get_provider(channel: str):
    return {
        "email": EmailProvider(),
        "sms": SMSProvider(),
        "whatsapp": WhatsAppProvider(),
    }[channel]


def run_simulation(days_forward: int):
    simulated_date = date.today() + timedelta(days=days_forward)

    line("=")
    print(f"FOLLOW-UP TIME-TRAVEL — simulating {days_forward} days forward")
    print(f"Real date: {date.today()}  |  Simulated date: {simulated_date}")
    line("=")

    store = StateStore(db_path="outreach.db")
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_actionable_leads()

    print(f"\nLoaded {len(leads)} actionable leads.\n")

    any_action = False

    for lead in leads:
        if store.is_opted_out(lead.lead_id):
            continue

        drafts = generate_all_channels(lead)

        for draft in drafts:
            channel = draft.channel.value
            action = next_action(store, lead.lead_id, channel,
                                 as_of_date=simulated_date)

            if action in (FollowUpAction.WAIT, FollowUpAction.STOPPED_REPLIED):
                continue

            any_action = True
            line()
            print(f"LEAD: {lead.company} ({lead.lead_id})")
            print(f"  Channel: {channel.upper()}  |  Action: {action.value}")

            if action == FollowUpAction.MOVE_TO_NURTURE:
                print(f"  -> Max follow-ups reached. Would move to nurture list.")
                continue

            # SEND_INITIAL or SEND_FOLLOW_UP — show the draft
            print(f"  Draft message ({channel}):")
            if draft.subject:
                print(f"    Subject: {draft.subject}")
            print(f"    Body: {draft.body[:200]}{'...' if len(draft.body) > 200 else ''}")

            # Same approval gate as demo.py — nothing auto-sends
            approve = input(
                f"\n  [SIMULATION] Actually send this {channel} message "
                f"to {lead.contact_name}? [y/N]: "
            ).strip().lower()

            if approve != "y":
                print("  -> Skipped (not approved).")
                continue

            # Real send path — identical to demo.py
            msg_id = store.queue_for_approval(draft)
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
                    store.record_follow_up_sent(
                        lead.lead_id, channel,
                        state["follow_up_count"] + 1
                    )
                print(f"  -> Sent and follow-up state updated.")

    if not any_action:
        line()
        print("No follow-ups or new sends are due at the simulated date.")
        print("Try a larger --simulate-days-forward value.")

    line("=")
    print(f"SIMULATION COMPLETE (simulated date: {simulated_date}).")
    line("=")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simulate follow-up actions N days in the future."
    )
    parser.add_argument(
        "--simulate-days-forward",
        type=int,
        required=True,
        help="Number of days to fast-forward from today.",
    )
    args = parser.parse_args()

    if args.simulate_days_forward < 0:
        print("Error: --simulate-days-forward must be a non-negative integer.")
        exit(1)

    run_simulation(args.simulate_days_forward)
