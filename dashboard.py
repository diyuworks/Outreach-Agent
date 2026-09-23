"""
CRM Dashboard — read-only view of outreach state.

Queries outreach.db (must already exist from a prior demo.py run) and prints
a per-lead, per-channel status table to the terminal.

Run:  python dashboard.py
"""
from lead_source import CSVLeadSource
from state_store import StateStore


# Column widths
W_COMPANY = 22
W_CONTACT = 18
W_CHANNEL = 10
W_STATUS = 16
W_DATE = 12
W_REPLY = 20


def print_dashboard():
    store = StateStore(db_path="outreach.db")
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_actionable_leads()

    if not leads:
        print("No actionable leads found in data/leads.csv.")
        return

    rows = store.get_dashboard_rows(leads)

    # Header
    header = (
        "Company".ljust(W_COMPANY)
        + "Contact".ljust(W_CONTACT)
        + "Channel".ljust(W_CHANNEL)
        + "Status".ljust(W_STATUS)
        + "Last Sent".ljust(W_DATE)
        + "Next F/U".ljust(W_DATE)
        + "Reply".ljust(W_REPLY)
    )
    total_width = W_COMPANY + W_CONTACT + W_CHANNEL + W_STATUS + W_DATE + W_DATE + W_REPLY

    print()
    print("=" * total_width)
    print("OUTREACH DASHBOARD".center(total_width))
    print("=" * total_width)
    print(header)
    print("-" * total_width)

    # Rows
    for r in rows:
        line = (
            r["company"][:W_COMPANY - 2].ljust(W_COMPANY)
            + r["contact_name"][:W_CONTACT - 2].ljust(W_CONTACT)
            + r["channel"].ljust(W_CHANNEL)
            + r["status"].ljust(W_STATUS)
            + str(r["last_sent"]).ljust(W_DATE)
            + str(r["next_follow_up"]).ljust(W_DATE)
            + str(r["reply_classification"]).ljust(W_REPLY)
        )
        print(line)

    print("-" * total_width)

    # Summary stats
    statuses = [r["status"] for r in rows]
    contacted = sum(1 for s in statuses if s != "NOT_CONTACTED")
    awaiting = sum(1 for s in statuses if s == "AWAITING_REPLY")
    due = sum(1 for s in statuses if s == "FOLLOW_UP_DUE")
    replied = sum(1 for s in statuses if s == "REPLIED")
    opted_out = sum(1 for s in statuses if s == "OPTED_OUT")

    print(
        f"\nSummary: {len(rows)} slots | "
        f"{contacted} contacted | "
        f"{awaiting} awaiting reply | "
        f"{due} follow-ups due | "
        f"{replied} replied | "
        f"{opted_out} opted out"
    )
    print()


if __name__ == "__main__":
    print_dashboard()
