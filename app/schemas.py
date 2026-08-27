from typing import Optional
from pydantic import BaseModel, Field


class TicketInput(BaseModel):
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    account_id: Optional[str] = None
    ticket_id: Optional[str] = None


class KBMatch(BaseModel):
    doc_path: str
    heading: str
    score: float
    excerpt: str


class TriageResult(BaseModel):
    product_area: str
    issue_category: str
    urgency_tier: str  # P1-P4
    reasoning: str
    kb_matches: list[KBMatch] = []
    recommended_responder_team: str
    draft_first_response: str
    prompt_version: str


class RiskFlag(BaseModel):
    ticket_id: Optional[str] = None
    signal: str
    justification_quote: str


class AccountBrief(BaseModel):
    account_id: str
    company: str
    found: bool
    executive_summary: Optional[str] = None
    open_risks_and_flags: list[RiskFlag] = []
    recommended_talking_points: list[str] = []
    tickets_considered: int = 0
    prompt_version: str
    error: Optional[str] = None
