import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""
Verification tests for the 'new_decision_maker_introduced' trigger fix.
"""
from core.response_classifier import (
    _detect_new_decision_maker_introduced,
    detect_additional_escalation_signals
)


def run_tests():
    print("=================================================================")
    print("TESTING FIX FOR 'new_decision_maker_introduced' TRIGGER")
    print("=================================================================\n")

    lead_own_email = "aisha@brightcart.com"

    # --------------------------------------------------------------------------
    # Test 1: Lead's own email in signature should NOT fire trigger
    # --------------------------------------------------------------------------
    text_1 = "Sounds interesting. Regards, Aisha | aisha@brightcart.com"
    signals_1 = detect_additional_escalation_signals(text_1, lead_email=lead_own_email)
    triggers_1 = [s["trigger"] for s in signals_1]
    direct_1 = _detect_new_decision_maker_introduced(text_1, own_email=lead_own_email)

    print(f"Test 1 Input: \"{text_1}\"")
    print(f"  Lead own email: {lead_own_email}")
    print(f"  Direct detector output: {direct_1}")
    print(f"  Signals: {signals_1}")

    assert "new_decision_maker_introduced" not in triggers_1, "Test 1 FAILED: Trigger fired on lead's own email signature!"
    assert direct_1 is None, "Test 1 FAILED: Direct detector returned non-None for own email signature!"
    print("=> [PASS] Test 1: Own email signature does NOT fire 'new_decision_maker_introduced'.\n")

    # --------------------------------------------------------------------------
    # Test 2: Different email address (e.g. CTO) STILL fires trigger
    # --------------------------------------------------------------------------
    text_2 = "I'm looping in our CTO, david@example.com"
    signals_2 = detect_additional_escalation_signals(text_2, lead_email=lead_own_email)
    triggers_2 = [s["trigger"] for s in signals_2]
    direct_2 = _detect_new_decision_maker_introduced(text_2, own_email=lead_own_email)

    print(f"Test 2 Input: \"{text_2}\"")
    print(f"  Lead own email: {lead_own_email}")
    print(f"  Direct detector output: {direct_2}")
    print(f"  Signals: {signals_2}")

    assert "new_decision_maker_introduced" in triggers_2, "Test 2 FAILED: Trigger did not fire on different email!"
    assert direct_2 is not None, "Test 2 FAILED: Direct detector returned None for different email!"
    assert "david@example.com" in direct_2["matched_phrase"], "Test 2 FAILED: matched_phrase missing new email!"
    print("=> [PASS] Test 2: Different email STILL correctly fires 'new_decision_maker_introduced'.\n")

    # --------------------------------------------------------------------------
    # Test 3: Intro phrase alone with no email at all STILL fires
    # --------------------------------------------------------------------------
    text_3 = "Please loop in our tech lead for this"
    signals_3 = detect_additional_escalation_signals(text_3, lead_email=lead_own_email)
    triggers_3 = [s["trigger"] for s in signals_3]
    direct_3 = _detect_new_decision_maker_introduced(text_3, own_email=lead_own_email)

    print(f"Test 3 Input: \"{text_3}\"")
    print(f"  Direct detector output: {direct_3}")
    print(f"  Signals: {signals_3}")

    assert "new_decision_maker_introduced" in triggers_3, "Test 3 FAILED: Trigger did not fire on intro phrase alone!"
    assert direct_3 is not None, "Test 3 FAILED: Direct detector returned None for intro phrase alone!"
    print("=> [PASS] Test 3: Intro phrase alone with no email STILL fires correctly.\n")

    # --------------------------------------------------------------------------
    # Bonus Test: Combined text with BOTH new email AND own email signature
    # --------------------------------------------------------------------------
    text_bonus = "I am looping in our VP, sarah@example.com. Thanks!\nRegards, Aisha <aisha@brightcart.com>"
    signals_bonus = detect_additional_escalation_signals(text_bonus, lead_email=lead_own_email)
    triggers_bonus = [s["trigger"] for s in signals_bonus]
    direct_bonus = _detect_new_decision_maker_introduced(text_bonus, own_email=lead_own_email)

    print(f"Bonus Test Input: \"{text_bonus}\"")
    print(f"  Direct detector output: {direct_bonus}")
    assert "new_decision_maker_introduced" in triggers_bonus, "Bonus test FAILED: Did not detect new email when own signature was also present!"
    assert "sarah@example.com" in direct_bonus["matched_phrase"], "Bonus test FAILED: Did not match new person's email!"
    print("=> [PASS] Bonus Test: Accurately isolates new email when lead's own signature is also in the email.\n")

    print("=================================================================")
    print("ALL TESTS IN test_decision_maker_fix.py PASSED!")
    print("=================================================================")


if __name__ == "__main__":
    run_tests()
