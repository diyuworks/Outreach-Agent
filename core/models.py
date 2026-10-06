"""
Data models for the Outreach & Follow-Up Agent.
Matches the input data contract defined by the Lead Generation team.
"""
from datetime import datetime, date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class LeadStatus(str, Enum):
    NEW = "NEW"
    RESEARCHED = "RESEARCHED"
    QUALIFIED = "QUALIFIED"
    CONTACTED = "CONTACTED"
    FOLLOW_UP = "FOLLOW_UP"
    RESPONDED = "RESPONDED"
    INTERESTED = "INTERESTED"
    MEETING = "MEETING"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"
    NURTURE = "NURTURE"
    OPT_OUT = "OPT_OUT"


class Channel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class ReplyClassification(str, Enum):
    HOT = "HOT"
    INTERESTED = "INTERESTED"
    REQUEST_FOR_INFORMATION = "REQUEST_FOR_INFORMATION"
    MEETING_REQUEST = "MEETING_REQUEST"
    PRICE_REQUEST = "PRICE_REQUEST"
    NOT_NOW = "NOT_NOW"
    NOT_INTERESTED = "NOT_INTERESTED"
    WRONG_PERSON = "WRONG_PERSON"
    OPT_OUT = "OPT_OUT"
    UNKNOWN = "UNKNOWN"


class Lead(BaseModel):
    """Matches Section 2 of the spec — the interface contract with the Lead Gen team."""
    lead_id: str
    company: str
    website: Optional[str] = None
    contact_name: str
    designation: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None  # E.164 format e.g. +919876543210
    country: Optional[str] = None
    lead_score: Optional[int] = Field(default=None, ge=0, le=100)
    lead_status: LeadStatus = LeadStatus.NEW
    primary_service: Optional[str] = ""
    personalization_hook: Optional[str] = ""
    city: Optional[str] = None
    industry: Optional[str] = None
    opportunity_value: Optional[float] = None  # estimated deal value, currency-agnostic number
    salesperson: Optional[str] = None  # who owns this lead
    notes: Optional[str] = None  # free-text notes, human-entered


class DraftMessage(BaseModel):
    lead_id: str
    channel: Channel
    subject: Optional[str] = None  # email only
    body: str
    created_at: datetime = Field(default_factory=datetime.now)
    approved: bool = False
    approved_by: Optional[str] = None
    sent: bool = False
    sent_at: Optional[datetime] = None


class FollowUpState(BaseModel):
    lead_id: str
    channel: Channel
    follow_up_count: int = 0
    next_follow_up_date: Optional[date] = None
    last_message_at: Optional[datetime] = None
    reply_received_at: Optional[datetime] = None
    reply_classification: Optional[ReplyClassification] = None
    opt_out: bool = False
