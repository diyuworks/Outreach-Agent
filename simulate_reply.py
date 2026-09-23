"""
Simulate Inbound Lead Reply & Trigger Escalation Alert.

Simulates an inbound reply from a lead, classifies intent, and dispatches
a real-time Hot Lead Escalation Alert to the salesperson if interested.

Run:  python simulate_reply.py
"""
import sys
import os
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from lead_source import CSVLeadSource
from state_store import StateStore
from escalation import process_reply


def run_simulate_reply():
    store = StateStore(db_path="outreach.db")
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_actionable_leads()

    if not leads:
        print("No leads found in data/leads.csv.")
        return

    lead = leads[0]  # Aisha Verma (BrightCart Retail)

    print("\n=======================================================")
    print("SIMULATE INBOUND REPLY & HOT LEAD ESCALATION")
    print("=======================================================\n")
    print(f"Target Lead: {lead.company} | Contact: {lead.contact_name} ({lead.designation})")
    print(f"Service: {lead.primary_service} | Lead Score: {lead.lead_score}/100\n")

    print("Choose or type an inbound reply from the lead:")
    print("  1. 'Can we schedule a call to discuss pricing?' (Meeting Request -> Hot Alert 🚨)")
    print("  2. 'What are your standard pricing packages?' (Pricing Request -> Hot Alert 🚨)")
    print("  3. 'Not interested, please stop contacting us' (Opt-Out -> Suppression 🛡️)")
    print("  4. Custom reply (Type your own)")
    print("  5. Multi-Trigger: Budget ($25k) + Technical Question (API/Security) 🚨")
    
    choice = input("\nEnter choice (1/2/3/4/5) [Default: 1]: ").strip()
    
    if choice == "2":
        reply_text = "What are your standard pricing packages for dedicated developers?"
    elif choice == "3":
        reply_text = "Not interested, please remove us from your list."
    elif choice == "4":
        reply_text = input("Type custom reply: ").strip()
        if not reply_text:
            reply_text = "Can we schedule a quick call this Thursday?"
    elif choice == "5":
        reply_text = "We have an allocated budget of $25,000 for this project. What is your approach to API rate limiting and security architecture?"
    else:
        reply_text = "Can we schedule a call to discuss pricing and onboarding?"

    print(f"\nSimulated Reply: \"{reply_text}\"")
    print("Processing classification & escalation pipeline...")

    # Process and dispatch real alert
    cls = process_reply(lead, reply_text, store, channel="email")

    print("\n=======================================================")
    print("PIPELINE EXECUTION COMPLETE.")
    print("Check dashboard (http://localhost:5050) or your inbox to verify!")
    print("=======================================================\n")


if __name__ == "__main__":
    run_simulate_reply()
