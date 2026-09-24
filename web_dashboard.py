"""
Web Dashboard Server for Outreach & Follow-Up Agent.
Provides a modern, interactive web interface and JSON API endpoints.

Run:  python web_dashboard.py
URL:  http://localhost:5000
"""
import os
import re
import json
import csv as csv_module
import sqlite3
import mimetypes
from datetime import datetime, date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv
load_dotenv()

from lead_source import CSVLeadSource
from state_store import StateStore
from follow_up_engine import next_action, FollowUpAction
from message_generator import generate_all_channels
from escalation import process_reply
from response_classifier import classify_reply, needs_human_escalation, detect_additional_escalation_signals
from phone_utils import normalize_to_e164

PORT = int(os.environ.get("PORT", 5050))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

HETVI_LEADS_CACHE = {}

def get_lead_or_hetvi(lead_id: str):
    source = CSVLeadSource(csv_path="data/leads.csv")
    leads = source.get_all_leads()
    lead = next((l for l in leads if l.lead_id == lead_id), None)
    if lead:
        return lead

    h_lead = HETVI_LEADS_CACHE.get(lead_id)
    if not h_lead:
        try:
            from providers.hetvi_lead_source import fetch_hetvi_leads
            for hl in fetch_hetvi_leads():
                HETVI_LEADS_CACHE[hl["lead_id"]] = hl
            h_lead = HETVI_LEADS_CACHE.get(lead_id)
        except Exception as e:
            print(f"[LeadLookup] Hetvi fetch error: {e}")

    if h_lead:
        from models import Lead, LeadStatus
        return Lead(
            lead_id=h_lead.get("lead_id"),
            company=h_lead.get("company", ""),
            website=h_lead.get("website") or "",
            contact_name=h_lead.get("contact_name") or "Decision Maker",
            designation=h_lead.get("designation"),
            email=h_lead.get("email"),
            phone=h_lead.get("phone"),
            country=h_lead.get("country"),
            lead_status=LeadStatus.QUALIFIED,
            primary_service=h_lead.get("primary_service", "") or "",
            personalization_hook=h_lead.get("personalization_hook", "") or ""
        )
    return None


class DashboardHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, filepath, content_type=None):
        if not os.path.exists(filepath):
            self.send_error(404, "File Not Found")
            return
        if not content_type:
            content_type, _ = mimetypes.guess_type(filepath)
            content_type = content_type or "application/octet-stream"

        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # API Endpoints
        if path == "/api/dashboard":
            self.handle_get_dashboard()
        elif path == "/api/simulate":
            days = int(query.get("days", [0])[0])
            self.handle_get_simulate(days)
        elif path == "/api/lead-details":
            lead_id = query.get("lead_id", [""])[0]
            self.handle_get_lead_details(lead_id)
        elif path == "/api/lead-timeline":
            lead_id = query.get("lead_id", [""])[0]
            self.handle_get_lead_timeline(lead_id)
        elif path == "/api/fetch-hetvi-leads":
            self.handle_get_fetch_hetvi_leads()
        elif path == "/api/daily-report":
            report_date = query.get("date", [None])[0]
            from daily_report import generate_report_text
            text = generate_report_text(report_date=report_date)
            self._send_json({"report": text})
        # Static Files
        elif path == "/" or path == "/index.html":
            self._send_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
        else:
            rel_path = path.lstrip("/")
            file_path = os.path.join(STATIC_DIR, rel_path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                self._send_file(file_path)
            else:
                self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/check-replies":
            self.handle_post_check_replies()
        elif path == "/api/send-message":
            self.handle_post_send_message()
        elif path == "/api/reset-db":
            self.handle_post_reset_db()
        elif path == "/api/add-lead":
            self.handle_post_add_lead()
        elif path == "/api/update-lead":
            self.handle_post_update_lead()
        elif path == "/api/simulate-reply":
            self.handle_post_simulate_reply()
        elif path == "/api/voice-command":
            self.handle_post_voice_command()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_post_voice_command(self):
        import base64
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        content_type = self.headers.get("Content-Type", "")

        audio_bytes = None
        text_command = None

        if "application/json" in content_type:
            try:
                payload = json.loads(post_data.decode("utf-8"))
            except Exception:
                payload = {}
            if "audio_base64" in payload:
                try:
                    audio_bytes = base64.b64decode(payload["audio_base64"])
                except Exception:
                    pass
            elif "text" in payload:
                text_command = payload["text"]
        elif "audio/" in content_type:
            audio_bytes = post_data
        else:
            try:
                payload = json.loads(post_data.decode("utf-8"))
                text_command = payload.get("text")
                if payload.get("audio_base64"):
                    audio_bytes = base64.b64decode(payload["audio_base64"])
            except Exception:
                text_command = post_data.decode("utf-8", errors="ignore")

        from voice_commands import process_voice_command
        result = process_voice_command(audio_bytes=audio_bytes, text_command=text_command)

        # If action is add_note and company is identified, persist to CRM
        if result.get("action") == "add_note" and result.get("status") == "success":
            company = result.get("params", {}).get("company_name", "")
            note = result.get("params", {}).get("note_text", "")
            if company and note:
                try:
                    source = CSVLeadSource(csv_path="data/leads.csv")
                    leads = source.get_all_leads()
                    matched = next((l for l in leads if company.lower() in l.company.lower()), None)
                    if matched:
                        store = StateStore(db_path="outreach.db")
                        existing_crm = store.get_lead_crm(matched.lead_id) or {}
                        existing_notes = existing_crm.get("notes") or ""
                        new_notes = (existing_notes + "\n" + note).strip() if existing_notes else note
                        store.update_lead_crm(
                            lead_id=matched.lead_id,
                            city=existing_crm.get("city"),
                            industry=existing_crm.get("industry"),
                            opportunity_value=existing_crm.get("opportunity_value"),
                            salesperson=existing_crm.get("salesperson"),
                            notes=new_notes
                        )
                        result["matched_lead_id"] = matched.lead_id
                except Exception as e:
                    print(f"[VoiceAddNote] Note persistence note: {e}")

        status_code = 200
        if result.get("status") == "rejected":
            status_code = 403
        self._send_json(result, status_code)


    def handle_post_add_lead(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(post_data)
        except Exception:
            payload = {}

        company = payload.get("company", "").strip()
        contact_name = payload.get("contact_name", "").strip()
        if not company or not contact_name:
            self._send_json({"status": "error", "message": "Company and Contact Name are required"}, 400)
            return

        email = payload.get("email", "").strip()
        phone = payload.get("phone", "").strip()

        provided_lead_id = payload.get("lead_id", "").strip()
        is_imported = bool(provided_lead_id)

        # For manual addition, at least one of Email or Phone is required.
        # For imports from external discovery (e.g. Hetvi), email and phone may be absent.
        if not is_imported and not email and not phone:
            self._send_json({"status": "error", "message": "At least one of Email or Phone is required"}, 400)
            return

        if email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            self._send_json({"status": "error", "message": "Invalid email format, e.g. name@example.com"}, 400)
            return

        if phone:
            norm_phone = normalize_to_e164(phone)
            if not norm_phone or not re.match(r'^\+[1-9]\d{7,14}$', norm_phone):
                self._send_json({"status": "error", "message": "Phone must be in E.164 format or valid dialable number, e.g. +919876543210 or (302) 219-0702"}, 400)
                return
            phone = norm_phone

        import csv
        csv_path = "data/leads.csv"
        existing_leads = []
        if os.path.exists(csv_path):
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                existing_leads = list(reader)

        # Check explicit force flag (override duplicates)
        force = bool(payload.get("force", False))
        if isinstance(payload.get("force"), str):
            force = payload.get("force").strip().lower() in ("true", "1", "yes")

        # Duplicate Lead Detection (Spec Section 15 & 19)
        # Applies to manual additions when force is not True
        if not is_imported and not force:
            norm_new_company = company.strip().lower()
            norm_new_email = email.strip().lower() if email else ""
            norm_new_phone = phone if phone else ""

            for el in existing_leads:
                existing_company = (el.get("company") or "").strip()
                existing_email = (el.get("email") or "").strip()
                existing_phone = (el.get("phone") or "").strip()
                existing_id = el.get("lead_id", "Unknown")

                # 1. Company name match (exact trimmed, case-insensitive)
                if norm_new_company and existing_company.lower() == norm_new_company:
                    self._send_json({
                        "status": "error",
                        "error_type": "duplicate_lead",
                        "field": "company",
                        "duplicate_lead_id": existing_id,
                        "duplicate_company": existing_company,
                        "message": f"Possible duplicate: company '{existing_company}' already exists as lead {existing_id}"
                    }, 409)
                    return

                # 2. Email match (exact trimmed, case-insensitive)
                if norm_new_email and existing_email and existing_email.lower() == norm_new_email:
                    self._send_json({
                        "status": "error",
                        "error_type": "duplicate_lead",
                        "field": "email",
                        "duplicate_lead_id": existing_id,
                        "duplicate_company": existing_company,
                        "message": f"Possible duplicate: email '{email}' already belongs to lead {existing_id} ({existing_company})"
                    }, 409)
                    return

                # 3. Phone match (normalized E.164 comparison)
                if norm_new_phone and existing_phone:
                    norm_existing_phone = normalize_to_e164(existing_phone)
                    if norm_existing_phone and norm_existing_phone == norm_new_phone:
                        orig_phone = payload.get("phone", phone)
                        self._send_json({
                            "status": "error",
                            "error_type": "duplicate_lead",
                            "field": "phone",
                            "duplicate_lead_id": existing_id,
                            "duplicate_company": existing_company,
                            "message": f"Possible duplicate: phone '{orig_phone}' already belongs to lead {existing_id} ({existing_company})"
                        }, 409)
                        return

        # Use provided lead_id if given (e.g. HETVI-187 from Hetvi activation),
        # otherwise auto-generate sequential L-prefixed ID
        if provided_lead_id:
            if any(el.get("lead_id") == provided_lead_id for el in existing_leads):
                self._send_json({"status": "error", "message": f"Lead {provided_lead_id} already exists"}, 409)
                return
            new_lead_id = provided_lead_id
        else:
            next_idx = len(existing_leads) + 1
            new_lead_id = f"L{next_idx:03d}"

        # Determine lead_status per spec:
        # If BOTH Service and Score are filled in -> QUALIFIED
        # If EITHER is missing -> NEW
        req_service = (payload.get("primary_service") or "").strip()
        raw_score = payload.get("lead_score")
        score_str = str(raw_score).strip() if raw_score is not None else ""

        if "lead_status" in payload and payload["lead_status"]:
            final_status = payload["lead_status"].strip()
        else:
            if req_service and score_str:
                final_status = "QUALIFIED"
            else:
                final_status = "NEW"

        # Validate opportunity_value if provided
        opp_val = payload.get("opportunity_value")
        parsed_opp_val = None
        if opp_val is not None and str(opp_val).strip() != "":
            try:
                parsed_opp_val = float(opp_val)
                if parsed_opp_val < 0:
                    raise ValueError
            except (ValueError, TypeError):
                self._send_json({"status": "error", "message": "Opportunity Value must be a valid numeric amount"}, 400)
                return

        city = (payload.get("city") or "").strip()
        industry = (payload.get("industry") or "").strip()
        salesperson = (payload.get("salesperson") or "").strip()
        notes = (payload.get("notes") or "").strip()

        new_row = {
            "lead_id": new_lead_id,
            "company": company,
            "website": payload.get("website") or f"{company.lower().replace(' ', '')}.example",
            "contact_name": contact_name,
            "designation": payload.get("designation") or "Decision Maker",
            "email": email or "",
            "phone": phone or "",
            "country": payload.get("country") or "India",
            "lead_score": score_str,
            "lead_status": final_status,
            "primary_service": req_service,
            "personalization_hook": payload.get("personalization_hook") or "",
            "city": city,
            "industry": industry,
            "opportunity_value": str(parsed_opp_val) if parsed_opp_val is not None else "",
            "salesperson": salesperson,
            "notes": notes
        }

        fieldnames = [
            "lead_id", "company", "website", "contact_name", "designation",
            "email", "phone", "country", "lead_score", "lead_status",
            "primary_service", "personalization_hook",
            "city", "industry", "opportunity_value", "salesperson", "notes"
        ]

        with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(new_row)

        # Also insert or update into StateStore SQLite leads table
        store = StateStore(db_path="outreach.db")
        store.update_lead_crm(
            lead_id=new_lead_id,
            company=company,
            contact_name=contact_name,
            designation=payload.get("designation") or "Decision Maker",
            email=email,
            phone=phone,
            country=payload.get("country") or "India",
            lead_score=int(score_str) if score_str.isdigit() else None,
            lead_status=final_status,
            primary_service=req_service,
            personalization_hook=payload.get("personalization_hook") or "",
            city=city or None,
            industry=industry or None,
            opportunity_value=parsed_opp_val,
            salesperson=salesperson or None,
            notes=notes or None
        )
        store.record_discovery(lead_id=new_lead_id, company=company, source="manual")

        self._send_json({
            "status": "success",
            "message": f"Added lead {contact_name} ({company}) successfully!",
            "lead": new_row
        })

    def handle_post_update_lead(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(post_data)
        except Exception:
            payload = {}

        lead_id = payload.get("lead_id")
        if not lead_id:
            self._send_json({"status": "error", "message": "lead_id is required"}, 400)
            return

        store = StateStore(db_path="outreach.db")

        # Opportunity value validation (Test 4)
        opp_value = payload.get("opportunity_value")
        parsed_opp_value = None
        if opp_value is not None and str(opp_value).strip() != "":
            try:
                parsed_opp_value = float(opp_value)
                if parsed_opp_value < 0:
                    raise ValueError("Opportunity value must be non-negative")
            except (ValueError, TypeError):
                self._send_json({
                    "status": "error",
                    "message": "Opportunity Value must be a valid numeric amount (e.g. 25000 or 1500.50)"
                }, 400)
                return

        city = (payload.get("city") or "").strip() or None
        industry = (payload.get("industry") or "").strip() or None
        salesperson = (payload.get("salesperson") or "").strip() or None
        notes = (payload.get("notes") or "").strip() or None

        # Update in StateStore SQLite
        store.update_lead_crm(
            lead_id=lead_id,
            city=city,
            industry=industry,
            opportunity_value=parsed_opp_value,
            salesperson=salesperson,
            notes=notes
        )

        # Also persist to data/leads.csv if present
        csv_path = "data/leads.csv"
        if os.path.exists(csv_path):
            try:
                import csv as csv_mod
                rows = []
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    reader = csv_mod.DictReader(f)
                    fieldnames = list(reader.fieldnames or [])
                    for fn in ["city", "industry", "opportunity_value", "salesperson", "notes"]:
                        if fn not in fieldnames:
                            fieldnames.append(fn)
                    for row in reader:
                        if row.get("lead_id") == lead_id:
                            row["city"] = city or ""
                            row["industry"] = industry or ""
                            row["opportunity_value"] = str(parsed_opp_value) if parsed_opp_value is not None else ""
                            row["salesperson"] = salesperson or ""
                            row["notes"] = notes or ""
                        rows.append(row)
                with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv_mod.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
            except Exception as e:
                print(f"[UpdateLead] Warning: Could not update CSV: {e}")

        # Update HETVI cache if applicable
        if lead_id in HETVI_LEADS_CACHE:
            hl = HETVI_LEADS_CACHE[lead_id]
            hl["city"] = city
            hl["industry"] = industry
            hl["opportunity_value"] = parsed_opp_value
            hl["salesperson"] = salesperson
            hl["notes"] = notes

        self._send_json({
            "status": "success",
            "message": f"Updated CRM details for lead {lead_id}",
            "lead": {
                "lead_id": lead_id,
                "city": city,
                "industry": industry,
                "opportunity_value": parsed_opp_value,
                "salesperson": salesperson,
                "notes": notes
            }
        })

    def handle_post_simulate_reply(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(post_data)
        except Exception:
            payload = {}

        lead_id = payload.get("lead_id")
        channel = payload.get("channel", "email").lower()
        reply_text = payload.get("reply_text", "Can we schedule a call to discuss pricing?")

        store = StateStore(db_path="outreach.db")
        source = CSVLeadSource(csv_path="data/leads.csv")
        leads = source.get_actionable_leads()
        lead = next((l for l in leads if l.lead_id == lead_id), None)
        if not lead:
            self._send_json({"status": "error", "message": "Lead not found"}, 404)
            return

        cls = process_reply(lead, reply_text, store, channel=channel)

        self._send_json({
            "status": "success",
            "message": f"Processed inbound reply from {lead.contact_name}: Classified as '{cls.value}'",
            "classification": cls.value,
            "lead_id": lead.lead_id
        })

    def handle_post_reset_db(self):
        store = StateStore(db_path="outreach.db")

        # Clear all tables to clean initial state
        store.conn.execute("DELETE FROM opt_outs")
        store.conn.execute("DELETE FROM follow_up_state")
        store.conn.execute("DELETE FROM messages")
        store.conn.execute("DELETE FROM reply_check_log")
        store.conn.commit()

        self._send_json({
            "status": "success",
            "message": "Demo data reset to clean state! All leads ready for fresh outreach."
        })

    def handle_post_send_message(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length).decode("utf-8")
            try:
                payload = json.loads(post_data)
            except Exception:
                payload = {}

            lead_id = payload.get("lead_id")
            channel = payload.get("channel", "email").lower()
            sim_days = int(payload.get("sim_days", 0))
            custom_subject = payload.get("subject")
            custom_body = payload.get("body")

            store = StateStore(db_path="outreach.db")
            lead = get_lead_or_hetvi(lead_id)

            if not lead:
                self._send_json({"status": "error", "message": f"Lead {lead_id} not found in database"}, 404)
                return

            # If lead was sourced from Hetvi and not yet in leads.csv, auto-persist it
            csv_path = "data/leads.csv"
            source = CSVLeadSource(csv_path=csv_path)
            existing_leads = source.get_all_leads()
            if not any(l.lead_id == lead.lead_id for l in existing_leads):
                try:
                    row = {
                        "lead_id": lead.lead_id,
                        "company": lead.company,
                        "website": lead.website or "",
                        "contact_name": lead.contact_name,
                        "designation": lead.designation or "",
                        "email": lead.email or "",
                        "phone": lead.phone or "",
                        "country": lead.country or "",
                        "lead_score": "",
                        "lead_status": "QUALIFIED",
                        "primary_service": lead.primary_service or "",
                        "personalization_hook": lead.personalization_hook or ""
                    }
                    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
                        writer = csv_module.DictWriter(f, fieldnames=list(row.keys()))
                        writer.writerow(row)
                except Exception as e:
                    print(f"[SendMessage] Warning saving lead to CSV: {e}")

            if store.is_opted_out(lead.lead_id):
                self._send_json({"status": "error", "message": "Lead is opted out"}, 400)
                return

            if channel == "email" and not lead.email:
                self._send_json({"status": "error", "message": "Cannot send EMAIL: Lead has no email address."}, 400)
                return

            if channel in ("sms", "whatsapp") and not lead.phone:
                self._send_json({"status": "error", "message": f"Cannot send {channel.upper()}: Lead has no phone number."}, 400)
                return

            state = store.get_follow_up_state(lead.lead_id, channel)
            follow_up_count = state["follow_up_count"] if state else 0
            is_initial = state is None

            dry_run = bool(payload.get("dry_run", False))

            # Generate message for this cadence step
            if channel == "email":
                from message_generator import generate_email
                target_count = (follow_up_count + 1) if not is_initial else 0
                draft = generate_email(lead, follow_up_count=target_count)
                if custom_subject:
                    draft.subject = custom_subject
                if custom_body:
                    draft.body = custom_body
                target = lead.email
                if dry_run:
                    print(f"  [SAFE DEMO - DRY RUN] Simulating EMAIL to {lead.contact_name} ({target})")
                    ok = True
                else:
                    from providers.email_provider import EmailProvider
                    provider = EmailProvider()
                    ok = provider.send(target, draft.subject, draft.body)
            elif channel == "sms":
                from message_generator import generate_sms
                draft = generate_sms(lead)
                if custom_body:
                    draft.body = custom_body
                from phone_utils import normalize_to_e164
                default_cc = "+91" if (getattr(lead, 'country', None) and str(lead.country).strip().lower() in ("india", "in", "+91", "91")) else "+1"
                normalized_target = normalize_to_e164(lead.phone, default_country_code=default_cc)
                if not normalized_target:
                    self._send_json({"status": "error", "message": f"Invalid phone number: {lead.phone}"}, 400)
                    return
                target = normalized_target
                if dry_run:
                    print(f"  [SAFE DEMO - DRY RUN] Simulating SMS to {lead.contact_name} ({target})")
                    ok = True
                else:
                    from providers.sms_provider import SMSProvider
                    provider = SMSProvider()
                    ok = provider.send(target, draft.body, country=getattr(lead, 'country', None))
            else:
                from message_generator import generate_whatsapp
                draft = generate_whatsapp(lead)
                if custom_body:
                    draft.body = custom_body
                from phone_utils import normalize_to_e164
                default_cc = "+91" if (getattr(lead, 'country', None) and str(lead.country).strip().lower() in ("india", "in", "+91", "91")) else "+1"
                normalized_target = normalize_to_e164(lead.phone, default_country_code=default_cc)
                if not normalized_target:
                    self._send_json({"status": "error", "message": f"Invalid phone number: {lead.phone}"}, 400)
                    return
                target = normalized_target
                if dry_run:
                    print(f"  [SAFE DEMO - DRY RUN] Simulating WHATSAPP to {lead.contact_name} ({target})")
                    ok = True
                else:
                    from providers.whatsapp_provider import WhatsAppProvider
                    provider = WhatsAppProvider()
                    ok = provider.send(target, draft.body, country=getattr(lead, 'country', None))

            if ok:
                msg_id = store.queue_for_approval(draft)
                store.approve_message(msg_id, approved_by="Web Dashboard User (Safe Demo)" if dry_run else "Web Dashboard User")
                store.mark_sent(msg_id)
                if is_initial:
                    store.record_initial_send(lead.lead_id, channel)
                else:
                    store.record_follow_up_sent(lead.lead_id, channel, follow_up_count + 1)

                mode_prefix = "[Safe Demo] " if dry_run else ""
                self._send_json({
                    "status": "success",
                    "message": f"{mode_prefix}Dispatched {channel.upper()} to {lead.contact_name} ({target})",
                    "follow_up_count": follow_up_count + 1 if not is_initial else 0,
                    "subject": getattr(draft, "subject", None),
                    "dry_run": dry_run
                })
            else:
                self._send_json({"status": "error", "message": f"Provider failed to send {channel.upper()}. Check API keys or network connection."}, 500)
        except Exception as e:
            print(f"[SendMessage] Unhandled Exception: {e}")
            self._send_json({"status": "error", "message": f"Dispatch error: {str(e)}"}, 500)

    def handle_get_dashboard(self):
        store = StateStore(db_path="outreach.db")
        source = CSVLeadSource(csv_path="data/leads.csv")
        leads = source.get_all_leads()

        dashboard_rows = store.get_dashboard_rows(leads)
        
        # Organize per lead with channel sub-objects
        lead_map = {}
        for lead in leads:
            crm = store.get_lead_crm(lead.lead_id) or {}
            lead_map[lead.lead_id] = {
                "lead_id": lead.lead_id,
                "company": lead.company,
                "website": lead.website,
                "contact_name": lead.contact_name,
                "designation": lead.designation,
                "email": lead.email,
                "phone": lead.phone,
                "country": lead.country,
                "city": crm.get("city") or lead.city,
                "industry": crm.get("industry") or lead.industry,
                "lead_score": lead.lead_score,
                "lead_status": lead.lead_status.value,
                "primary_service": lead.primary_service,
                "personalization_hook": lead.personalization_hook,
                "opportunity_value": crm.get("opportunity_value") if crm.get("opportunity_value") is not None else lead.opportunity_value,
                "salesperson": crm.get("salesperson") or lead.salesperson,
                "notes": crm.get("notes") or lead.notes,
                "is_opted_out": store.is_opted_out(lead.lead_id),
                "channels": {}
            }

        for row in dashboard_rows:
            # Match company to lead
            for lead_id, l_data in lead_map.items():
                if l_data["company"] == row["company"]:
                    l_data["channels"][row["channel"].lower()] = {
                        "channel": row["channel"],
                        "status": row["status"],
                        "last_sent": row["last_sent"],
                        "next_follow_up": row["next_follow_up"],
                        "reply_classification": row["reply_classification"]
                    }

        # Calculate metrics
        statuses = [r["status"] for r in dashboard_rows]
        metrics = {
            "total_leads": len(leads),
            "total_slots": len(dashboard_rows),
            "contacted": sum(1 for s in statuses if s != "NOT_CONTACTED"),
            "awaiting_reply": sum(1 for s in statuses if s == "AWAITING_REPLY"),
            "follow_up_due": sum(1 for s in statuses if s == "FOLLOW_UP_DUE"),
            "replied": sum(1 for s in statuses if s == "REPLIED"),
            "opted_out": sum(1 for s in statuses if s == "OPTED_OUT"),
            "last_reply_check": store.get_last_reply_check() or "Never",
            "company_name": "SAUBHAGYAM",
            "sender_name": "Priya"
        }

        # Recent activities / sent messages
        recent_messages = []
        try:
            cur = store.conn.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT 15"
            )
            for r in cur.fetchall():
                recent_messages.append(dict(r))
        except Exception:
            pass

        # Escalations list
        escalations = []
        try:
            escalations_sent_keys = {
                row["reply_key"].split(":")[0]
                for row in store.conn.execute("SELECT reply_key FROM escalations_sent").fetchall()
                if ":" in row["reply_key"]
            }
            cur = store.conn.execute(
                "SELECT * FROM follow_up_state WHERE reply_classification IS NOT NULL"
            )
            for r in cur.fetchall():
                classification_str = r["reply_classification"]
                if classification_str:
                    try:
                        enum_val = classify_reply(classification_str)
                        if needs_human_escalation(enum_val) or r["lead_id"] in escalations_sent_keys:
                            lead_info = next((l for l in leads if l.lead_id == r["lead_id"]), None)
                            escalations.append({
                                "lead_id": r["lead_id"],
                                "company": lead_info.company if lead_info else r["lead_id"],
                                "contact_name": lead_info.contact_name if lead_info else "Lead",
                                "channel": r["channel"],
                                "classification": classification_str,
                                "received_at": r["reply_received_at"]
                            })
                    except Exception:
                        pass
        except Exception:
            pass

        self._send_json({
            "metrics": metrics,
            "leads": list(lead_map.values()),
            "recent_messages": recent_messages,
            "escalations": escalations
        })

    def handle_get_fetch_hetvi_leads(self):
        """Fetch leads from Hetvi's discovery API, filter out already-imported ones."""
        try:
            from providers.hetvi_lead_source import fetch_hetvi_leads
            hetvi_leads = fetch_hetvi_leads()

            store = StateStore(db_path="outreach.db")
            for hl in hetvi_leads:
                HETVI_LEADS_CACHE[hl["lead_id"]] = hl
                store.record_discovery(lead_id=hl["lead_id"], company=hl.get("company", ""), source="hetvi")

            # Get existing lead_ids from CSV for duplicate filtering
            existing_ids = set()
            csv_path = "data/leads.csv"
            if os.path.exists(csv_path):
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    reader = csv_module.DictReader(f)
                    for row in reader:
                        existing_ids.add(row.get("lead_id", ""))

            # Filter out already-activated leads
            new_leads = [l for l in hetvi_leads if l["lead_id"] not in existing_ids]

            # Priority Sort: Leads with BOTH email and phone -> top, ONE available -> middle, NEITHER -> bottom
            def contact_priority(lead):
                has_email = bool(lead.get("email") and str(lead.get("email")).strip())
                has_phone = bool(lead.get("phone") and str(lead.get("phone")).strip())
                if has_email and has_phone:
                    return 2
                if has_email or has_phone:
                    return 1
                return 0

            new_leads.sort(key=contact_priority, reverse=True)

            # Annotate each lead with phone reachability heuristic from phone_utils
            from phone_utils import normalize_to_e164, is_likely_unreachable_for_sms_whatsapp
            for lead in new_leads:
                raw_phone = lead.get("phone")
                if raw_phone and str(raw_phone).strip():
                    country = lead.get("country", "")
                    default_cc = "+91" if (country and str(country).strip().lower() in ("india", "in", "+91", "91")) else "+1"
                    e164 = normalize_to_e164(str(raw_phone), default_country_code=default_cc)
                    if e164:
                        unreachable, reason = is_likely_unreachable_for_sms_whatsapp(e164)
                        lead["phone_normalized"] = e164
                        lead["phone_unreachable"] = unreachable
                        lead["phone_unreachable_reason"] = reason
                    else:
                        lead["phone_normalized"] = None
                        lead["phone_unreachable"] = True
                        lead["phone_unreachable_reason"] = "Could not parse phone number into E.164"
                else:
                    lead["phone_normalized"] = None
                    lead["phone_unreachable"] = False
                    lead["phone_unreachable_reason"] = ""

            if not hetvi_leads and not new_leads:
                # fetch_hetvi_leads returned empty — could be network error or no leads
                self._send_json({
                    "status": "success",
                    "leads": [],
                    "total_from_api": 0,
                    "filtered_duplicates": 0,
                    "message": "No leads returned from Hetvi's service. Check network or API availability."
                })
                return


            self._send_json({
                "status": "success",
                "leads": new_leads,
                "total_from_api": len(hetvi_leads),
                "filtered_duplicates": len(hetvi_leads) - len(new_leads)
            })
        except Exception as e:
            print(f"[FetchHetviLeads] Error: {e}")
            self._send_json({
                "status": "error",
                "message": f"Could not fetch Hetvi leads: {str(e)}",
                "leads": []
            }, 500)

    def handle_get_simulate(self, days_forward: int):
        simulated_date = date.today() + timedelta(days=days_forward)
        store = StateStore(db_path="outreach.db")
        source = CSVLeadSource(csv_path="data/leads.csv")
        leads = source.get_actionable_leads()

        results = []
        for lead in leads:
            is_opted_out = store.is_opted_out(lead.lead_id)
            for ch in ["email", "sms", "whatsapp"]:
                if is_opted_out:
                    action = "OPTED_OUT"
                else:
                    act = next_action(store, lead.lead_id, ch, as_of_date=simulated_date)
                    action = act.value

                state = store.get_follow_up_state(lead.lead_id, ch)
                results.append({
                    "lead_id": lead.lead_id,
                    "company": lead.company,
                    "contact_name": lead.contact_name,
                    "channel": ch.upper(),
                    "projected_action": action,
                    "current_count": state["follow_up_count"] if state else 0,
                    "next_date": state["next_follow_up_date"] if state else None
                })

        self._send_json({
            "simulated_days": days_forward,
            "simulated_date": simulated_date.isoformat(),
            "projections": results
        })

    def handle_get_lead_details(self, lead_id: str):
        store = StateStore(db_path="outreach.db")
        lead = get_lead_or_hetvi(lead_id)

        if not lead:
            self._send_json({"error": "Lead not found"}, 404)
            return

        drafts = generate_all_channels(lead)
        draft_list = []
        for d in drafts:
            draft_list.append({
                "channel": d.channel.value,
                "subject": d.subject,
                "body": d.body
            })

        # Sent history
        sent_history = []
        try:
            cur = store.conn.execute(
                "SELECT * FROM messages WHERE lead_id = ? ORDER BY id DESC",
                (lead.lead_id,)
            )
            for r in cur.fetchall():
                sent_history.append(dict(r))
        except Exception:
            pass

        crm = store.get_lead_crm(lead.lead_id) or {}
        lead_dict = lead.dict()
        if crm.get("city") is not None: lead_dict["city"] = crm["city"]
        if crm.get("industry") is not None: lead_dict["industry"] = crm["industry"]
        if crm.get("opportunity_value") is not None: lead_dict["opportunity_value"] = crm["opportunity_value"]
        if crm.get("salesperson") is not None: lead_dict["salesperson"] = crm["salesperson"]
        if crm.get("notes") is not None: lead_dict["notes"] = crm["notes"]

        timeline = store.get_conversation_timeline(lead.lead_id)

        self._send_json({
            "lead": lead_dict,
            "drafts": draft_list,
            "history": sent_history,
            "conversation_timeline": timeline,
            "timeline": timeline,
            "is_opted_out": store.is_opted_out(lead.lead_id)
        })

    def handle_get_lead_timeline(self, lead_id: str):
        store = StateStore(db_path="outreach.db")
        timeline = store.get_conversation_timeline(lead_id)
        self._send_json({
            "status": "success",
            "lead_id": lead_id,
            "timeline": timeline,
            "conversation_timeline": timeline,
            "count": len(timeline)
        })

    def handle_post_check_replies(self):
        store = StateStore(db_path="outreach.db")
        source = CSVLeadSource(csv_path="data/leads.csv")
        leads = source.get_actionable_leads()

        email_to_lead = {}
        for lead in leads:
            if lead.email:
                email_to_lead[lead.email.strip().lower()] = lead

        known_emails = set(email_to_lead.keys())
        last_checked = store.get_last_reply_check()

        try:
            from providers.email_reader import fetch_replies
            replies = fetch_replies(known_emails, after_timestamp=last_checked)
            store.record_reply_check()

            processed = []
            escalations_triggered = []
            for reply in replies:
                sender = reply["sender"]
                lead = email_to_lead.get(sender)
                if lead:
                    cls = process_reply(lead, reply["body"], store, channel="email", received_at=reply.get("received_at"))
                    processed.append({
                        "lead_id": lead.lead_id,
                        "company": lead.company,
                        "classification": cls.value,
                        "body": reply["body"]
                    })
                    extra_signals = detect_additional_escalation_signals(reply["body"], lead_email=lead.email if lead else None)
                    if needs_human_escalation(cls) or len(extra_signals) > 0:
                        escalations_triggered.append({
                            "lead_id": lead.lead_id,
                            "company": lead.company,
                            "contact_name": lead.contact_name,
                            "classification": cls.value,
                            "triggers": [s["trigger"] for s in extra_signals]
                        })

            self._send_json({
                "status": "success",
                "replies_found": len(replies),
                "processed": processed,
                "escalations_triggered": escalations_triggered,
                "checked_at": datetime.now().isoformat()
            })
        except Exception as e:
            self._send_json({
                "status": "error",
                "message": str(e)
            }, 500)


import webbrowser
import threading


def start_server():
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    url = f"http://localhost:{PORT}"
    print("\n=======================================================")
    print(">>> OUTREACH AGENT WEB DASHBOARD STARTED")
    print(f">>> Dashboard URL: {url}")
    print(">>> Automatically opening browser...")
    print("=======================================================\n")
    
    # Auto-open browser after 1 second
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web dashboard server...")
        server.server_close()


if __name__ == "__main__":
    start_server()
