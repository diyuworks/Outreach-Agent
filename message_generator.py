"""
Generates personalized outreach messages.
Structure (per spec Section 4/11): observation -> problem -> how we help -> CTA.
No fake urgency, no fabricated claims, no promised pricing/timelines.
"""
from models import Lead, DraftMessage, Channel

YOUR_NAME = "Priya"
YOUR_COMPANY = "SAUBHAGYAM"
COMPANY_DESCRIPTOR = (
    "a global AI and software development company delivering enterprise "
    "applications, mobile apps, cloud platforms, and digital transformation "
    "solutions for modern businesses"
)

# Generic "problem" framing per service — factual, not exaggerated
SERVICE_PAIN_POINTS = {
    "eCommerce Development": "scaling checkout, inventory, and logistics smoothly across new markets",
    "Dedicated Developers": "finding reliable, vetted developers fast without a lengthy in-house hiring cycle",
    "ERP Development": "manual, spreadsheet-based processes that slow down operations as the business grows",
    "AI/ML Development": "manual workflows that could be automated with the right AI tooling",
    "Mobile App Development": "getting a polished mobile experience to market quickly",
}


def _pain_point(service: str) -> str:
    return SERVICE_PAIN_POINTS.get(
        service, "keeping technology aligned with fast-moving business growth"
    )


def generate_email(lead: Lead, follow_up_count: int = 0) -> DraftMessage:
    service_raw = (lead.primary_service or "").strip()
    has_service = bool(service_raw)
    service_display = service_raw if has_service else "technology solutions"
    service_lower = service_display.lower()
    hook_display = (lead.personalization_hook or "growing your digital footprint").strip()
    pain = _pain_point(service_raw)
    
    if follow_up_count == 0:
        # Initial Outreach
        subject = f"Idea for {lead.company}'s {service_lower}" if has_service else f"Idea for {lead.company}"
        service_sentence = (
            f"We help businesses with {service_display}, including scoping, building, and supporting the solution end-to-end."
            if has_service else
            "We help businesses implement the right technology solutions for their needs, including scoping, building, and supporting them end-to-end."
        )
        body = (
            f"Hi {lead.contact_name},\n\n"
            f"I'm reaching out from {YOUR_COMPANY}, {COMPANY_DESCRIPTOR}.\n\n"
            f"I noticed {lead.company} {hook_display}.\n\n"
            f"Companies at this stage often run into challenges around {pain}.\n\n"
            f"{service_sentence}\n\n"
            f"Would you be open to a short conversation to see whether this could "
            f"be useful for {lead.company}?\n\n"
            f"If I don't hear back, I'll follow up in a few days with something "
            f"useful — no pressure either way.\n\n"
            f"Regards,\n{YOUR_NAME}\n{YOUR_COMPANY}\n\n"
            f"---\nDon't want to hear from us again? Reply UNSUBSCRIBE and we'll stop immediately."
        )
    elif follow_up_count == 1:
        # Follow-up #1 (Day 3): Gentle check-in / Quick bump
        subject = f"Re: Idea for {lead.company}'s {service_lower}" if has_service else f"Re: Idea for {lead.company}"
        note_ref = f"regarding {service_lower} for {lead.company}" if has_service else f"for {lead.company}"
        body = (
            f"Hi {lead.contact_name},\n\n"
            f"Following up on my previous note {note_ref}.\n\n"
            f"I know you're busy, but I wanted to make sure this didn't get buried under your inbox. "
            f"We recently helped teams streamline similar challenges around {pain}.\n\n"
            f"Would you have 10 minutes this Thursday or Friday for a quick intro chat?\n\n"
            f"Best regards,\n{YOUR_NAME}\n{YOUR_COMPANY}\n\n"
            f"---\nReply UNSUBSCRIBE to opt out."
        )
    elif follow_up_count == 2:
        # Follow-up #2 (Day 6): Value-add / Resource angle
        subject = f"Quick question regarding {lead.company}'s {service_lower}" if has_service else f"Quick question regarding {lead.company}"
        scaling_ref = f"scaling {service_lower}" if has_service else "scaling technology initiatives"
        body = (
            f"Hi {lead.contact_name},\n\n"
            f"Reaching back out with a quick thought for {lead.company}.\n\n"
            f"When {scaling_ref}, most teams face bottlenecks in execution speed and architecture. "
            f"At {YOUR_COMPANY}, we provide battle-tested engineers and turnkey digital solutions to solve this without overhead.\n\n"
            f"Are you the right person to speak with about this, or is there someone else on your team you'd recommend?\n\n"
            f"Regards,\n{YOUR_NAME}\n{YOUR_COMPANY}\n\n"
            f"---\nReply UNSUBSCRIBE to opt out."
        )
    else:
        # Follow-up #3 (Day 7+): Graceful Break-up / Move to Nurture
        subject = f"Closing the loop — {lead.company}"
        priority_phrase = f"{service_lower} isn't an active priority" if has_service else "exploring new technology solutions isn't an active priority"
        body = (
            f"Hi {lead.contact_name},\n\n"
            f"I haven't heard back, so I assume {priority_phrase} for {lead.company} right now.\n\n"
            f"I won't follow up further, but if your roadmap evolves or you need a trusted technology partner down the road, "
            f"feel free to reach back out anytime.\n\n"
            f"Wishing you and {lead.company} continued success.\n\n"
            f"Warm regards,\n{YOUR_NAME}\n{YOUR_COMPANY}"
        )
        
    return DraftMessage(lead_id=lead.lead_id, channel=Channel.EMAIL, subject=subject, body=body)


def generate_sms(lead: Lead) -> DraftMessage:
    service_raw = (lead.primary_service or "").strip()
    help_phrase = f"with {service_raw}" if service_raw else "with the right technology solutions"
    hook_display = (lead.personalization_hook or "expanding operations").strip()
    body = (
        f"Hi {lead.contact_name}, saw {lead.company} {hook_display}. "
        f"We help {help_phrase} — open to a quick chat? "
        f"I'll follow up in a few days if I don't hear back. "
        f"- {YOUR_NAME}, {YOUR_COMPANY}. Reply STOP to opt out."
    )
    return DraftMessage(lead_id=lead.lead_id, channel=Channel.SMS, body=body)


def generate_whatsapp(lead: Lead) -> DraftMessage:
    service_raw = (lead.primary_service or "").strip()
    help_phrase = f"with {service_raw}" if service_raw else "implement the right technology solutions"
    hook_display = (lead.personalization_hook or "expanding operations").strip()
    body = (
        f"Hi {lead.contact_name}, this is {YOUR_NAME} from {YOUR_COMPANY}.\n"
        f"Noticed {lead.company} {hook_display} — we help companies "
        f"{help_phrase}. Open to a quick chat this week?\n"
        f"I'll follow up in a few days if I don't hear back."
    )
    return DraftMessage(lead_id=lead.lead_id, channel=Channel.WHATSAPP, body=body)


def generate_all_channels(lead: Lead) -> list[DraftMessage]:
    drafts = []
    if lead.email:
        drafts.append(generate_email(lead))
    if lead.phone:
        drafts.append(generate_sms(lead))
        drafts.append(generate_whatsapp(lead))
    return drafts
