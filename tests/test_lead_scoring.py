"""
Tests for Dynamic Lead Scoring Intelligence Engine.
"""
import os
import unittest
from models import Lead
from state_store import StateStore
from lead_scoring import compute_dynamic_score, get_score_breakdown, recalculate_all_leads


class TestDynamicLeadScoring(unittest.TestCase):
    def setUp(self):
        self.test_db = f"test_lead_scoring_{self._testMethodName}.db"
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except OSError:
                pass
        self.store = StateStore(db_path=self.test_db)

    def tearDown(self):
        try:
            self.store.conn.close()
        except Exception:
            pass
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except OSError:
                pass

    def test_base_score_default(self):
        lead = Lead(
            lead_id="LEAD-001",
            company="Acme Corp",
            contact_name="John Doe",
            email="john@example.com",
            phone="+1234567890",
            lead_score=70
        )
        score = compute_dynamic_score(lead, self.store)
        self.assertEqual(score, 70)

        breakdown = get_score_breakdown(lead, self.store)
        self.assertEqual(breakdown["base_score"], 70)
        self.assertEqual(breakdown["modifier"], 0)
        self.assertEqual(breakdown["final_score"], 70)

    def test_reply_sentiment_boost(self):
        lead = Lead(
            lead_id="LEAD-002",
            company="Globex",
            contact_name="Alice Smith",
            email="alice@example.com",
            phone="+1234567891",
            lead_score=60
        )
        # Record an INTERESTED reply
        self.store.record_reply(
            lead_id="LEAD-002",
            channel="email",
            classification="INTERESTED",
            reply_text="Yes, let's schedule a call tomorrow!"
        )

        score = compute_dynamic_score(lead, self.store)
        self.assertGreater(score, 60)

        breakdown = get_score_breakdown(lead, self.store)
        self.assertGreater(breakdown["modifier"], 0)
        self.assertEqual(breakdown["final_score"], score)
        self.assertTrue(any("Reply" in s["label"] for s in breakdown["signals"]))

    def test_opt_out_penalty(self):
        lead = Lead(
            lead_id="LEAD-003",
            company="Initech",
            contact_name="Bob Brown",
            email="bob@example.com",
            phone="+1234567892",
            lead_score=80
        )
        # Record an OPT_OUT reply and opt-out suppression
        self.store.record_reply(
            lead_id="LEAD-003",
            channel="email",
            classification="OPT_OUT",
            reply_text="Please unsubscribe me immediately."
        )
        self.store.record_opt_out("LEAD-003")

        score = compute_dynamic_score(lead, self.store)
        self.assertLess(score, 80)

        breakdown = get_score_breakdown(lead, self.store)
        self.assertLess(breakdown["modifier"], 0)
        self.assertTrue(any(s["direction"] == "penalty" for s in breakdown["signals"]))

    def test_score_clamping(self):
        # Score shouldn't exceed 100 or drop below 0
        lead_high = Lead(
            lead_id="LEAD-HIGH",
            company="High Tech",
            contact_name="High Guy",
            email="high@example.com",
            phone="+1234567893",
            lead_score=98
        )
        self.store.record_reply(
            lead_id="LEAD-HIGH",
            channel="email",
            classification="HOT",
            reply_text="Send proposal"
        )
        score = compute_dynamic_score(lead_high, self.store)
        self.assertLessEqual(score, 100)

        lead_low = Lead(
            lead_id="LEAD-LOW",
            company="Low Tech",
            contact_name="Low Guy",
            email="low@example.com",
            phone="+1234567894",
            lead_score=10
        )
        self.store.record_reply(
            lead_id="LEAD-LOW",
            channel="email",
            classification="OPT_OUT",
            reply_text="Stop calling me"
        )
        self.store.record_opt_out("LEAD-LOW")
        score_low = compute_dynamic_score(lead_low, self.store)
        self.assertGreaterEqual(score_low, 0)

    def test_recalculate_all_leads(self):
        leads = [
            Lead(lead_id="L1", company="C1", contact_name="L1", email="l1@a.com", phone="+1", lead_score=50),
            Lead(lead_id="L2", company="C2", contact_name="L2", email="l2@a.com", phone="+2", lead_score=75),
        ]
        results = recalculate_all_leads(leads, self.store)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["lead_id"], "L1")
        self.assertEqual(results[0]["base_score"], 50)
        self.assertEqual(results[1]["lead_id"], "L2")
        self.assertEqual(results[1]["base_score"], 75)


if __name__ == "__main__":
    unittest.main()
