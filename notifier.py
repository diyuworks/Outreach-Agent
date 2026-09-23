"""
Multi-channel escalation notifier.

Sends an urgent alert (email, SMS, and optionally Slack/Discord webhook) the
moment a hot lead reply is detected (MEETING_REQUEST, PRICE_REQUEST, HOT).

Reuses the existing EmailProvider (Gmail SMTP) and SMSProvider (Twilio/
Fast2SMS, whichever is configured) — no new sending code, no new dependency.
Slack/Discord is a plain HTTP POST to a webhook URL, no SDK needed.

Deduplication: call sites must pass a unique `reply_key` (e.g.
f"{lead_id}:{channel}:{received_at_iso}") and check
StateStore.escalation_already_sent(reply_key) before calling notify(),
then StateStore.record_escalation_sent(reply_key) after. This class does
NOT do dedup itself — dedup lives in StateStore, and covers ALL alert
channels (email + sms + slack) together for one reply, not separately.
"""
import os
import json
import urllib.request
from datetime import datetime
from typing import Optional

from models import Lead, ReplyClassification
from providers.email_provider import EmailProvider
from providers.sms_provider import SMSProvider


class EscalationNotifier:
    def __init__(self):
        self.email_provider = EmailProvider()
        self.sms_provider = SMSProvider()
        self.sales_rep_email = os.getenv("SALES_REP_ALERT_EMAIL")
        self.sales_rep_phone = os.getenv("SALES_REP_ALERT_PHONE")
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL") or None

    def notify(
        self,
        lead: Lead,
        reply_text: str,
        classification: ReplyClassification,
        channel: str,
        received_at: Optional[str] = None,
        additional_signals: Optional[list] = None,
    ) -> None:
        """Fire all configured alert channels for one escalation event."""
        received_at = received_at or datetime.now().isoformat(timespec="seconds")

        if self.sales_rep_email:
            self._send_email_alert(lead, reply_text, classification, channel, received_at, additional_signals)
        else:
            print("  [NOTIFIER] SALES_REP_ALERT_EMAIL not set in .env — skipping email alert.")

        if self.sales_rep_phone:
            self._send_sms_alert(lead, reply_text, classification, channel, received_at, additional_signals)
        # SMS is optional, same as Slack — no warning printed if unset.

        if self.slack_webhook_url:
            self._send_slack_alert(lead, reply_text, classification, channel, received_at, additional_signals)
        # Slack is explicitly optional per spec — no warning printed if unset.

    # ---------- Email alert ----------
    def _send_email_alert(self, lead, reply_text, classification, channel, received_at, additional_signals=None):
        if additional_signals:
            names = [s["trigger"].replace("_", " ") for s in additional_signals]
            trigger_str = ", ".join(names[:2])
            subject = f"🚨 HOT LEAD ESCALATION: {lead.company} ({trigger_str})"
        else:
            subject = (
                f"🚨 HOT LEAD ESCALATION: {lead.company} requested a "
                f"{'meeting' if classification == ReplyClassification.MEETING_REQUEST else 'pricing discussion'}"
            )
        body = self._format_alert_body(lead, reply_text, classification, channel, received_at, additional_signals)
        ok = self.email_provider.send(self.sales_rep_email, subject, body)
        if ok:
            print(f"  [NOTIFIER] Escalation email sent to {self.sales_rep_email}")

    @staticmethod
    def _format_alert_body(lead: Lead, reply_text: str, classification: ReplyClassification,
                            channel: str, received_at: str,
                            additional_signals: Optional[list] = None) -> str:
        priority = "High Priority" if lead.lead_score >= 75 else "Medium Priority"

        if additional_signals:
            lines = [f"  - {s['trigger']}: \"{s['matched_phrase']}\"" for s in additional_signals]
            triggers_block = "Escalation Triggers Detected:\n" + "\n".join(lines) + "\n\n"
        else:
            triggers_block = f"Escalation Trigger: {classification.value}\n\n"

        return (
            f"HOT LEAD ALERT — {classification.value}\n"
            f"{'=' * 50}\n\n"
            f"{triggers_block}"
            f"Lead Info:\n"
            f"  Company: {lead.company}\n"
            f"  Contact: {lead.contact_name} ({lead.designation or 'N/A'})\n"
            f"  Country: {lead.country or 'N/A'}\n"
            f"  Website: {lead.website or 'N/A'}\n\n"
            f"AI Lead Score: {lead.lead_score}/100 ({priority})\n"
            f"Service Needed: {lead.primary_service}\n\n"
            f"Channel & Timestamp: Received via {channel.title()} on {received_at}\n\n"
            f"Inbound Message:\n  \"{reply_text}\"\n\n"
            f"Recommended Next Action:\n"
            f"  Schedule a discovery call within 24 hours.\n\n"
            f"{'=' * 50}\n"
            f"This is an automated alert from the Outreach Agent escalation system."
        )

    # ---------- SMS alert ----------
    def _send_sms_alert(self, lead, reply_text, classification, channel, received_at, additional_signals=None):
        # Kept short deliberately — SMS has practical length limits. Full
        # detail (lead score, message quote, full phrases) lives in email alert.
        if additional_signals:
            seen = set()
            unique_triggers = []
            for s in additional_signals:
                tr_name = s["trigger"].replace("_", " ")
                if tr_name not in seen:
                    seen.add(tr_name)
                    unique_triggers.append(tr_name)
            triggers_str = f" Triggers: {', '.join(unique_triggers)}."
        else:
            triggers_str = f" Intent: {classification.value}."

        body = (
            f"🚨 HOT LEAD: {lead.company}.{triggers_str} "
            f"{lead.contact_name} replied via {channel}. Check email for full details."
        )
        ok = self.sms_provider.send(self.sales_rep_phone, body)
        if ok:
            print(f"  [NOTIFIER] Escalation SMS sent to {self.sales_rep_phone}")

    # ---------- Slack / Discord webhook ----------
    def _send_slack_alert(self, lead, reply_text, classification, channel, received_at, additional_signals=None):
        priority = "High Priority" if lead.lead_score >= 75 else "Medium Priority"
        trigger_desc = classification.value
        if additional_signals:
            trigger_desc = ", ".join(s["trigger"].replace("_", " ") for s in additional_signals)

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"🚨 *HOT LEAD ESCALATION*\n*{lead.company}* — {trigger_desc}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Contact:*\n{lead.contact_name} ({lead.designation or 'N/A'})"},
                {"type": "mrkdwn", "text": f"*Score:*\n{lead.lead_score}/100 ({priority})"},
                {"type": "mrkdwn", "text": f"*Service:*\n{lead.primary_service}"},
                {"type": "mrkdwn", "text": f"*Channel:*\n{channel.title()} — {received_at}"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Message:*\n>{reply_text}"}},
            {"type": "section", "text": {"type": "mrkdwn",
                "text": "*Next action:* Schedule a discovery call within 24 hours."}},
        ]
        if additional_signals:
            triggers_text = "\n".join(f"• *{s['trigger']}*: `{s['matched_phrase']}`" for s in additional_signals)
            blocks.insert(2, {"type": "section", "text": {"type": "mrkdwn", "text": f"*Triggers:*\n{triggers_text}"}})

        payload = {
            "text": f"🚨 *HOT LEAD ESCALATION*: {lead.company} — {trigger_desc}",
            "blocks": blocks,
        }
        try:
            req = urllib.request.Request(
                self.slack_webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            print("  [NOTIFIER] Slack/Discord webhook alert sent.")
        except Exception as e:
            print(f"  [NOTIFIER] Failed to send Slack/Discord webhook: {e}")
