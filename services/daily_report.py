"""
Generates the Section-17-style daily operating report from outreach.db.
Auto-computed metrics only for objective counts; subjective/analytical
fields are left for human input, with supporting raw data shown instead
of an auto-generated conclusion.
"""
import os
import sys
import time
import argparse
from datetime import datetime, date
from collections import Counter
from typing import Dict, Any, Optional


from core.state_store import StateStore
from core.lead_source import CSVLeadSource
from core.models import LeadStatus


def generate_daily_report(
    target_date: Optional[str] = None,
    db_path: str = "outreach.db",
    csv_path: str = "data/leads.csv"
) -> Dict[str, Any]:
    """
    Computes all Section 17 metrics for target_date (default: today 'YYYY-MM-DD').
    Returns a dict with 'text', 'filepath', and raw structured data.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    report_date = target_date or today_str
    is_today = (report_date == today_str)

    store = StateStore(db_path=db_path)

    # 1. New companies discovered & researched
    # Checks discovery_log, leads created_at in SQLite, or fallback
    discovered_count = store.get_daily_discovery_count(report_date)
    if discovered_count == 0:
        cur = store.conn.execute(
            "SELECT count(*) as c FROM leads WHERE created_at LIKE ?",
            (f"{report_date}%",)
        )
        discovered_count = cur.fetchone()["c"]

    # 2. Lead data aggregation
    source = CSVLeadSource(csv_path=csv_path) if os.path.exists(csv_path) else None
    csv_leads = source.get_all_leads() if source else []

    # Merge with SQLite CRM data
    all_leads = []
    seen_ids = set()

    for lead in csv_leads:
        seen_ids.add(lead.lead_id)
        crm = store.get_lead_crm(lead.lead_id) or {}
        # Apply CRM overrides if present
        if crm.get("city"):
            lead.city = crm["city"]
        if crm.get("industry"):
            lead.industry = crm["industry"]
        if crm.get("opportunity_value") is not None:
            lead.opportunity_value = crm["opportunity_value"]
        if crm.get("salesperson"):
            lead.salesperson = crm["salesperson"]
        if crm.get("notes"):
            lead.notes = crm["notes"]
        lead_dict = lead.model_dump()
        lead_dict["created_at"] = crm.get("created_at")
        lead_dict["updated_at"] = crm.get("updated_at")
        all_leads.append(lead_dict)

    # Also check any SQLite leads not in CSV
    cur_extra = store.conn.execute("SELECT * FROM leads")
    for row in cur_extra.fetchall():
        r = dict(row)
        if r["lead_id"] not in seen_ids:
            seen_ids.add(r["lead_id"])
            all_leads.append(r)

    # Filter leads relevant to this report date
    if is_today:
        active_leads = all_leads
    else:
        # Strict date filter for past dates (zero-activity checks)
        active_leads = [
            l for l in all_leads
            if (l.get("created_at") and l["created_at"].startswith(report_date))
            or (l.get("updated_at") and l["updated_at"].startswith(report_date))
        ]

    # Metrics computation
    qualified_leads = [l for l in active_leads if (l.get("lead_status") or "").upper() == "QUALIFIED"]
    qualified_count = len(qualified_leads)

    hot_leads_count = sum(
        1 for l in active_leads
        if l.get("lead_score") is not None and l["lead_score"] >= 90
    )
    high_leads_count = sum(
        1 for l in active_leads
        if l.get("lead_score") is not None and 75 <= l["lead_score"] <= 89
    )

    # 3. Outreach prepared / sent
    messages_sent = store.get_daily_messages_sent_count(report_date)
    messages_prepared = store.get_daily_messages_prepared_count(report_date)

    # 4. Replies & Classifications
    replies = store.get_daily_replies(report_date)
    replies_count = len(replies)

    positive_replies = [r for r in replies if r.get("classification") in ("INTERESTED", "HOT")]
    positive_replies_count = len(positive_replies)

    meetings = [r for r in replies if r.get("classification") == "MEETING_REQUEST"]
    meetings_count = len(meetings)

    # 5. Proposals, Opportunities, Estimated Pipeline Value
    # Check proposal status
    proposals_count = sum(
        1 for l in active_leads
        if (l.get("lead_status") or "").upper() == "PROPOSAL"
        or (l.get("notes") and "proposal" in l["notes"].lower())
    )

    # Opportunities (leads with opportunity_value assigned > 0)
    opportunities = [
        l for l in active_leads
        if l.get("opportunity_value") is not None and float(l["opportunity_value"]) > 0
    ]
    opportunities_count = len(opportunities)
    pipeline_val = sum(float(l["opportunity_value"]) for l in opportunities)

    # 6. Top 10 opportunities: (Company — Score — Service — Buying Signal)
    scored_leads = [l for l in active_leads if l.get("lead_score") is not None]
    scored_leads.sort(key=lambda x: x["lead_score"], reverse=True)

    top_10 = []
    top_10_note = ""
    if not scored_leads:
        top_10_note = f"(none recorded for {report_date})"
    else:
        top_10 = scored_leads[:10]
        if is_today and len(scored_leads) < 10:
            top_10_note = f"({len(top_10)} available)"

    # 7. Best-performing raw breakdowns (human evaluation, not significance tested)
    industries = [l.get("industry") for l in active_leads if l.get("industry")]
    countries = [l.get("country") for l in active_leads if l.get("country")]
    services = [l.get("primary_service") for l in active_leads if l.get("primary_service")]

    def get_source_name(l):
        lid = l.get("lead_id", "")
        if lid.startswith("HETVI"):
            return "Hetvi Discovery API"
        return "CSV Import"

    sources = [get_source_name(l) for l in active_leads]

    def format_breakdown(items):
        if not items:
            return "(no data for this date)"
        counts = Counter(items).most_common()
        parts = [f"{name}: {cnt}" for name, cnt in counts]
        return f"{', '.join(parts)} (raw counts, not a significance-tested conclusion - evaluate manually)"

    perf_industry = format_breakdown(industries)
    perf_country = format_breakdown(countries)
    perf_service = format_breakdown(services)
    perf_source = format_breakdown(sources)

    # 8. Major objections (verbatim quotes)
    objections = store.get_daily_objections(report_date)
    objection_lines = []
    if objections:
        for obj in objections:
            body = (obj.get("body") or "").strip()
            comp = obj.get("company")
            if not comp:
                lead_match = next((l for l in all_leads if l.get("lead_id") == obj.get("lead_id")), None)
                if lead_match:
                    comp = lead_match.get("company")
            comp = comp or obj.get("lead_id") or "Unknown"
            ch = obj.get("channel") or "email"
            objection_lines.append(f'  - "{body}" (Company: {comp}, Channel: {ch})')
    else:
        objection_lines.append("  (none recorded today)" if is_today else f"  (none recorded for {report_date})")

    # Format the report string matching Section 17 field structure exactly
    top_10_formatted = []
    if not top_10:
        top_10_formatted.append(f"  {top_10_note}")
    else:
        for idx, lead in enumerate(top_10, 1):
            comp = lead.get("company") or "(Unknown Company)"
            score = lead.get("lead_score", "N/A")
            serv = lead.get("primary_service") or "General Software Development"
            hook = (lead.get("personalization_hook") or "Direct outreach").replace("\n", " ")
            if len(hook) > 80:
                hook = hook[:77] + "..."
            top_10_formatted.append(f"  {idx}. {comp} - {score} - {serv} - {hook}")

    meetings_display = (
        f"{meetings_count} (inferred from MEETING_REQUEST replies; no distinct meeting-confirmed tracking exists)"
        if meetings_count > 0 else "0"
    )

    researched_display = (
        f"{discovered_count} (equal to discovered; no separate research-tracking step exists in system)"
    )

    outreach_display = (
        f"{messages_sent} sent" if messages_prepared == 0
        else f"{messages_sent} sent ({messages_prepared} prepared)"
    )

    pipeline_display = f"${pipeline_val:,.2f}" if pipeline_val > 0 else "0.00"

    report_lines = [
        f"=================================================================",
        f"DAILY OPERATING REPORT - {report_date}",
        f"=================================================================",
        f"New companies discovered: {discovered_count}",
        f"Companies researched: {researched_display}",
        f"Qualified leads: {qualified_count}",
        f"HOT leads: {hot_leads_count}",
        f"HIGH leads: {high_leads_count}",
        f"Outreach prepared/sent: {outreach_display}",
        f"Replies: {replies_count}",
        f"Positive replies: {positive_replies_count}",
        f"Meetings: {meetings_display}",
        f"Proposals: {proposals_count}",
        f"Opportunities: {opportunities_count}",
        f"Estimated pipeline value: {pipeline_display}",
        f"Top 10 opportunities: (Company - Score - Service - Buying Signal)",
        *top_10_formatted,
        f"Best-performing industry: {perf_industry}",
        f"Best-performing country: {perf_country}",
        f"Best-performing service: {perf_service}",
        f"Best-performing lead source: {perf_source}",
        f"Major objections:",
        *objection_lines,
        f"Recommended strategy changes:",
        f"  [                                                                    ]",
        f"  (fill in manually - no automated recommendation generated)",
        f"=================================================================",
    ]

    report_text = "\n".join(report_lines)

    # Save to timestamped report file under reports/
    os.makedirs("reports", exist_ok=True)
    report_filepath = os.path.join("reports", f"daily_report_{report_date}.md")
    with open(report_filepath, "w", encoding="utf-8") as f:
        f.write(report_text + "\n")

    # Retention policy: Delete reports older than 30 days, keeping at least the latest report
    cleanup_old_reports(reports_dir="reports", retention_days=30)

    return {

        "report_date": report_date,
        "filepath": report_filepath,
        "text": report_text,
        "metrics": {
            "discovered_count": discovered_count,
            "qualified_count": qualified_count,
            "hot_leads_count": hot_leads_count,
            "high_leads_count": high_leads_count,
            "messages_sent": messages_sent,
            "messages_prepared": messages_prepared,
            "replies_count": replies_count,
            "positive_replies_count": positive_replies_count,
            "meetings_count": meetings_count,
            "proposals_count": proposals_count,
            "opportunities_count": opportunities_count,
            "pipeline_value": pipeline_val,
            "top_10": top_10,
            "objections": objections,
        }
    }


def cleanup_old_reports(reports_dir: str = "reports", retention_days: int = 30):
    """
    Retention policy: Delete any report file older than retention_days (30 days) from reports/.
    Preserves at least the most recent report regardless of age so reports directory is never left empty.
    """
    if not os.path.exists(reports_dir):
        return

    now = time.time()
    cutoff_seconds = retention_days * 86400

    report_files = []
    for fname in os.listdir(reports_dir):
        if fname.startswith("daily_report_") and fname.endswith(".md"):
            fpath = os.path.join(reports_dir, fname)
            if os.path.isfile(fpath):
                report_files.append((fpath, os.path.getmtime(fpath)))

    # Sort files by modification time (newest first)
    report_files.sort(key=lambda x: x[1], reverse=True)

    # Keep at least the most recent report
    if len(report_files) <= 1:
        return

    # Delete files older than cutoff except the newest one
    for fpath, mtime in report_files[1:]:
        if (now - mtime) > cutoff_seconds:
            try:
                os.remove(fpath)
                print(f"[DailyReport] Cleaned up expired report (>30 days): {fpath}")
            except Exception as e:
                print(f"[DailyReport] Warning: Could not remove {fpath}: {e}")


def generate_report_text(report_date: Optional[str] = None, db_path: str = "outreach.db", csv_path: str = "data/leads.csv") -> str:

    """
    Returns the exact Section-17 plain-text report string.
    Reused by both the CLI script and the web API endpoint.
    """
    result = generate_daily_report(target_date=report_date, db_path=db_path, csv_path=csv_path)
    return result["text"]


def main():
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Generate Section 17 Daily Operating Report")
    parser.add_argument(
        "--date",
        dest="report_date",
        default=None,
        help="Date to generate report for (format: YYYY-MM-DD). Defaults to today."
    )
    args = parser.parse_args()

    result = generate_daily_report(target_date=args.report_date)
    print(result["text"])
    print(f"\n[Report saved to: {result['filepath']}]")


if __name__ == "__main__":
    main()
