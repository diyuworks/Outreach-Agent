"""
LeadSource abstraction. Today it reads from a CSV file.
Tomorrow, if the Lead Gen team hands off via SQLite / Google Sheet / API,
only THIS file needs to change — nothing downstream (messaging, follow-up,
state store) needs to know or care where leads come from.
"""
import csv
from abc import ABC, abstractmethod
from typing import List
from core.models import Lead, LeadStatus


class LeadSource(ABC):
    @abstractmethod
    def get_actionable_leads(self) -> List[Lead]:
        """Return leads that are ready for outreach or follow-up."""
        raise NotImplementedError

    @abstractmethod
    def get_all_leads(self) -> List[Lead]:
        """Return all leads in the source, including unreviewed NEW leads."""
        raise NotImplementedError


class CSVLeadSource(LeadSource):
    def __init__(self, csv_path: str):
        self.csv_path = csv_path

    def _parse_row_to_lead(self, row: dict) -> Lead:
        if not row.get("lead_id") or not row.get("company"):
            return None

        # Safely parse lead_score
        score_val = None
        raw_score = str(row.get("lead_score", "")).strip() if row.get("lead_score") is not None else ""
        if raw_score.isdigit():
            score_val = int(raw_score)

        # Parse lead_status
        raw_status = (row.get("lead_status") or "NEW").strip()
        try:
            status = LeadStatus(raw_status)
        except ValueError:
            status = LeadStatus.NEW

        # Safely parse opportunity_value
        opp_val = None
        raw_opp = str(row.get("opportunity_value", "")).strip() if row.get("opportunity_value") is not None else ""
        if raw_opp:
            try:
                opp_val = float(raw_opp)
            except ValueError:
                opp_val = None

        return Lead(
            lead_id=row["lead_id"],
            company=row["company"],
            website=row.get("website") or None,
            contact_name=row.get("contact_name", "") or "(Unknown)",
            designation=row.get("designation") or None,
            email=row.get("email") or None,
            phone=row.get("phone") or None,
            country=row.get("country") or None,
            city=row.get("city") or None,
            industry=row.get("industry") or None,
            lead_score=score_val,
            lead_status=status,
            primary_service=row.get("primary_service") or "",
            personalization_hook=row.get("personalization_hook") or "",
            opportunity_value=opp_val,
            salesperson=row.get("salesperson") or None,
            notes=row.get("notes") or None,
        )

    def get_actionable_leads(self) -> List[Lead]:
        leads = []
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lead = self._parse_row_to_lead(row)
                    if lead and lead.lead_status in (LeadStatus.QUALIFIED, LeadStatus.FOLLOW_UP):
                        leads.append(lead)
                except Exception as e:
                    print(f"[LeadSource] Skipping row {row.get('lead_id')}: {e}")
                    continue
        return leads

    def get_all_leads(self) -> List[Lead]:
        leads = []
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lead = self._parse_row_to_lead(row)
                    if lead:
                        leads.append(lead)
                except Exception as e:
                    print(f"[LeadSource] Skipping row {row.get('lead_id')}: {e}")
                    continue
        return leads
