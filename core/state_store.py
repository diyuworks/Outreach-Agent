"""
SQLite-backed state store (free, zero-setup).
Tracks: message history, follow-up schedule, opt-out list (cross-channel),
and pending human-approval queue.
"""
import sqlite3
from datetime import datetime, date, timedelta
from typing import Optional
from core.models import DraftMessage, ReplyClassification


class StateStore:
    def __init__(self, db_path: str = "outreach.db"):
        self.conn = sqlite3.connect(db_path, timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self._init_schema()
        self._migrate_schema()

    def _init_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT,
                channel TEXT,
                subject TEXT,
                body TEXT,
                approved INTEGER DEFAULT 0,
                approved_by TEXT,
                sent INTEGER DEFAULT 0,
                sent_at TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS follow_up_state (
                lead_id TEXT,
                channel TEXT,
                follow_up_count INTEGER DEFAULT 0,
                next_follow_up_date TEXT,
                last_message_at TEXT,
                reply_received_at TEXT,
                reply_classification TEXT,
                PRIMARY KEY (lead_id, channel)
            );

            -- Cross-channel: one opt-out here blocks ALL channels for that lead
            CREATE TABLE IF NOT EXISTS opt_outs (
                lead_id TEXT PRIMARY KEY,
                opted_out_at TEXT
            );

            -- Tracks when we last polled the inbox for replies
            CREATE TABLE IF NOT EXISTS reply_check_log (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_checked_at TEXT
            );

            -- Dedup tracking for escalation alerts
            CREATE TABLE IF NOT EXISTS escalations_sent (
                reply_key TEXT PRIMARY KEY,
                sent_at TEXT
            );

            -- One-off scheduled messages (sent by scheduler.py when due)
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_name TEXT,
                channel TEXT,
                recipient_address TEXT,
                subject TEXT,
                body TEXT,
                send_at TEXT,
                sent INTEGER DEFAULT 0,
                sent_at TEXT,
                created_at TEXT
            );

            -- CRM Lead Data (Spec Section 15)
            CREATE TABLE IF NOT EXISTS leads (
                lead_id TEXT PRIMARY KEY,
                company TEXT,
                website TEXT,
                contact_name TEXT,
                designation TEXT,
                email TEXT,
                phone TEXT,
                country TEXT,
                city TEXT,
                industry TEXT,
                lead_score INTEGER,
                lead_status TEXT,
                primary_service TEXT,
                personalization_hook TEXT,
                opportunity_value REAL,
                salesperson TEXT,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            -- Log of all inbound replies with verbatim text (Spec Section 17)
            CREATE TABLE IF NOT EXISTS replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT,
                channel TEXT,
                classification TEXT,
                body TEXT,
                received_at TEXT
            );

            -- Discovery log tracking leads discovered per day
            CREATE TABLE IF NOT EXISTS discovery_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT UNIQUE,
                company TEXT,
                source TEXT,
                discovered_at TEXT
            );
            """
        )
        self.conn.commit()

    def _migrate_schema(self):
        """Migration-safe column additions for existing SQLite tables."""
        cur = self.conn.execute("PRAGMA table_info(leads)")
        existing_cols = {row["name"] for row in cur.fetchall()}
        crm_columns = [
            ("city", "TEXT"),
            ("industry", "TEXT"),
            ("opportunity_value", "REAL"),
            ("salesperson", "TEXT"),
            ("notes", "TEXT"),
            ("created_at", "TEXT"),
            ("updated_at", "TEXT"),
        ]
        for col_name, col_type in crm_columns:
            if col_name not in existing_cols:
                self.conn.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")

        # Check follow_up_state for reply_body and reply_text columns
        cur_fu = self.conn.execute("PRAGMA table_info(follow_up_state)")
        existing_fu_cols = {row["name"] for row in cur_fu.fetchall()}
        if "reply_body" not in existing_fu_cols:
            self.conn.execute("ALTER TABLE follow_up_state ADD COLUMN reply_body TEXT")
        if "reply_text" not in existing_fu_cols:
            self.conn.execute("ALTER TABLE follow_up_state ADD COLUMN reply_text TEXT")

        # Ensure replies and discovery_log tables exist
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT,
                channel TEXT,
                classification TEXT,
                body TEXT,
                received_at TEXT
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS discovery_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT UNIQUE,
                company TEXT,
                source TEXT,
                discovered_at TEXT
            );
            """
        )
        self.conn.commit()

    # ---------- CRM Lead Methods (Spec Section 15) ----------
    def get_lead_crm(self, lead_id: str) -> Optional[dict]:
        """Fetch CRM attributes for a specific lead."""
        row = self.conn.execute("SELECT * FROM leads WHERE lead_id = ?", (lead_id,)).fetchone()
        return dict(row) if row else None

    def update_lead_field(self, lead_id: str, field: str, value):
        """Generic method to update a single CRM field for a lead."""
        valid_fields = {
            "city", "industry", "opportunity_value", "salesperson", "notes",
            "company", "contact_name", "designation", "email", "phone",
            "country", "lead_score", "lead_status", "primary_service", "personalization_hook"
        }
        if field not in valid_fields:
            raise ValueError(f"Invalid lead CRM field: {field}")
        self.conn.execute("INSERT OR IGNORE INTO leads (lead_id) VALUES (?)", (lead_id,))
        self.conn.execute(
            f"UPDATE leads SET {field} = ?, updated_at = ? WHERE lead_id = ?",
            (value, datetime.now().isoformat(), lead_id),
        )
        self.conn.commit()

    def update_lead_notes(self, lead_id: str, notes: str):
        """Update free-text sales notes for a lead."""
        self.update_lead_field(lead_id, "notes", notes)

    def update_opportunity_value(self, lead_id: str, value: Optional[float]):
        """Update estimated deal opportunity value for a lead."""
        self.update_lead_field(lead_id, "opportunity_value", value)

    def assign_salesperson(self, lead_id: str, salesperson: str):
        """Assign or reassign a lead owner / salesperson."""
        self.update_lead_field(lead_id, "salesperson", salesperson)

    def update_lead_crm(self, lead_id: str, **kwargs):
        """Update multiple CRM fields in one operation."""
        valid_fields = {
            "city", "industry", "opportunity_value", "salesperson", "notes",
            "company", "contact_name", "designation", "email", "phone",
            "country", "lead_score", "lead_status", "primary_service", "personalization_hook"
        }
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        if not updates:
            return
        self.conn.execute("INSERT OR IGNORE INTO leads (lead_id) VALUES (?)", (lead_id,))
        set_clauses = [f"{k} = ?" for k in updates.keys()]
        values = list(updates.values())
        values.append(datetime.now().isoformat())
        values.append(lead_id)
        query = f"UPDATE leads SET {', '.join(set_clauses)}, updated_at = ? WHERE lead_id = ?"
        self.conn.execute(query, values)
        self.conn.commit()


    # ---------- Escalation Alert Dedup ----------
    def escalation_already_sent(self, reply_key: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM escalations_sent WHERE reply_key = ?", (reply_key,)
        ).fetchone()
        return row is not None

    def record_escalation_sent(self, reply_key: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO escalations_sent (reply_key, sent_at) VALUES (?, ?)",
            (reply_key, datetime.now().isoformat()),
        )
        self.conn.commit()

    # ---------- Scheduled Messages (one-off sends) ----------
    def add_scheduled_message(self, recipient_name, channel, recipient_address,
                               body, send_at_iso, subject=None) -> int:
        cur = self.conn.execute(
            "INSERT INTO scheduled_messages "
            "(recipient_name, channel, recipient_address, subject, body, send_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (recipient_name, channel, recipient_address, subject, body,
             send_at_iso, datetime.now().isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_due_scheduled_messages(self, as_of_iso: str = None):
        as_of_iso = as_of_iso or datetime.now().isoformat()
        return self.conn.execute(
            "SELECT * FROM scheduled_messages WHERE sent = 0 AND send_at <= ?",
            (as_of_iso,),
        ).fetchall()

    def mark_scheduled_message_sent(self, message_id: int):
        self.conn.execute(
            "UPDATE scheduled_messages SET sent = 1, sent_at = ? WHERE id = ?",
            (datetime.now().isoformat(), message_id),
        )
        self.conn.commit()

    # ---------- Opt-out (cross-channel, spec Section 8/9) ----------
    def is_opted_out(self, lead_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM opt_outs WHERE lead_id = ?", (lead_id,)
        ).fetchone()
        return row is not None

    def record_opt_out(self, lead_id: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO opt_outs (lead_id, opted_out_at) VALUES (?, ?)",
            (lead_id, datetime.now().isoformat()),
        )
        self.conn.commit()
        print(f"  [OPT-OUT RECORDED] {lead_id} suppressed on ALL channels going forward.")

    # ---------- Approval queue ----------
    def queue_for_approval(self, msg: DraftMessage) -> int:
        cur = self.conn.execute(
            "INSERT INTO messages (lead_id, channel, subject, body, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (msg.lead_id, msg.channel.value, msg.subject, msg.body, datetime.now().isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid

    def approve_message(self, message_id: int, approved_by: str):
        self.conn.execute(
            "UPDATE messages SET approved = 1, approved_by = ? WHERE id = ?",
            (approved_by, message_id),
        )
        self.conn.commit()

    def mark_sent(self, message_id: int):
        self.conn.execute(
            "UPDATE messages SET sent = 1, sent_at = ? WHERE id = ?",
            (datetime.now().isoformat(), message_id),
        )
        self.conn.commit()

    # ---------- Follow-up state (spec Section 7) ----------
    FOLLOW_UP_GAPS_DAYS = [3, 6, 7]  # business-day approximations for demo simplicity

    def get_follow_up_state(self, lead_id: str, channel: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM follow_up_state WHERE lead_id = ? AND channel = ?",
            (lead_id, channel),
        ).fetchone()

    def record_initial_send(self, lead_id: str, channel: str):
        next_date = date.today() + timedelta(days=self.FOLLOW_UP_GAPS_DAYS[0])
        self.conn.execute(
            "INSERT OR REPLACE INTO follow_up_state "
            "(lead_id, channel, follow_up_count, next_follow_up_date, last_message_at) "
            "VALUES (?, ?, 0, ?, ?)",
            (lead_id, channel, next_date.isoformat(), datetime.now().isoformat()),
        )
        self.conn.commit()

    def record_follow_up_sent(self, lead_id: str, channel: str, follow_up_count: int):
        gap = (
            self.FOLLOW_UP_GAPS_DAYS[follow_up_count]
            if follow_up_count < len(self.FOLLOW_UP_GAPS_DAYS)
            else None
        )
        next_date = (date.today() + timedelta(days=gap)).isoformat() if gap else None
        self.conn.execute(
            "UPDATE follow_up_state SET follow_up_count = ?, next_follow_up_date = ?, "
            "last_message_at = ? WHERE lead_id = ? AND channel = ?",
            (follow_up_count, next_date, datetime.now().isoformat(), lead_id, channel),
        )
        self.conn.commit()

    def record_reply(self, lead_id: str, channel: str, classification,
                     reply_text: Optional[str] = None, received_at: Optional[str] = None):
        rx_time = received_at or datetime.now().isoformat()
        cls_val = classification.value if hasattr(classification, "value") else str(classification)
        cur = self.conn.execute(
            "UPDATE follow_up_state SET reply_received_at = ?, reply_classification = ?, "
            "next_follow_up_date = NULL WHERE lead_id = ? AND channel = ?",
            (rx_time, cls_val, lead_id, channel),
        )
        if cur.rowcount == 0:
            self.conn.execute(
                "INSERT OR REPLACE INTO follow_up_state (lead_id, channel, reply_received_at, reply_classification) "
                "VALUES (?, ?, ?, ?)",
                (lead_id, channel, rx_time, cls_val),
            )
        self.conn.execute(
            "INSERT INTO replies (lead_id, channel, classification, body, received_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (lead_id, channel, cls_val, reply_text or "", rx_time),
        )
        self.conn.commit()

    # ---------- Conversation Timeline (per-lead, all channels) ----------
    def get_conversation_timeline(self, lead_id: str) -> list:
        """
        Return every sent-message and received-reply event for this lead across all channels,
        sorted chronologically ascending (oldest first).
        """
        timeline = []

        # 1. Sent messages from 'messages' table
        try:
            cur_sent = self.conn.execute(
                "SELECT channel, subject, body, sent_at, created_at FROM messages "
                "WHERE lead_id = ? AND sent = 1 ORDER BY sent_at ASC, id ASC",
                (lead_id,)
            )
            for row in cur_sent.fetchall():
                ts = row["sent_at"] or row["created_at"] or ""
                body = row["body"] or ""
                ch = (row["channel"] or "email").lower()
                timeline.append({
                    "type": "sent",
                    "channel": ch,
                    "timestamp": ts,
                    "content": body,
                    "subject": row["subject"],
                    "classification": None
                })
        except Exception as e:
            print(f"[Timeline] Error querying sent messages: {e}")

        # 2. Received replies from 'replies' table
        seen_reply_timestamps = set()
        try:
            cur_replies = self.conn.execute(
                "SELECT channel, classification, body, received_at FROM replies "
                "WHERE lead_id = ? ORDER BY received_at ASC, id ASC",
                (lead_id,)
            )
            for row in cur_replies.fetchall():
                ts = row["received_at"] or ""
                body = row["body"]
                content = body if (body and str(body).strip()) else "[reply text not available for this older record]"
                ch = (row["channel"] or "email").lower()
                timeline.append({
                    "type": "received",
                    "channel": ch,
                    "timestamp": ts,
                    "content": content,
                    "classification": row["classification"]
                })
                if ts:
                    seen_reply_timestamps.add((ch, ts))
        except Exception as e:
            print(f"[Timeline] Error querying replies table: {e}")

        # 3. Fallback check on follow_up_state for older records not in replies table
        try:
            cur_fu = self.conn.execute(
                "SELECT channel, reply_received_at, reply_classification, reply_body, reply_text FROM follow_up_state "
                "WHERE lead_id = ? AND reply_received_at IS NOT NULL",
                (lead_id,)
            )
            for row in cur_fu.fetchall():
                ts = row["reply_received_at"] or ""
                ch = (row["channel"] or "email").lower()
                if (ch, ts) not in seen_reply_timestamps:
                    body = row["reply_text"] or row["reply_body"]
                    content = body if (body and str(body).strip()) else "[reply text not available for this older record]"
                    timeline.append({
                        "type": "received",
                        "channel": ch,
                        "timestamp": ts,
                        "content": content,
                        "classification": row["reply_classification"]
                    })
        except Exception as e:
            print(f"[Timeline] Error querying follow_up_state fallback: {e}")

        # Sort chronologically ascending (oldest first)
        timeline.sort(key=lambda item: item.get("timestamp") or "")
        return timeline

    # ---------- Reporting queries (Spec Section 17) ----------
    def record_discovery(self, lead_id: str, company: str = "", source: str = "hetvi", discovered_at: Optional[str] = None):
        ts = discovered_at or datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR IGNORE INTO discovery_log (lead_id, company, source, discovered_at) "
            "VALUES (?, ?, ?, ?)",
            (lead_id, company, source, ts),
        )
        self.conn.commit()

    def get_daily_discovery_count(self, date_str: str) -> int:
        cur = self.conn.execute(
            "SELECT count(*) as c FROM discovery_log WHERE discovered_at LIKE ?",
            (f"{date_str}%",),
        )
        return cur.fetchone()["c"]

    def get_daily_messages_sent_count(self, date_str: str) -> int:
        cur = self.conn.execute(
            "SELECT count(*) as c FROM messages WHERE sent = 1 AND sent_at LIKE ?",
            (f"{date_str}%",),
        )
        return cur.fetchone()["c"]

    def get_daily_messages_prepared_count(self, date_str: str) -> int:
        cur = self.conn.execute(
            "SELECT count(*) as c FROM messages WHERE created_at LIKE ?",
            (f"{date_str}%",),
        )
        return cur.fetchone()["c"]

    def get_daily_replies(self, date_str: str) -> list:
        rows = self.conn.execute(
            "SELECT r.*, l.company, l.contact_name FROM replies r "
            "LEFT JOIN leads l ON r.lead_id = l.lead_id "
            "WHERE r.received_at LIKE ? ORDER BY r.id ASC",
            (f"{date_str}%",),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_daily_objections(self, date_str: str) -> list:
        rows = self.conn.execute(
            "SELECT r.*, l.company, l.contact_name FROM replies r "
            "LEFT JOIN leads l ON r.lead_id = l.lead_id "
            "WHERE r.classification = 'NOT_INTERESTED' AND r.received_at LIKE ? "
            "ORDER BY r.id ASC",
            (f"{date_str}%",),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- Reply check log (Feature 3) ----------
    def get_last_reply_check(self) -> Optional[str]:
        row = self.conn.execute(
            "SELECT last_checked_at FROM reply_check_log WHERE id = 1"
        ).fetchone()
        return row["last_checked_at"] if row else None

    def record_reply_check(self):
        self.conn.execute(
            "INSERT OR REPLACE INTO reply_check_log (id, last_checked_at) VALUES (1, ?)",
            (datetime.now().isoformat(),),
        )
        self.conn.commit()

    # ---------- Dashboard (read-only) ----------
    def get_dashboard_rows(self, leads) -> list:
        """
        Build a per-lead/per-channel status grid by combining lead metadata
        (from CSVLeadSource) with DB state. Returns a list of dicts.
        """
        channels = ["email", "sms", "whatsapp"]
        rows = []
        for lead in leads:
            is_opted_out = self.is_opted_out(lead.lead_id)
            for ch in channels:
                state = self.get_follow_up_state(lead.lead_id, ch)

                # Last sent date: latest sent message for this lead+channel
                sent_row = self.conn.execute(
                    "SELECT sent_at FROM messages "
                    "WHERE lead_id = ? AND channel = ? AND sent = 1 "
                    "ORDER BY sent_at DESC LIMIT 1",
                    (lead.lead_id, ch),
                ).fetchone()
                last_sent = sent_row["sent_at"][:10] if sent_row and sent_row["sent_at"] else None

                # Derive status
                next_fu = None
                reply_class = None
                if is_opted_out:
                    status = "OPTED_OUT"
                elif state is None:
                    status = "NOT_CONTACTED"
                else:
                    reply_class = state["reply_classification"]
                    next_fu = state["next_follow_up_date"]
                    if reply_class:
                        status = "REPLIED"
                    elif state["follow_up_count"] >= 3 and not next_fu:
                        status = "NURTURE"
                    elif next_fu and date.fromisoformat(next_fu) <= date.today():
                        status = "FOLLOW_UP_DUE"
                    elif last_sent:
                        status = "AWAITING_REPLY"
                    else:
                        status = "SENT"

                rows.append({
                    "company": lead.company,
                    "contact_name": lead.contact_name,
                    "channel": ch.upper(),
                    "status": status,
                    "last_sent": last_sent or "—",
                    "next_follow_up": next_fu or "—",
                    "reply_classification": reply_class or "—",
                })
        return rows

