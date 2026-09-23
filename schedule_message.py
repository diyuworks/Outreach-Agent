"""
Schedule a one-off message for a future date/time.

Does NOT send anything itself — writes to outreach.db, and the existing
scheduler.py (already polling for follow-ups) picks it up and sends it
when due, then applies the SAME human-approval gate used everywhere else.

Usage:  python schedule_message.py
"""
from datetime import datetime
from state_store import StateStore


def main():
    print("\n" + "=" * 60)
    print("  SCHEDULE A ONE-OFF MESSAGE")
    print("=" * 60)

    name = input("\n  Recipient name: ").strip()
    if not name:
        print("  Name is required. Exiting.")
        return

    channel = input("  Channel (email / sms / whatsapp): ").strip().lower()
    if channel not in ("email", "sms", "whatsapp"):
        print("  Invalid channel. Choose: email, sms, or whatsapp.")
        return

    if channel == "email":
        address = input("  Recipient email address: ").strip()
    else:
        address = input("  Recipient phone (E.164 format, e.g. +919106998824): ").strip()
    if not address:
        print("  Address is required. Exiting.")
        return

    subject = None
    if channel == "email":
        subject = input("  Email subject line: ").strip() or None

    body = input("  Message body: ").strip()
    if not body:
        print("  Message body is required. Exiting.")
        return

    date_str = input("  Date to send (YYYY-MM-DD): ").strip()
    time_str = input("  Time to send, 24-hour format (HH:MM): ").strip()

    try:
        send_at = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        print("  Invalid date/time format. Use YYYY-MM-DD and HH:MM.")
        return

    if send_at <= datetime.now():
        print("  ⚠️  That time is in the past — please enter a future date/time.")
        return

    store = StateStore(db_path="outreach.db")
    msg_id = store.add_scheduled_message(
        recipient_name=name,
        channel=channel,
        recipient_address=address,
        body=body,
        send_at_iso=send_at.isoformat(),
        subject=subject,
    )

    print(f"\n  ✅ Scheduled (id={msg_id}):")
    print(f"     To:      {name} ({address})")
    print(f"     Channel: {channel.upper()}")
    print(f"     When:    {send_at.strftime('%d %b %Y at %H:%M')}")
    print(f"     Message: {body[:100]}{'...' if len(body) > 100 else ''}")
    print(f"\n  It will be sent automatically next time scheduler.py polls")
    print(f"  and finds it due (same human-approval flow as everything else).")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
