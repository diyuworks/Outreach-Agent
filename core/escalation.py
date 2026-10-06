"""
Shared escalation display logic.

Extracted from demo.py so both demo.py and check_replies.py can reuse
the same escalation summary block without duplicating code.
"""
import os
from typing import Optional, List, Dict
from core.models import Lead, ReplyClassification
from core.response_classifier import classify_reply, needs_human_escalation, detect_additional_escalation_signals
from core.notifier import EscalationNotifier
from providers.email_provider import EmailProvider
from providers.sms_provider import SMSProvider
from providers.whatsapp_provider import WhatsAppProvider
from datetime import datetime

_notifier = EscalationNotifier()  # module-level, reused across calls

# How many hours we tell the LEAD to expect a response in. Kept as a
# constant so it's easy to change without hunting through message strings.
ESCALATION_RESPONSE_ETA_HOURS = int(os.getenv("ESCALATION_RESPONSE_ETA_HOURS", "2"))

# IMPORTANT DESIGN NOTE: this confirmation is sent to the LEAD automatically,
# without an interactive approval prompt — unlike every other outbound
# message in this project. This is a deliberate exception, not an oversight:
# process_reply() is called from background/non-interactive contexts
# (scheduler.py, webhook_server.py, check_replies.py) where a blocking
# input() prompt would hang the process. The message itself is a short,
# factual acknowledgment (not a sales pitch), which keeps the risk low.
# Set AUTO_SEND_ETA_CONFIRMATION=false in .env to disable this entirely if
# that tradeoff isn't acceptable — no ETA confirmation will be sent, but
# nothing else in the escalation flow is affected.
AUTO_SEND_ETA_CONFIRMATION = os.getenv("AUTO_SEND_ETA_CONFIRMATION", "true").lower() != "false"


def print_escalation_summary(lead: Lead, reply_text: str,
                             classification: ReplyClassification,
                             additional_signals: Optional[List[Dict[str, str]]] = None):
    """Print the escalation summary block for an escalated lead reply."""
    print("  *** ESCALATION TRIGGERED — human salesperson notified ***")
    print(f"  Company: {lead.company}")
    print(f"  Contact: {lead.contact_name} ({lead.designation})")
    print(f"  Requirement: {lead.primary_service}")
    print(f"  Lead score: {lead.lead_score}")
    print(f"  Reply: \"{reply_text}\"")
    if additional_signals:
        print("  Escalation triggers detected:")
        for sig in additional_signals:
            print(f"    - {sig['trigger']}: \"{sig['matched_phrase']}\"")
    else:
        print(f"  Escalation trigger: {classification.value}")
    print(f"  Recommended next action: Reach out within 24h to schedule "
          f"the requested meeting/pricing call.")


def send_eta_confirmation(lead: Lead, channel: str, store) -> None:
    """
    Send the LEAD a short response-time confirmation on the same channel
    they replied on. See AUTO_SEND_ETA_CONFIRMATION note above for why this
    doesn't go through the usual interactive approval prompt.
    """
    auto_send = os.getenv("AUTO_SEND_ETA_CONFIRMATION", "true").lower() != "false"
    if not auto_send:
        print("  [ETA] Response-time confirmation disabled via AUTO_SEND_ETA_CONFIRMATION=false.")
        return

    if store.is_opted_out(lead.lead_id):
        print("  [ETA] Lead is opted out — skipping response-time confirmation.")
        return

    body = (
        f"Thanks for reaching out, {lead.contact_name}! Someone from our team "
        f"will get back to you within {ESCALATION_RESPONSE_ETA_HOURS} business "
        f"hours to discuss {lead.primary_service}."
    )

    sent = False
    if channel == "email" and lead.email:
        sent = EmailProvider().send(lead.email, f"Re: {lead.company} — we'll be in touch", body)
    elif channel == "sms" and lead.phone:
        sent = SMSProvider().send(lead.phone, body)
    elif channel == "whatsapp" and lead.phone:
        sent = WhatsAppProvider().send(lead.phone, body)
    else:
        print(f"  [ETA] No usable address for channel '{channel}' — skipping confirmation.")
        return

    if sent:
        print(f"  [ETA] Response-time confirmation sent to {lead.contact_name} via {channel}.")


def process_reply(lead: Lead, reply_text: str, store, channel: str = "email", received_at: str = None):
    """
    Classify a reply, record it in the store, handle opt-out and escalation.

    Returns the ReplyClassification.
    """
    classification = classify_reply(reply_text)
    additional_signals = detect_additional_escalation_signals(reply_text, lead_email=lead.email if lead else None)

    store.record_reply(lead.lead_id, channel, classification, reply_text=reply_text, received_at=received_at)
    print(f"\n  Classified as: {classification.value}")

    if classification == ReplyClassification.OPT_OUT:
        store.record_opt_out(lead.lead_id)

    should_escalate = (
        needs_human_escalation(classification)
        or len(additional_signals) > 0
    )

    if should_escalate:
        print("-" * 70)
        print_escalation_summary(lead, reply_text, classification, additional_signals)
        print("-" * 70)

        received_at = received_at or datetime.now().isoformat(timespec="seconds")
        reply_key = f"{lead.lead_id}:{channel}:{received_at}"
        if not store.escalation_already_sent(reply_key):
            _notifier.notify(lead, reply_text, classification, channel, received_at, additional_signals=additional_signals)
            store.record_escalation_sent(reply_key)
            send_eta_confirmation(lead, channel, store)
        else:
            print("  [NOTIFIER] Alert already sent for this reply — skipping duplicate.")
    else:
        print(f"  -> No immediate escalation needed for this classification.")

    return classification

