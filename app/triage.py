"""
Task 1 — Intelligent ticket triage agent.

Given a raw ticket (subject + body), produces a structured triage decision:
product area, issue category, urgency tier (P1-P4) with reasoning, matched
KB doc(s), a recommended responder team, and a draft first-response.
"""
import re

from app import kb_retrieval, llm_client, observability
from app.config import PROMPT_VERSIONS
from app.schemas import TicketInput, TriageResult, KBMatch

VALID_CATEGORIES = [
    "Bug", "Feature Request", "How-To", "Performance",
    "Billing", "Integration", "Onboarding", "Data Loss",
]
VALID_URGENCY = ["P1", "P2", "P3", "P4"]

RESPONDER_TEAMS = {
    "Bug": "Tier-2 Engineering Support",
    "Feature Request": "Product Management",
    "How-To": "Tier-1 Support",
    "Performance": "Tier-2 Engineering Support",
    "Billing": "Billing & Renewals",
    "Integration": "Integrations/Platform Support",
    "Onboarding": "Customer Success / Onboarding",
    "Data Loss": "Tier-2 Engineering Support (Incident)",
}

SYSTEM_PROMPT = f"""You are a technical support triage assistant for an enterprise SaaS company.
Classify the incoming ticket and respond with STRICT JSON ONLY (no markdown fences, no prose)
matching this shape:

{{
  "product_area": "<module/component the issue relates to>",
  "issue_category": "<one of: {', '.join(VALID_CATEGORIES)}>",
  "urgency_tier": "<one of: {', '.join(VALID_URGENCY)}>",
  "reasoning": "<2-3 sentences explaining the classification>",
  "recommended_responder_team": "<team best suited to own this>",
  "draft_first_response": "<a professional, empathetic first-response message to send the customer, acknowledging the issue and setting expectations; do not invent facts not in the ticket>"
}}

Urgency guidance:
- P1: business-critical, production down, no workaround, or data loss affecting many users.
- P2: major functionality impaired, workaround exists but is costly.
- P3: moderate impact, workaround readily available.
- P4: cosmetic, low impact, or a how-to/feature-request with no urgency.
"""


def _build_user_prompt(ticket: TicketInput, kb_hits: list[dict]) -> str:
    kb_context = "\n".join(
        f"- [{h['doc_path']} > {h['heading']}] {h['excerpt']}" for h in kb_hits
    ) or "(no closely matching KB article found)"
    return f"""Ticket subject: {ticket.subject}

Ticket body:
{ticket.body}

Potentially relevant knowledge-base excerpts (may or may not be relevant — use judgement):
{kb_context}
"""


def _mock_classify(ticket: TicketInput) -> dict:
    """Deterministic keyword-based fallback used when LLM_PROVIDER=mock."""
    text = f"{ticket.subject} {ticket.body}".lower()
    # strip simple negations so "not urgent" / "no longer" don't trip positive keyword hits
    negated_text = re.sub(r"\b(not|no longer|isn't|isnt|n't)\s+(\w+\s+){0,2}urgent\b", "", text)

    if any(w in text for w in ["down", "outage", "critical", "data loss", "cannot access", "unable to login", "all users"]):
        urgency = "P1"
    elif any(w in negated_text for w in ["error", "failing", "timeout", "broken", "urgent"]):
        urgency = "P2"
    elif any(w in text for w in ["slow", "intermittent", "sometimes", "minor"]):
        urgency = "P3"
    else:
        urgency = "P4"

    # Feature-request phrasing is checked first: it's a strong, specific signal that
    # should win even if the ticket also mentions something being "slow" in passing.
    if any(w in text for w in ["would be great if", "feature request", "please add", "it would be great"]):
        category = "Feature Request"
    elif any(w in text for w in ["invoice", "billing", "charge", "payment", "renewal", "price"]):
        category = "Billing"
    elif any(w in text for w in ["integration", "salesforce", "snowflake", "webhook", "sso", "connector"]):
        category = "Integration"
    elif any(w in text for w in ["missing", "lost", "corrupted", "deleted", "data loss"]):
        category = "Data Loss"
    elif any(w in text for w in ["slow", "timeout", "latency", "performance", "lag"]):
        category = "Performance"
    elif any(w in text for w in ["how do i", "how to", "documentation", "guide"]):
        category = "How-To"
    elif any(w in text for w in ["onboarding", "setup", "new user", "getting started"]):
        category = "Onboarding"
    else:
        category = "Bug"

    product_area = ticket.subject.split()[0] if ticket.subject else "General"

    return {
        "product_area": product_area,
        "issue_category": category,
        "urgency_tier": urgency,
        "reasoning": f"Mock classifier: keyword match determined category='{category}', urgency='{urgency}' from subject/body text.",
        "recommended_responder_team": RESPONDER_TEAMS.get(category, "Tier-1 Support"),
        "draft_first_response": (
            f"Hi, thanks for reaching out. We've logged your report regarding "
            f"\"{ticket.subject}\" and it's been routed as a {urgency} {category} issue. "
            f"Our team will follow up shortly with next steps."
        ),
    }


def triage_ticket(ticket: TicketInput) -> TriageResult:
    query_text = f"{ticket.subject} {ticket.body}"
    kb_hits = kb_retrieval.search(query_text, top_k=3)

    result = llm_client.complete_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_user_prompt(ticket, kb_hits),
        temperature=0.2,
        mock_fn=lambda: _mock_classify(ticket),
    )

    # --- Guardrails: never trust raw LLM output blindly ---
    category = result.get("issue_category", "Bug")
    if category not in VALID_CATEGORIES:
        observability.log_event("triage.guardrail_fallback", field="issue_category",
                                 llm_value=str(category)[:100], fallback_value="Bug")
        category = "Bug"  # safe default; flagged via the logged event above
    urgency_raw = str(result.get("urgency_tier", "P3")).upper()
    urgency_match = re.match(r"P[1-4]", urgency_raw)
    urgency = urgency_match.group(0) if urgency_match else "P3"
    if not urgency_match:
        observability.log_event("triage.guardrail_fallback", field="urgency_tier",
                                 llm_value=urgency_raw[:100], fallback_value="P3")

    return TriageResult(
        product_area=result.get("product_area", "Unknown"),
        issue_category=category,
        urgency_tier=urgency,
        reasoning=result.get("reasoning", ""),
        kb_matches=[KBMatch(**h) for h in kb_hits],
        recommended_responder_team=result.get(
            "recommended_responder_team", RESPONDER_TEAMS.get(category, "Tier-1 Support")
        ),
        draft_first_response=result.get("draft_first_response", ""),
        prompt_version="triage_v1",
    )
