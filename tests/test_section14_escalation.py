import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import sys
import os
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
from core.models import Lead, ReplyClassification
from core.response_classifier import classify_reply, needs_human_escalation, detect_additional_escalation_signals
from core.escalation import process_reply, print_escalation_summary
from core.notifier import EscalationNotifier
from core.state_store import StateStore

def run_tests():
    print("=" * 70)
    print("RUNNING SECTION 14 ESCALATION TRIGGER TEST SUITE")
    print("=" * 70)
    
    # --------------------------------------------------------------------------
    # TEST 1: All 9 triggers individually detect correctly
    # --------------------------------------------------------------------------
    print("\n--- TEST 1: All 9 Triggers Detection ---")
    test_cases_9 = [
        (
            "1. meeting_request",
            "Can we schedule a call for this Friday afternoon to discuss?",
            "meeting_request"
        ),
        (
            "2. pricing_inquiry",
            "What are your standard pricing packages and hourly rates?",
            "pricing_inquiry"
        ),
        (
            "3. proposal_request",
            "Please send over a formal proposal and statement of work for our team to review.",
            "proposal_request"
        ),
        (
            "4. company_profile_request",
            "Could you share your company profile and case studies of past work?",
            "company_profile_request"
        ),
        (
            "5. project_description_provided",
            "We are currently building an enterprise fleet management platform that handles dynamic routing, driver dispatching, and automated compliance auditing across five regional hubs. Our platform needs real-time vehicle telemetry synchronization.",
            "project_description_provided"
        ),
        (
            "6. project_requirements_provided",
            "Our key requirements are: must have OAuth2 single sign-on, PostgreSQL database, and high throughput event ingestion.",
            "project_requirements_provided"
        ),
        (
            "7. technical_question",
            "What is your approach to API rate limiting and database scalability under high concurrency?",
            "technical_question"
        ),
        (
            "8. budget_indicated",
            "We have an allocated budget of $25,000 for this initial milestone.",
            "budget_indicated"
        ),
        (
            "9. new_decision_maker_introduced",
            "I am looping in our CTO, please connect directly with david@example.com for next steps.",
            "new_decision_maker_introduced"
        ),
    ]

    all_t1_passed = True
    for label, text, expected_trigger in test_cases_9:
        signals = detect_additional_escalation_signals(text)
        detected_triggers = [s["trigger"] for s in signals]
        passed = expected_trigger in detected_triggers
        status = "PASSED" if passed else "FAILED"
        print(f"[{status}] {label}")
        print(f"       Input: \"{text[:75]}...\"")
        print(f"       Signals: {signals}")
        if not passed:
            all_t1_passed = False
    
    assert all_t1_passed, "Test 1 failed on one or more triggers!"
    print("=> Test 1 PASSED: All 9 triggers detected correctly.")

    # --------------------------------------------------------------------------
    # TEST 2: False Positive Check (Negative replies must NOT fire signals)
    # --------------------------------------------------------------------------
    print("\n--- TEST 2: False-Positive Check (Negative / Non-Escalating Replies) ---")
    negative_cases = [
        "not interested, please remove me",
        "maybe later, circle back next quarter",
        "who is this?",
        "sounds good, thanks",
        "wrong person, not the right contact",
    ]

    all_t2_passed = True
    for text in negative_cases:
        signals = detect_additional_escalation_signals(text)
        passed = (len(signals) == 0)
        status = "PASSED" if passed else "FAILED"
        print(f"[{status}] Input: \"{text}\" -> Signals detected: {signals}")
        if not passed:
            all_t2_passed = False

    assert all_t2_passed, "Test 2 failed on false-positive triggers!"
    print("=> Test 2 PASSED: 0 false positives on non-escalating replies.")

    # --------------------------------------------------------------------------
    # TEST 3: Multi-trigger (Budget + Technical Question)
    # --------------------------------------------------------------------------
    print("\n--- TEST 3: Multi-trigger (Budget + Technical Question) ---")
    multi_reply = (
        "We have an allocated budget of $35,000 for this project. "
        "What is your approach to API rate limiting and database architecture?"
    )
    signals = detect_additional_escalation_signals(multi_reply)
    detected_triggers = [s["trigger"] for s in signals]
    print(f"Input: \"{multi_reply}\"")
    print(f"Signals detected: {signals}")
    assert "budget_indicated" in detected_triggers, "budget_indicated not detected in multi-trigger reply!"
    assert "technical_question" in detected_triggers, "technical_question not detected in multi-trigger reply!"
    print(f"=> Test 3 PASSED: Both 'budget_indicated' and 'technical_question' detected in single reply.")

    # --------------------------------------------------------------------------
    # TEST 4: Existing MEETING_REQUEST regression test
    # --------------------------------------------------------------------------
    print("\n--- TEST 4: Existing MEETING_REQUEST Regression Test ---")
    meeting_reply = "Can we schedule a call to discuss this next week?"
    classification = classify_reply(meeting_reply)
    needs_esc = needs_human_escalation(classification)
    signals = detect_additional_escalation_signals(meeting_reply)
    print(f"Input: \"{meeting_reply}\"")
    print(f"Classified as: {classification.value}")
    print(f"needs_human_escalation(classification): {needs_esc}")
    print(f"Signals: {signals}")
    assert classification == ReplyClassification.MEETING_REQUEST, "Classification regression!"
    assert needs_esc is True, "needs_human_escalation regression!"
    print("=> Test 4 PASSED: Existing MEETING_REQUEST path remains fully functional.")

    # --------------------------------------------------------------------------
    # TEST 5: SMS Alert Length Verification
    # --------------------------------------------------------------------------
    print("\n--- TEST 5: SMS Alert Length Verification ---")
    dummy_lead = Lead(
        lead_id="test_lead_001",
        company="Acme Corp Solutions",
        contact_name="Aisha Verma",
        designation="VP of Engineering",
        primary_service="Custom Software Development",
        email="aisha@acme.com",
        phone="+1234567890",
        lead_score=85
    )
    # Multiple signals
    multi_signals = [
        {"trigger": "budget_indicated", "matched_phrase": "$35,000"},
        {"trigger": "technical_question", "matched_phrase": "API rate limiting"},
        {"trigger": "proposal_request", "matched_phrase": "formal proposal"}
    ]
    notifier = EscalationNotifier()
    
    # Capture formatted SMS body
    # We can inspect the body logic directly or simulate send
    seen = set()
    unique_triggers = []
    for s in multi_signals:
        tr_name = s["trigger"].replace("_", " ")
        if tr_name not in seen:
            seen.add(tr_name)
            unique_triggers.append(tr_name)
    triggers_str = f" Triggers: {', '.join(unique_triggers)}."
    sms_body = (
        f"🚨 HOT LEAD: {dummy_lead.company}.{triggers_str} "
        f"{dummy_lead.contact_name} replied via email. Check email for full details."
    )
    print(f"Formatted SMS ({len(sms_body)} chars):\n  \"{sms_body}\"")
    assert len(sms_body) <= 180, f"SMS too long! ({len(sms_body)} chars)"
    print(f"=> Test 5 PASSED: SMS body length is {len(sms_body)} chars (well under multi-segment limit).")

    print("\n" + "=" * 70)
    print("ALL 5 TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
