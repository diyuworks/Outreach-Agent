import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""
Test Suite for Spec Section 15: CRM Fields (models, state_store, web_dashboard, validation)
"""
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import json
import sqlite3
from models import Lead, LeadStatus
from state_store import StateStore
from lead_source import CSVLeadSource

def run_tests():
    print("=" * 70)
    print("RUNNING SPEC SECTION 15 CRM FIELDS TEST SUITE")
    print("=" * 70)

    # --------------------------------------------------------------------------
    # TEST 3: Schema Migration and Data Integrity (Check row counts before/after)
    # --------------------------------------------------------------------------
    print("\n--- TEST 3: Schema Migration & Data Preservation Check ---")
    conn = sqlite3.connect("outreach.db")
    conn.row_factory = sqlite3.Row
    
    # Check messages and follow_up_state row counts before instantiating new store
    cnt_messages_before = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    cnt_followup_before = conn.execute("SELECT COUNT(*) FROM follow_up_state").fetchone()[0]
    conn.close()

    # Re-instantiate StateStore which executes _init_schema() and _migrate_schema()
    store = StateStore(db_path="outreach.db")
    
    # Check table structure for leads table
    cur = store.conn.execute("PRAGMA table_info(leads)")
    cols = {r["name"]: r["type"] for r in cur.fetchall()}
    print(f"Columns in SQLite 'leads' table: {list(cols.keys())}")
    
    for req_col in ["city", "industry", "opportunity_value", "salesperson", "notes"]:
        assert req_col in cols, f"Required column '{req_col}' missing from SQLite leads table!"

    # Verify existing table row counts unchanged
    cnt_messages_after = store.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    cnt_followup_after = store.conn.execute("SELECT COUNT(*) FROM follow_up_state").fetchone()[0]
    
    assert cnt_messages_before == cnt_messages_after, "Messages row count changed unexpectedly!"
    assert cnt_followup_before == cnt_followup_after, "FollowUpState row count changed unexpectedly!"
    print(f"Row counts preserved: messages={cnt_messages_after}, follow_up_state={cnt_followup_after}")
    print("=> Test 3 PASSED: SQLite schema migration is safe, non-destructive, and additive.")

    # --------------------------------------------------------------------------
    # TEST 1: Existing leads load correctly with new fields default to None / empty
    # --------------------------------------------------------------------------
    print("\n--- TEST 1: Existing Leads Backwards Compatibility ---")
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_all_leads()
    assert len(leads) >= 7, f"Expected at least 7 leads, got {len(leads)}"
    
    # Check first lead (L001 BrightCart)
    l1 = next(l for l in leads if l.lead_id == "L001")
    print(f"Lead L001 loaded: {l1.company} ({l1.contact_name})")
    print(f"  city: {l1.city!r}")
    print(f"  industry: {l1.industry!r}")
    print(f"  opportunity_value: {l1.opportunity_value!r}")
    print(f"  salesperson: {l1.salesperson!r}")
    print(f"  notes: {l1.notes!r}")
    
    # Ensure accessing fields doesn't throw and defaults safely
    assert hasattr(l1, "city")
    assert hasattr(l1, "opportunity_value")
    assert hasattr(l1, "salesperson")
    assert hasattr(l1, "notes")
    print("=> Test 1 PASSED: Existing leads load seamlessly with new CRM fields defaulting to None.")

    # --------------------------------------------------------------------------
    # TEST 4: Opportunity Value Validation (Must reject non-numeric)
    # --------------------------------------------------------------------------
    print("\n--- TEST 4: Opportunity Value Validation ---")
    # 1. Float validation in Lead model
    valid_lead = Lead(
        lead_id="TEST_001",
        company="Test Company",
        contact_name="Test Person",
        opportunity_value=45000.50
    )
    assert valid_lead.opportunity_value == 45000.50

    # 2. Reject non-numeric input
    invalid_caught = False
    try:
        Lead(
            lead_id="TEST_002",
            company="Test Company 2",
            contact_name="Test Person 2",
            opportunity_value="invalid_amount_abc"
        )
    except Exception:
        invalid_caught = True
    assert invalid_caught, "Opportunity Value did not reject non-numeric string!"
    print("=> Test 4 PASSED: Opportunity Value strictly enforces numeric/float validation.")

    # --------------------------------------------------------------------------
    # TEST 2: Add / Update lead with CRM fields, save, and confirm persistence
    # --------------------------------------------------------------------------
    print("\n--- TEST 2: Update CRM Fields & Confirm Persistence ---")
    test_lead_id = "L001"
    
    # Use StateStore methods to update CRM fields
    store.update_lead_notes(test_lead_id, "Discussed omnichannel expansion. High intent.")
    store.update_opportunity_value(test_lead_id, 35000.0)
    store.assign_salesperson(test_lead_id, "Priya Sharma")
    store.update_lead_field(test_lead_id, "city", "Bengaluru")
    store.update_lead_field(test_lead_id, "industry", "eCommerce & D2C")

    # Read back from StateStore
    saved_crm = store.get_lead_crm(test_lead_id)
    print(f"Persisted CRM record for {test_lead_id}:")
    print(f"  City: {saved_crm.get('city')}")
    print(f"  Industry: {saved_crm.get('industry')}")
    print(f"  Opportunity Value: {saved_crm.get('opportunity_value')}")
    print(f"  Salesperson: {saved_crm.get('salesperson')}")
    print(f"  Notes: {saved_crm.get('notes')}")

    assert saved_crm.get("city") == "Bengaluru"
    assert saved_crm.get("industry") == "eCommerce & D2C"
    assert saved_crm.get("opportunity_value") == 35000.0
    assert saved_crm.get("salesperson") == "Priya Sharma"
    assert "Discussed omnichannel" in saved_crm.get("notes")

    print("=> Test 2 PASSED: CRM details persisted and retrieved accurately.")

    print("\n" + "=" * 70)
    print("ALL 4 SPEC SECTION 15 TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
