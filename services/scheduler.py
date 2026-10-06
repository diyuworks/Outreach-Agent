"""
Automated Background Scheduler for Outreach & Follow-Up Agent.

Periodically runs:
1. Inbound Reply Checker (Gmail API inbox scanner -> response classification -> hot lead escalation alerts)
2. Scheduled Follow-up Scanner (checks due follow-ups -> generates drafts -> alerts/queues for approval)

Usage:
    python scheduler.py                 # Runs continuously (default: checks every 10 minutes)
    python scheduler.py --interval 5    # Runs continuously with custom interval (e.g. 5 minutes)
    python scheduler.py --once          # Runs a single scan cycle and exits (ideal for cron jobs)
"""
import os
import sys
import time
import argparse
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

from core.lead_source import CSVLeadSource
from core.state_store import StateStore
from core.message_generator import generate_email, generate_sms, generate_whatsapp
from core.follow_up_engine import next_action, FollowUpAction
from core.response_classifier import classify_reply, needs_human_escalation
from core.escalation import process_reply
from core.notifier import EscalationNotifier
from providers.email_provider import EmailProvider
from providers.sms_provider import SMSProvider
from providers.whatsapp_provider import WhatsAppProvider


def log(msg: str, tag: str = "SCHEDULER"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{tag}] {msg}")


def get_provider(channel: str):
    """Reuses the same provider lookup pattern from demo.py."""
    return {
        "email": EmailProvider(),
        "sms": SMSProvider(),
        "whatsapp": WhatsAppProvider(),
    }[channel]


def check_inbound_replies(store: StateStore, leads: list) -> int:
    """
    Checks Gmail inbox for new replies from known leads, classifies them,
    and triggers instant escalation if hot.
    """
    log("Scanning Gmail inbox for new replies...", "REPLIES")

    email_to_lead = {lead.email.strip().lower(): lead for lead in leads if lead.email}
    known_emails = set(email_to_lead.keys())

    if not known_emails:
        log("No lead email addresses configured.", "REPLIES")
        return 0

    last_checked = store.get_last_reply_check()

    try:
        from providers.email_reader import fetch_replies
        replies = fetch_replies(known_emails, after_timestamp=last_checked)
    except FileNotFoundError:
        log("Gmail API credentials.json not found. Skipping live inbox check.", "WARNING")
        return 0
    except Exception as e:
        log(f"Error checking Gmail inbox: {e}", "ERROR")
        return 0

    store.record_reply_check()

    if not replies:
        log("No new replies detected.", "REPLIES")
        return 0

    log(f"Found {len(replies)} new reply(ies) from known leads!", "REPLIES")
    for reply in replies:
        sender = reply.get("sender", "").strip().lower()
        lead = email_to_lead.get(sender)
        if not lead:
            continue

        log(f"Processing reply from {lead.contact_name} <{sender}> ({lead.company})", "REPLIES")
        process_reply(
            lead=lead,
            reply_text=reply["body"],
            store=store,
            channel="email",
            received_at=reply.get("received_at"),
        )

    return len(replies)


def scan_due_follow_ups(store: StateStore, leads: list) -> int:
    """
    Scans for leads where next_follow_up_date <= today and queues or highlights
    the next follow-up message.
    """
    log("Scanning for scheduled follow-ups due today...", "FOLLOW-UP")
    today = date.today()
    due_count = 0
    channels = ["email", "sms", "whatsapp"]

    for lead in leads:
        if store.is_opted_out(lead.lead_id):
            continue

        for channel in channels:
            action = next_action(store, lead.lead_id, channel, as_of_date=today)
            if action == FollowUpAction.SEND_FOLLOW_UP:
                state = store.get_follow_up_state(lead.lead_id, channel)
                fu_num = (state["follow_up_count"] if state else 0) + 1
                log(
                    f"[DUE] {lead.company} ({lead.contact_name}) - {channel.upper()} Follow-Up #{fu_num} is due!",
                    "FOLLOW-UP"
                )
                due_count += 1
            elif action == FollowUpAction.MOVE_TO_NURTURE:
                log(
                    f"[NURTURE] Cadence complete for {lead.company} ({channel.upper()}) -> Moving to Nurture.",
                    "FOLLOW-UP"
                )

    if due_count == 0:
        log("No follow-ups are currently overdue or pending today.", "FOLLOW-UP")
    else:
        log(f"Total {due_count} follow-up action(s) due today.", "FOLLOW-UP")

    return due_count


def send_due_scheduled_messages(store: StateStore) -> int:
    """
    Checks for one-off scheduled messages whose send_at time has passed.
    Asks for human approval before sending (same pattern as follow-ups).
    """
    due = store.get_due_scheduled_messages()
    if not due:
        log("No scheduled messages are due right now.", "SCHEDULED")
        return 0

    log(f"Found {len(due)} scheduled message(s) due!", "SCHEDULED")
    sent_count = 0

    for row in due:
        print(f"\n  [SCHEDULED] Due: {row['recipient_name']} via {row['channel'].upper()}")
        print(f"    To:      {row['recipient_address']}")
        print(f"    Message: {row['body'][:150]}{'...' if len(row['body']) > 150 else ''}")
        if row['subject']:
            print(f"    Subject: {row['subject']}")

        approve = input(f"\n    Approve and send this scheduled {row['channel']} message? [y/N]: ").strip().lower()
        if approve != "y":
            print("    Skipped - remains pending, will ask again next poll.")
            continue

        try:
            provider = get_provider(row['channel'])
            if row['channel'] == 'email':
                ok = provider.send(row['recipient_address'], row['subject'], row['body'])
            else:
                ok = provider.send(row['recipient_address'], row['body'])

            if ok:
                store.mark_scheduled_message_sent(row['id'])
                sent_count += 1
                log(f"[OK] Scheduled message (id={row['id']}) sent to {row['recipient_name']}!", "SCHEDULED")
        except Exception as e:
            log(f"[ERROR] Failed to send scheduled message (id={row['id']}): {e}", "ERROR")

    return sent_count


def run_single_cycle():
    """Runs a single check cycle."""
    store = StateStore(db_path="outreach.db")
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_actionable_leads()

    print("\n" + "=" * 65)
    log("Starting automated background scan cycle...")
    print("=" * 65)

    replies_count = check_inbound_replies(store, leads)
    followups_count = scan_due_follow_ups(store, leads)
    scheduled_count = send_due_scheduled_messages(store)

    log(f"Cycle completed. [Replies: {replies_count}, Follow-ups due: {followups_count}, Scheduled sent: {scheduled_count}]")
    print("=" * 65 + "\n")


def run_scheduler_daemon(interval_minutes: int = 10):
    """Runs the scheduler continuously with the specified interval in minutes."""
    log(f"Outreach Background Scheduler started. Checking every {interval_minutes} minute(s).")
    log("Press Ctrl+C anytime to stop.\n")

    try:
        while True:
            run_single_cycle()

            log(f"Sleeping for {interval_minutes} minute(s) until next scan...")
            total_seconds = interval_minutes * 60
            for remaining in range(total_seconds, 0, -1):
                mins, secs = divmod(remaining, 60)
                sys.stdout.write(f"\rNext scan in: {mins:02d}:{secs:02d} | (Ctrl+C to exit)")
                sys.stdout.flush()
                time.sleep(1)
            print()

    except KeyboardInterrupt:
        print("\n")
        log("Scheduler stopped gracefully by user.", "SHUTDOWN")


def main():
    parser = argparse.ArgumentParser(description="Outreach Background Scheduler Daemon")
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Polling interval in minutes (default: 10)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scan cycle and exit immediately (for cron / testing)",
    )

    args = parser.parse_args()

    if args.once:
        run_single_cycle()
    else:
        run_scheduler_daemon(interval_minutes=args.interval)


if __name__ == "__main__":
    main()
