"""
Classifies an inbound reply into one of the categories from spec Section 8.
Demo version uses keyword matching — good enough to show the logic working live.
(Production version could swap this for an LLM-based classifier behind the
same function signature, without changing anything else in the pipeline.)
"""
from core.models import ReplyClassification

RULES = [
    (ReplyClassification.OPT_OUT, ["unsubscribe", "stop", "remove me", "opt out"]),
    (ReplyClassification.MEETING_REQUEST, ["schedule a call", "book a call", "meet", "meeting", "calendar"]),
    (ReplyClassification.PRICE_REQUEST, ["price", "pricing", "cost", "quote", "how much"]),
    (ReplyClassification.NOT_INTERESTED, ["not interested", "no thanks", "not looking"]),
    (ReplyClassification.NOT_NOW, ["not right now", "maybe later", "not now", "circle back"]),
    (ReplyClassification.WRONG_PERSON, ["wrong person", "not the right contact", "reach out to"]),
    (ReplyClassification.REQUEST_FOR_INFORMATION, ["tell me more", "more information", "more details", "send details"]),
    (ReplyClassification.INTERESTED, ["interested", "sounds good", "tell me how", "let's talk"]),
]


def classify_reply(reply_text: str) -> ReplyClassification:
    text = reply_text.lower()
    for classification, keywords in RULES:
        if any(kw in text for kw in keywords):
            return classification
    return ReplyClassification.UNKNOWN


ESCALATE_IMMEDIATELY = {
    ReplyClassification.MEETING_REQUEST,
    ReplyClassification.PRICE_REQUEST,
    ReplyClassification.HOT,
}


def needs_human_escalation(classification: ReplyClassification) -> bool:
    return classification in ESCALATE_IMMEDIATELY


# ==============================================================================
# SECTION 14: HUMAN ESCALATION SIGNAL DETECTORS (9 DISTINCT TRIGGERS)
#
# Detects patterns of language already present in inbound reply text.
# Purely keyword/pattern-based content signal detection, keeping every match
# explainable and transparent without guessing or inferring lead data.
# ==============================================================================
import re
from typing import Optional, List, Dict


# --- Trigger 1: Meeting Request ---
def _detect_meeting_request(text: str) -> Optional[Dict[str, str]]:
    """Detects requests to book or schedule a call/meeting."""
    patterns = [
        r"\b(?:schedule|book|set up|hop on|jump on|have)\s+(?:a\s+)?(?:call|meeting|chat|demo)\b",
        r"\b(?:can we meet|let's meet|meet next|available for a call|calendar link|calendly)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return {"trigger": "meeting_request", "matched_phrase": m.group(0)}
    return None


# --- Trigger 2: Pricing Inquiry ---
def _detect_pricing_inquiry(text: str) -> Optional[Dict[str, str]]:
    """Detects inquiries about cost, pricing models, quotes, or rates."""
    # Exclude technical phrases like 'rate limit' or 'rate limiting'
    patterns = [
        r"\b(?:pricing|pricing packages?|prices?|costs?|quotes?|rate card|hourly rates?|day rates?|billing rates?|how much (?:do you charge|does it cost)|fee structure|commercials)\b",
        r"\b(?:what are your rates|your rates|their rates)\b",
        r"\brates\b(?!\s*limit)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return {"trigger": "pricing_inquiry", "matched_phrase": m.group(0)}
    return None


# --- Trigger 3: Proposal Request ---
def _detect_proposal_request(text: str) -> Optional[Dict[str, str]]:
    """Detects explicit requests for formal proposals, SOWs, or RFPs."""
    patterns = [
        r"\b(?:send(?:ing)?(?:\s+over)?\s+a\s+proposal|formal proposal|submit a proposal|proposal|statement of work|sow|rfp|request for proposal)\b"
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return {"trigger": "proposal_request", "matched_phrase": m.group(0)}
    return None


# --- Trigger 4: Company Profile Request ---
def _detect_company_profile_request(text: str) -> Optional[Dict[str, str]]:
    """Detects requests for company portfolio, credentials, case studies, or profile."""
    patterns = [
        r"\b(?:company profile|your portfolio|case studies|case study|past work|previous work|your credentials|credentials|tell us about your company|pitch deck|presentation deck|client references)\b"
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return {"trigger": "company_profile_request", "matched_phrase": m.group(0)}
    return None


# --- Trigger 5: Project Description Provided ---
def _detect_project_description_provided(text: str) -> Optional[Dict[str, str]]:
    """
    Detects detailed project descriptions (heuristically length >= 30 words
    with phrases explaining what the prospect is building or needs).
    """
    words = text.split()
    if len(words) < 30:
        return None

    project_indicators = [
        r"\b(?:we need|we're building|we are building|our project|we want to build|we are looking to build|we're looking to build|we are developing|we're developing|our platform|our application|our app|our system|currently working on)\b"
    ]
    for pattern in project_indicators:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            start = max(0, m.start() - 10)
            end = min(len(text), m.end() + 50)
            snippet = text[start:end].strip()
            return {"trigger": "project_description_provided", "matched_phrase": snippet}
    return None


# --- Trigger 6: Project Requirements Provided ---
def _detect_project_requirements_provided(text: str) -> Optional[Dict[str, str]]:
    """
    Detects concrete project requirements or spec language (e.g. 'must have',
    'requirements are', 'we require', or bulleted spec lists).
    """
    spec_patterns = [
        r"\b(?:must have|requirements are|the requirements are|our requirements|we require|key requirements|scope of work|deliverables|acceptance criteria|specifications)\b",
    ]
    for pattern in spec_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            end = min(len(text), m.end() + 50)
            snippet = text[m.start():end].strip()
            return {"trigger": "project_requirements_provided", "matched_phrase": snippet}

    # Structured bulleted or numbered list (at least 2 items)
    list_items = re.findall(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+(.+)$", text)
    if len(list_items) >= 2:
        return {
            "trigger": "project_requirements_provided",
            "matched_phrase": f"List of {len(list_items)} requirements (e.g. '{list_items[0][:40]}')"
        }
    return None


# --- Trigger 7: Technical Question ---
def _detect_technical_question(text: str) -> Optional[Dict[str, str]]:
    """
    Detects technical questions: presence of '?' combined with technical
    architecture, stack, security, or infra terms.
    """
    if "?" not in text and not re.search(r"\b(?:how do you handle|what is your approach|can you integrate|do you support)\b", text, re.IGNORECASE):
        return None

    tech_terms = [
        r"\b(?:api|apis|database|databases|architecture|tech stack|stack|integration|integrations|security|scalable|scalability|hosting|cloud|latency|rate limit(?:ing)?|oauth|encryption|microservices|infrastructure|backend|frontend|devops|sla|uptime|kubernetes|docker|aws|azure|gcp)\b"
    ]
    for pattern in tech_terms:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            sentences = re.split(r"(?<=[.?!])\s+", text)
            for s in sentences:
                if "?" in s and re.search(pattern, s, re.IGNORECASE):
                    return {"trigger": "technical_question", "matched_phrase": s.strip()}
            return {"trigger": "technical_question", "matched_phrase": m.group(0)}
    return None


# --- Trigger 8: Budget Indicated ---
def _detect_budget_indicated(text: str) -> Optional[Dict[str, str]]:
    """
    Detects monetary amounts or explicit budget declarations.
    """
    patterns = [
        r"([$₹£€]\s*[\d,]+(?:\.\d+)?\s*(?:k|m|kilo|million|lac|lakh|crore)?)",
        r"(\b[\d,]+(?:\.\d+)?\s*(?:usd|inr|eur|gbp|k\b|dollars?|rupees?))",
        r"\b(?:our budget is|budget of|we can spend|allocated budget|spending limit|budget range|budget cap)\s*([$₹£€]?\s*[\d,]+[a-zA-Z]*)?",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            snippet = m.group(0).strip()
            if snippet:
                return {"trigger": "budget_indicated", "matched_phrase": snippet}
    return None


# --- Trigger 9: New Decision Maker Introduced ---
def _detect_new_decision_maker_introduced(text: str, own_email: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Detects introduction of another decision maker, colleague, or referral.
    Looks for email address patterns or referral phrases.
    Excludes own_email if provided (e.g. signature).
    """
    intro_patterns = [
        r"\b(?:cc'ing|ccing|cc'd|loop in|looping in|introduce you to|introducing you to|reach out to my colleague|my colleague|speak with|talk to|connecting you with|our cto|our tech lead|our vp|our ceo|our coo|our head of)\b",
    ]
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

    intro_match = None
    for pattern in intro_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            intro_match = m
            break

    email_match = None
    for em in re.finditer(email_pattern, text):
        if own_email and em.group(0).strip().lower() == own_email.strip().lower():
            continue
        email_match = em
        break

    if intro_match and email_match:
        return {
            "trigger": "new_decision_maker_introduced",
            "matched_phrase": f"{intro_match.group(0)} ({email_match.group(0)})"
        }
    elif intro_match:
        start = intro_match.start()
        end = min(len(text), intro_match.end() + 40)
        return {
            "trigger": "new_decision_maker_introduced",
            "matched_phrase": text[start:end].strip()
        }
    elif email_match:
        return {
            "trigger": "new_decision_maker_introduced",
            "matched_phrase": f"email shared: {email_match.group(0)}"
        }

    return None


def detect_additional_escalation_signals(reply_text: str, lead_email: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Detects Section-14-style escalation triggers that aren't already
    covered by the main classification categories. Returns a list of
    {trigger: str, matched_phrase: str} for every trigger detected —
    empty list if none. Purely keyword/pattern based, same style as
    classify_reply() — not lead-data inference.
    """
    if not reply_text:
        return []

    detectors = [
        _detect_meeting_request,
        _detect_pricing_inquiry,
        _detect_proposal_request,
        _detect_company_profile_request,
        _detect_project_description_provided,
        _detect_project_requirements_provided,
        _detect_technical_question,
        _detect_budget_indicated,
        _detect_new_decision_maker_introduced,
    ]

    signals = []
    seen_triggers = set()
    for detector in detectors:
        if detector == _detect_new_decision_maker_introduced:
            res = detector(reply_text, own_email=lead_email)
        else:
            res = detector(reply_text)
        if res and res["trigger"] not in seen_triggers:
            signals.append(res)
            seen_triggers.add(res["trigger"])

    return signals

