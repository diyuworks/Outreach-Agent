"""
Dynamic Lead Scoring Intelligence Engine.

Recalculates lead scores in real-time based on engagement signals:
  - Base score (from CSV / Lead Gen team import)
  - Reply sentiment (HOT / INTERESTED / MEETING_REQUEST / OPT_OUT etc.)
  - Reply speed (how quickly the prospect responded)
  - Multi-channel engagement (replied on multiple channels)
  - Follow-up responsiveness (replied after fewer follow-ups = higher intent)
  - Opt-out penalty (hard suppression)
  - Opportunity value bonus

Each signal contributes a weighted modifier to the base score.
Score is always clamped to 0–100.

Usage:
    from lead_scoring import compute_dynamic_score, get_score_breakdown
    score = compute_dynamic_score(lead, store)
    breakdown = get_score_breakdown(lead, store)
"""
from datetime import datetime, timedelta
from typing import Optional


# ---------- Signal Weights ----------
WEIGHTS = {
    # Reply Classification Modifiers (additive to base score)
    "reply_HOT":                    +15,
    "reply_MEETING_REQUEST":        +15,
    "reply_INTERESTED":             +12,
    "reply_PRICE_REQUEST":          +10,
    "reply_REQUEST_FOR_INFORMATION": +8,
    "reply_NOT_NOW":                 -5,
    "reply_WRONG_PERSON":           -10,
    "reply_NOT_INTERESTED":         -15,
    "reply_OPT_OUT":                -30,
    "reply_UNKNOWN":                 +2,

    # Engagement Signals
    "has_any_reply":                 +5,   # prospect engaged at all
    "multi_channel_reply":           +8,   # replied on 2+ channels
    "fast_reply":                   +10,   # replied within 24 hours
    "medium_reply":                  +5,   # replied within 72 hours

    # Follow-Up Efficiency
    "replied_on_initial":           +10,   # replied without needing follow-ups
    "replied_after_1_followup":      +5,   # replied after 1 follow-up
    "needed_3plus_followups":        -5,   # needed 3+ follow-ups (low intent)

    # Opt-Out Hard Penalty
    "opted_out":                    -40,

    # Opportunity Value Bonus
    "high_opp_value":                +5,   # opportunity_value >= 50000
    "very_high_opp_value":           +8,   # opportunity_value >= 100000

    # Recency Bonus (contacted recently = warmer lead)
    "contacted_last_7_days":         +3,
    "contacted_last_30_days":        +1,
    "stale_no_contact_30_days":      -5,
}


def _get_engagement_signals(lead, store) -> dict:
    """
    Query the database for all engagement signals for a given lead.
    Returns a dict of signal_name -> True/False.
    """
    signals = {}
    lead_id = lead.lead_id if hasattr(lead, 'lead_id') else lead.get('lead_id', '')

    # 1. Check all follow_up_state records across channels
    channels = ["email", "sms", "whatsapp"]
    reply_channels = []
    reply_classifications = []
    min_follow_ups_to_reply = None
    fastest_reply_hours = None

    for ch in channels:
        state = store.get_follow_up_state(lead_id, ch)
        if state and state["reply_classification"]:
            reply_channels.append(ch)
            reply_classifications.append(state["reply_classification"])

            fu_count = state["follow_up_count"] or 0
            if min_follow_ups_to_reply is None or fu_count < min_follow_ups_to_reply:
                min_follow_ups_to_reply = fu_count

            # Calculate reply speed
            if state["reply_received_at"] and state["last_message_at"]:
                try:
                    sent_dt = datetime.fromisoformat(state["last_message_at"])
                    reply_dt = datetime.fromisoformat(state["reply_received_at"])
                    hours_diff = (reply_dt - sent_dt).total_seconds() / 3600
                    if fastest_reply_hours is None or hours_diff < fastest_reply_hours:
                        fastest_reply_hours = hours_diff
                except (ValueError, TypeError):
                    pass

    # Has any reply
    signals["has_any_reply"] = len(reply_channels) > 0

    # Multi-channel reply
    signals["multi_channel_reply"] = len(reply_channels) >= 2

    # Reply speed
    if fastest_reply_hours is not None:
        signals["fast_reply"] = fastest_reply_hours <= 24
        signals["medium_reply"] = 24 < fastest_reply_hours <= 72
    else:
        signals["fast_reply"] = False
        signals["medium_reply"] = False

    # Follow-up efficiency
    if min_follow_ups_to_reply is not None:
        signals["replied_on_initial"] = min_follow_ups_to_reply == 0
        signals["replied_after_1_followup"] = min_follow_ups_to_reply == 1
        signals["needed_3plus_followups"] = min_follow_ups_to_reply >= 3
    else:
        signals["replied_on_initial"] = False
        signals["replied_after_1_followup"] = False
        signals["needed_3plus_followups"] = False

    # Reply classification signals (use the best/most positive classification)
    for cls in reply_classifications:
        signals[f"reply_{cls}"] = True

    # 2. Opt-out check
    signals["opted_out"] = store.is_opted_out(lead_id)

    # 3. Opportunity value
    opp_value = None
    crm = store.get_lead_crm(lead_id)
    if crm and crm.get("opportunity_value") is not None:
        opp_value = crm["opportunity_value"]
    elif hasattr(lead, 'opportunity_value') and lead.opportunity_value is not None:
        opp_value = lead.opportunity_value

    signals["high_opp_value"] = (opp_value or 0) >= 50000
    signals["very_high_opp_value"] = (opp_value or 0) >= 100000

    # 4. Recency — when was the last message sent?
    try:
        row = store.conn.execute(
            "SELECT MAX(sent_at) as last_sent FROM messages WHERE lead_id = ? AND sent = 1",
            (lead_id,)
        ).fetchone()
        if row and row["last_sent"]:
            last_sent_dt = datetime.fromisoformat(row["last_sent"])
            days_since = (datetime.now() - last_sent_dt).days
            signals["contacted_last_7_days"] = days_since <= 7
            signals["contacted_last_30_days"] = 7 < days_since <= 30
            signals["stale_no_contact_30_days"] = days_since > 30
        else:
            signals["contacted_last_7_days"] = False
            signals["contacted_last_30_days"] = False
            signals["stale_no_contact_30_days"] = False
    except Exception:
        signals["contacted_last_7_days"] = False
        signals["contacted_last_30_days"] = False
        signals["stale_no_contact_30_days"] = False

    return signals


def compute_dynamic_score(lead, store) -> int:
    """
    Compute the dynamic lead score (0-100) based on base score + engagement signals.
    """
    # Base score from CSV / Lead Gen
    base = 50  # default if no base score
    if hasattr(lead, 'lead_score') and lead.lead_score is not None:
        base = lead.lead_score
    elif isinstance(lead, dict) and lead.get('lead_score') is not None:
        try:
            base = int(lead['lead_score'])
        except (ValueError, TypeError):
            base = 50

    signals = _get_engagement_signals(lead, store)
    modifier = 0

    for signal_name, is_active in signals.items():
        if is_active and signal_name in WEIGHTS:
            modifier += WEIGHTS[signal_name]

    # Clamp to 0-100
    return max(0, min(100, base + modifier))


def get_score_breakdown(lead, store) -> dict:
    """
    Return a detailed breakdown of the dynamic score for display in the dashboard.
    Shows base score, each active signal, its weight, and the final computed score.
    """
    base = 50
    if hasattr(lead, 'lead_score') and lead.lead_score is not None:
        base = lead.lead_score
    elif isinstance(lead, dict) and lead.get('lead_score') is not None:
        try:
            base = int(lead['lead_score'])
        except (ValueError, TypeError):
            base = 50

    signals = _get_engagement_signals(lead, store)
    active_signals = []
    total_modifier = 0

    for signal_name, is_active in signals.items():
        if is_active and signal_name in WEIGHTS:
            weight = WEIGHTS[signal_name]
            total_modifier += weight
            # Human-readable signal name
            label = signal_name.replace("_", " ").replace("reply ", "Reply: ").title()
            active_signals.append({
                "signal": signal_name,
                "label": label,
                "weight": weight,
                "direction": "boost" if weight > 0 else "penalty"
            })

    final_score = max(0, min(100, base + total_modifier))

    return {
        "base_score": base,
        "modifier": total_modifier,
        "final_score": final_score,
        "signals": active_signals,
        "signal_count": len(active_signals)
    }


def recalculate_all_leads(leads: list, store) -> list:
    """
    Recalculate dynamic scores for a list of leads.
    Returns list of dicts with lead_id, base_score, dynamic_score, modifier, and breakdown.
    """
    results = []
    for lead in leads:
        lead_id = lead.lead_id if hasattr(lead, 'lead_id') else lead.get('lead_id', '')
        breakdown = get_score_breakdown(lead, store)
        results.append({
            "lead_id": lead_id,
            "base_score": breakdown["base_score"],
            "dynamic_score": breakdown["final_score"],
            "modifier": breakdown["modifier"],
            "breakdown": breakdown
        })
    return results
