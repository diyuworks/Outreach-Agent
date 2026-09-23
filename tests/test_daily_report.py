import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""
Automated verification for Spec Section 17 Daily Operating Report.
Tests all 5 required verification steps:
1. Day with activity matches database counts directly.
2. Major objections displays verbatim NOT_INTERESTED text quotes.
3. Recommended strategy changes is left blank for human evaluation.
4. Report is written to a dated markdown file in reports/.
5. Zero-activity date handles all-zero counts and empty sections gracefully.
"""
import os
import sys
from datetime import datetime

from state_store import StateStore
from models import Lead, LeadStatus, Channel, ReplyClassification, DraftMessage
from escalation import process_reply
from daily_report import generate_daily_report


def run_tests():
    print("=================================================================")
    print("STARTING SPEC SECTION 17 DAILY OPERATING REPORT VERIFICATION")
    print("=================================================================\n")

    today_str = datetime.now().strftime("%Y-%m-%d")
    store = StateStore(db_path="outreach.db")

    # 1. Setup simulated activity for today
    print("Step 1: Setting up simulated activity for today...")

    # Create test lead object
    test_lead = Lead(
        lead_id="L001",
        company="BrightCart Retail",
        contact_name="Aisha Verma",
        email="aisha@brightcart.example",
        lead_score=88,
        lead_status=LeadStatus.QUALIFIED,
        primary_service="eCommerce Development",
        personalization_hook="recently announced expansion into three new cities"
    )

    # Simulate message sent
    draft = DraftMessage(
        lead_id="L001",
        channel=Channel.EMAIL,
        subject="Intro to eCommerce services",
        body="Hi Aisha, loved your expansion news."
    )
    msg_id = store.queue_for_approval(draft)
    store.approve_message(msg_id, approved_by="Human Reviewer")
    store.mark_sent(msg_id)
    print(f"  [Activity] Message sent (ID: {msg_id})")

    # Simulate a positive reply (INTERESTED)
    process_reply(
        lead=test_lead,
        reply_text="Sounds interesting, could you send more details?",
        store=store,
        channel="email",
        received_at=datetime.now().isoformat()
    )
    print("  [Activity] Simulated INTERESTED reply recorded.")

    # Simulate a MEETING_REQUEST reply
    process_reply(
        lead=test_lead,
        reply_text="Can we get on a quick Zoom call tomorrow at 3 PM?",
        store=store,
        channel="email",
        received_at=datetime.now().isoformat()
    )
    print("  [Activity] Simulated MEETING_REQUEST reply recorded.")

    # Simulate a NOT_INTERESTED reply with specific verbatim text
    verbatim_objection = "We already signed an enterprise contract with another agency last week, so we are not interested at this time."
    process_reply(
        lead=test_lead,
        reply_text=verbatim_objection,
        store=store,
        channel="email",
        received_at=datetime.now().isoformat()
    )
    print(f"  [Activity] Simulated NOT_INTERESTED objection recorded: '{verbatim_objection}'")

    # Generate Report for today
    print("\nStep 2: Generating Report for today...")
    report_today = generate_daily_report(target_date=today_str)
    metrics = report_today["metrics"]
    text = report_today["text"]

    # Verify counts match database directly
    db_sent = store.get_daily_messages_sent_count(today_str)
    db_replies = store.get_daily_replies(today_str)
    db_pos = sum(1 for r in db_replies if r["classification"] in ("INTERESTED", "HOT"))
    db_meetings = sum(1 for r in db_replies if r["classification"] == "MEETING_REQUEST")

    assert metrics["messages_sent"] == db_sent, f"Messages sent mismatch: {metrics['messages_sent']} vs {db_sent}"
    assert metrics["replies_count"] == len(db_replies), f"Replies count mismatch: {metrics['replies_count']} vs {len(db_replies)}"
    assert metrics["positive_replies_count"] == db_pos, f"Positive replies mismatch: {metrics['positive_replies_count']} vs {db_pos}"
    assert metrics["meetings_count"] == db_meetings, f"Meetings count mismatch: {metrics['meetings_count']} vs {db_meetings}"
    print("  [PASS] Test 1: Active day counts match database queries directly.")

    # Verify Test 2: Major objections contains verbatim quote
    assert verbatim_objection in text, "Verbatim objection text not found in generated report!"
    assert "Major objections:" in text
    print("  [PASS] Test 2: Major objections contains verbatim quote, not a generated summary.")

    # Verify Test 3: Recommended strategy changes is blank for human input
    assert "Recommended strategy changes:" in text
    assert "[                                                                    ]" in text
    assert "(fill in manually" in text
    print("  [PASS] Test 3: Recommended strategy changes is blank and marked for manual input.")

    # Verify Test 4: Dated report file written to reports/
    expected_file = os.path.join("reports", f"daily_report_{today_str}.md")
    assert os.path.exists(expected_file), f"Report file {expected_file} was not found!"
    with open(expected_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert content.strip() == text.strip(), "File content does not match generated report text!"
    print(f"  [PASS] Test 4: Report successfully saved to {expected_file}.")

    # Verify Test 5: Zero-activity day
    print("\nStep 3: Running zero-activity day test (date: 2025-01-01)...")
    zero_date = "2025-01-01"
    report_zero = generate_daily_report(target_date=zero_date)
    z_m = report_zero["metrics"]
    z_text = report_zero["text"]

    assert z_m["discovered_count"] == 0, f"Discovered count should be 0, got {z_m['discovered_count']}"
    assert z_m["qualified_count"] == 0, f"Qualified count should be 0, got {z_m['qualified_count']}"
    assert z_m["hot_leads_count"] == 0, f"HOT leads should be 0, got {z_m['hot_leads_count']}"
    assert z_m["high_leads_count"] == 0, f"HIGH leads should be 0, got {z_m['high_leads_count']}"
    assert z_m["messages_sent"] == 0, f"Messages sent should be 0, got {z_m['messages_sent']}"
    assert z_m["replies_count"] == 0, f"Replies should be 0, got {z_m['replies_count']}"
    assert z_m["positive_replies_count"] == 0, f"Positive replies should be 0, got {z_m['positive_replies_count']}"
    assert z_m["meetings_count"] == 0, f"Meetings should be 0, got {z_m['meetings_count']}"
    assert z_m["pipeline_value"] == 0.0, f"Pipeline value should be 0.0, got {z_m['pipeline_value']}"
    assert f"(none recorded for {zero_date})" in z_text, "Top 10 / objections should show empty message"
    print("  [PASS] Test 5: Zero-activity date handled gracefully with all-zero counts and empty sections.")

    print("\n=================================================================")
    print("ALL 5 TESTS PASSED SUCCESSFULLY!")
    print("=================================================================\n")
    print("Sample generated report:")
    print(text)


if __name__ == "__main__":
    run_tests()
