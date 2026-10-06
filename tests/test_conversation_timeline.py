"""
Test Suite: Conversation Timeline (per-lead, all channels)
Verifies:
1. Initial sent message + simulated reply appear in chronological order with classification.
2. Lead with no activity returns clean empty timeline state.
3. Multi-channel interleaved events (Email + SMS + Replies) in true chronological order.
4. Non-regression of existing draft generation, CRM fields, and lead-details.
5. Legacy reply records without raw text gracefully fallback without crashing.
"""
import unittest
import requests
import sqlite3
import os
import sys
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from core.state_store import StateStore
from core.lead_source import CSVLeadSource
from core.models import Lead, LeadStatus, ReplyClassification

BASE_URL = "http://127.0.0.1:5050"

class TestConversationTimeline(unittest.TestCase):
    def setUp(self):
        self.store = StateStore(db_path="outreach.db")

    def test_01_sent_and_reply_timeline(self):
        """1. Test sending initial message + reply simulation, verifying chronological timeline and classification."""
        test_lead_id = "TIMELINE-TEST-001"
        
        # Insert test lead in DB
        self.store.conn.execute("INSERT OR REPLACE INTO leads (lead_id, company, contact_name, email) VALUES (?, ?, ?, ?)",
                                (test_lead_id, "Apex Tech Solutions", "Alice Walker", "alice@apextech.example"))
        self.store.conn.commit()

        # Simulate sent email
        t1 = (datetime.now() - timedelta(minutes=10)).isoformat()
        self.store.conn.execute(
            "INSERT INTO messages (lead_id, channel, subject, body, sent, sent_at, approved, approved_by) "
            "VALUES (?, ?, ?, ?, 1, ?, 1, 'AutoTester')",
            (test_lead_id, "email", "Intro to Saubhayam Devs", "Hi Alice, scaling your backend?", t1)
        )
        self.store.conn.commit()

        # Simulate reply received
        t2 = (datetime.now() - timedelta(minutes=5)).isoformat()
        self.store.record_reply(
            lead_id=test_lead_id,
            channel="email",
            classification=ReplyClassification.MEETING_REQUEST,
            reply_text="Yes! Can we schedule a quick call this Thursday?",
            received_at=t2
        )

        # Query timeline via StateStore
        timeline = self.store.get_conversation_timeline(test_lead_id)
        self.assertGreaterEqual(len(timeline), 2)
        self.assertEqual(timeline[0]["type"], "sent")
        self.assertEqual(timeline[0]["channel"], "email")
        self.assertEqual(timeline[0]["content"], "Hi Alice, scaling your backend?")
        self.assertIsNone(timeline[0]["classification"])

        self.assertEqual(timeline[1]["type"], "received")
        self.assertEqual(timeline[1]["channel"], "email")
        self.assertIn("Thursday", timeline[1]["content"])
        self.assertEqual(timeline[1]["classification"], "MEETING_REQUEST")

        # Test API endpoint
        res = requests.get(f"{BASE_URL}/api/lead-timeline?lead_id={test_lead_id}", timeout=5)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(len(data["timeline"]), 2)

        # Clean up
        self.store.conn.execute("DELETE FROM messages WHERE lead_id = ?", (test_lead_id,))
        self.store.conn.execute("DELETE FROM replies WHERE lead_id = ?", (test_lead_id,))
        self.store.conn.execute("DELETE FROM follow_up_state WHERE lead_id = ?", (test_lead_id,))
        self.store.conn.execute("DELETE FROM leads WHERE lead_id = ?", (test_lead_id,))
        self.store.conn.commit()
        print("=> [PASS] Test 1: Sent email + reply correctly interleaved with classification in timeline.")

    def test_02_empty_timeline_for_new_lead(self):
        """2. Lead with no activity returns empty timeline cleanly."""
        fresh_lead_id = "TIMELINE-TEST-EMPTY"
        timeline = self.store.get_conversation_timeline(fresh_lead_id)
        self.assertEqual(timeline, [])

        res = requests.get(f"{BASE_URL}/api/lead-timeline?lead_id={fresh_lead_id}", timeout=5)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["timeline"], [])
        print("=> [PASS] Test 2: Clean empty timeline for lead with zero message activity.")

    def test_03_multi_channel_interleaved_chronology(self):
        """3. Multi-channel events (Email + SMS + Replies) are strictly interleaved by chronological timestamp."""
        test_lead_id = "TIMELINE-TEST-MULTICHANNEL"

        now = datetime.now()
        t_email_sent = (now - timedelta(hours=3)).isoformat()
        t_sms_sent = (now - timedelta(hours=2)).isoformat()
        t_sms_reply = (now - timedelta(hours=1)).isoformat()
        t_email_reply = now.isoformat()

        # 1. Email sent
        self.store.conn.execute(
            "INSERT INTO messages (lead_id, channel, subject, body, sent, sent_at) VALUES (?, 'email', 'Subject 1', 'Email Content', 1, ?)",
            (test_lead_id, t_email_sent)
        )
        # 2. SMS sent
        self.store.conn.execute(
            "INSERT INTO messages (lead_id, channel, subject, body, sent, sent_at) VALUES (?, 'sms', NULL, 'SMS Content', 1, ?)",
            (test_lead_id, t_sms_sent)
        )
        # 3. SMS reply
        self.store.record_reply(
            lead_id=test_lead_id,
            channel="sms",
            classification=ReplyClassification.PRICE_REQUEST,
            reply_text="What are your rates per hour?",
            received_at=t_sms_reply
        )
        # 4. Email reply
        self.store.record_reply(
            lead_id=test_lead_id,
            channel="email",
            classification=ReplyClassification.MEETING_REQUEST,
            reply_text="Let's book a Zoom meeting tomorrow at 3pm.",
            received_at=t_email_reply
        )
        self.store.conn.commit()

        timeline = self.store.get_conversation_timeline(test_lead_id)
        self.assertEqual(len(timeline), 4)

        # Confirm exact chronological order across different channels
        self.assertEqual(timeline[0]["channel"], "email")
        self.assertEqual(timeline[0]["type"], "sent")
        self.assertEqual(timeline[0]["timestamp"], t_email_sent)

        self.assertEqual(timeline[1]["channel"], "sms")
        self.assertEqual(timeline[1]["type"], "sent")
        self.assertEqual(timeline[1]["timestamp"], t_sms_sent)

        self.assertEqual(timeline[2]["channel"], "sms")
        self.assertEqual(timeline[2]["type"], "received")
        self.assertEqual(timeline[2]["classification"], "PRICE_REQUEST")
        self.assertEqual(timeline[2]["timestamp"], t_sms_reply)

        self.assertEqual(timeline[3]["channel"], "email")
        self.assertEqual(timeline[3]["type"], "received")
        self.assertEqual(timeline[3]["classification"], "MEETING_REQUEST")
        self.assertEqual(timeline[3]["timestamp"], t_email_reply)

        # Clean up
        self.store.conn.execute("DELETE FROM messages WHERE lead_id = ?", (test_lead_id,))
        self.store.conn.execute("DELETE FROM replies WHERE lead_id = ?", (test_lead_id,))
        self.store.conn.execute("DELETE FROM follow_up_state WHERE lead_id = ?", (test_lead_id,))
        self.store.conn.commit()
        print("=> [PASS] Test 3: Multi-channel events (Email + SMS) interleaved in true chronological order.")

    def test_04_no_regression_lead_details(self):
        """4. Confirm lead details API returns drafts, crm fields, and conversation timeline without regression."""
        res = requests.get(f"{BASE_URL}/api/lead-details?lead_id=L001", timeout=5)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("lead", data)
        self.assertIn("drafts", data)
        self.assertIn("history", data)
        self.assertIn("conversation_timeline", data)
        self.assertIsInstance(data["conversation_timeline"], list)
        
        # Verify drafts exist for email, sms, whatsapp
        channels = [d["channel"] for d in data["drafts"]]
        self.assertIn("email", channels)
        self.assertIn("sms", channels)
        self.assertIn("whatsapp", channels)
        print("=> [PASS] Test 4: Lead details endpoint maintains all existing drafts, CRM fields & adds timeline.")

    def test_05_legacy_reply_without_text_does_not_crash(self):
        """5. Confirm legacy reply records without stored text render fallback gracefully."""
        legacy_lead_id = "TIMELINE-TEST-LEGACY"
        legacy_time = (datetime.now() - timedelta(days=20)).isoformat()

        # Insert legacy follow_up_state with NULL reply_body/reply_text
        self.store.conn.execute(
            "INSERT OR REPLACE INTO follow_up_state (lead_id, channel, reply_received_at, reply_classification, reply_body, reply_text) "
            "VALUES (?, 'email', ?, 'NOT_INTERESTED', NULL, NULL)",
            (legacy_lead_id, legacy_time)
        )
        self.store.conn.commit()

        timeline = self.store.get_conversation_timeline(legacy_lead_id)
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["type"], "received")
        self.assertEqual(timeline[0]["classification"], "NOT_INTERESTED")
        self.assertEqual(timeline[0]["content"], "[reply text not available for this older record]")

        # Clean up
        self.store.conn.execute("DELETE FROM follow_up_state WHERE lead_id = ?", (legacy_lead_id,))
        self.store.conn.commit()
        print("=> [PASS] Test 5: Legacy reply records gracefully fallback to informative text without errors.")

if __name__ == "__main__":
    unittest.main()
