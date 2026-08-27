"""
Task 2 — TAM account health summariser.

Given an account_id, pulls the account record + last-90-days tickets and
produces a 3-section brief: executive summary, open risks/flagged issues
(each justified with a direct quote), and recommended talking points.

Determinism: temperature=0 + fixed seed reduces (but on most providers does
not perfectly guarantee) sampling variance. On top of that we memoise on a
hash of the exact inputs, so repeated calls with the same account+ticket
snapshot return a byte-identical cached result within a process — see
Task 4 design note for the full discussion of why we don't rely on
temperature=0 alone.
"""
import hashlib
import json
from functools import lru_cache

from app import data_loader, llm_client
from app.schemas import AccountBrief, RiskFlag

SYSTEM_PROMPT = """You are a TAM (Technical Account Manager) assistant. Given a customer
account's profile and its recent support tickets, produce STRICT JSON ONLY (no markdown
fences, no prose) matching this shape:

{
  "executive_summary": "<3-5 sentences summarising overall account health, usage, and trajectory>",
  "open_risks_and_flags": [
    {"ticket_id": "<id or null>", "signal": "<short description of the risk, e.g. 'champion departure'>", "justification_quote": "<a short direct quote (<25 words) from the ticket body or escalation_notes that supports this flag>"}
  ],
  "recommended_talking_points": ["<point 1>", "<point 2>", "..."]
}

Rules:
- Every entry in open_risks_and_flags MUST include a justification_quote copied verbatim
  from the provided ticket text or escalation_notes — never fabricate a quote.
- If there is no genuine risk signal, return an empty open_risks_and_flags list. Do not
  invent risk to pad the output.
- Base every claim only on the data provided below. Do not assume facts not present.
"""


def _account_input_hash(account: dict, tickets: list[dict]) -> str:
    payload = json.dumps({"account": account, "tickets": tickets}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _build_user_prompt(account: dict, tickets: list[dict]) -> str:
    ticket_lines = []
    for t in tickets:
        ticket_lines.append(
            f"- [{t['ticket_id']}] ({t.get('urgency')}, {t.get('category')}, {t.get('status')}) "
            f"{t.get('subject')}\n  Body: {t.get('body', '')[:500]}"
        )
    tickets_block = "\n".join(ticket_lines) or "(no tickets in the last 90 days)"

    return f"""Account profile:
{json.dumps(account, indent=2, default=str)}

Tickets from the last 90 days ({len(tickets)} total):
{tickets_block}
"""


def _mock_brief(account: dict, tickets: list[dict]) -> dict:
    """Deterministic rule-based fallback for LLM_PROVIDER=mock."""
    flags = []
    for note in account.get("escalation_notes", []) or []:
        low = note.lower()
        if any(w in low for w in ["churn", "competitor", "cancel", "frustrat", "left the company", "evaluat"]):
            flags.append({
                "ticket_id": None,
                "signal": "escalation note risk signal",
                "justification_quote": note[:150],
            })
    for t in tickets:
        if t.get("urgency") == "P1":
            flags.append({
                "ticket_id": t["ticket_id"],
                "signal": "unresolved P1 ticket" if t.get("status") not in ("Resolved", "Closed") else "recent P1 incident",
                "justification_quote": (t.get("body", "")[:150] or t.get("subject", "")),
            })

    health = account.get("health_status", "Unknown")
    trend = account.get("usage_trend", "Unknown")
    summary = (
        f"{account.get('company', 'This account')} is currently marked '{health}' with a "
        f"'{trend}' usage trend across {len(account.get('products', []))} product(s). "
        f"There are {len(tickets)} ticket(s) in the last 90 days "
        f"({account.get('p1_tickets_last_30d', 0)} P1 in the last 30 days). "
        f"NPS score: {account.get('nps_score', 'N/A')}."
    )

    talking_points = [
        f"Review renewal timeline (renewal_date: {account.get('renewal_date', 'unknown')}).",
        f"Discuss usage trend ('{trend}') and adoption of licensed vs active seats "
        f"({account.get('seats_active', '?')}/{account.get('seats_licensed', '?')}).",
    ]
    if flags:
        talking_points.append("Address open risk signals below before they escalate further.")

    return {
        "executive_summary": summary,
        "open_risks_and_flags": flags,
        "recommended_talking_points": talking_points,
    }


@lru_cache(maxsize=256)
def _generate_cached(account_id: str, input_hash: str, account_json: str, tickets_json: str) -> str:
    """Cached on exact input content, not just account_id, so a stale cache
    entry can never mask a genuine data change."""
    account = json.loads(account_json)
    tickets = json.loads(tickets_json)

    result = llm_client.complete_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=_build_user_prompt(account, tickets),
        temperature=0.0,
        mock_fn=lambda: _mock_brief(account, tickets),
    )
    return json.dumps(result)


def generate_account_brief(account_id: str) -> AccountBrief:
    account = data_loader.get_account(account_id)
    if account is None:
        return AccountBrief(
            account_id=account_id,
            company="Unknown",
            found=False,
            tickets_considered=0,
            prompt_version="account_brief_v1",
            error=f"No account found with account_id='{account_id}'. "
                  f"Ticket/account_id references without a matching account are a known, "
                  f"documented data gap — handled gracefully rather than raising.",
        )

    tickets = data_loader.get_account_tickets(account_id, days=90)

    account_json = json.dumps(account, sort_keys=True, default=str)
    tickets_json = json.dumps(tickets, sort_keys=True, default=str)
    input_hash = _account_input_hash(account, tickets)

    raw = _generate_cached(account_id, input_hash, account_json, tickets_json)
    result = json.loads(raw)

    return AccountBrief(
        account_id=account_id,
        company=account.get("company", "Unknown"),
        found=True,
        executive_summary=result.get("executive_summary", ""),
        open_risks_and_flags=[RiskFlag(**f) for f in result.get("open_risks_and_flags", [])],
        recommended_talking_points=result.get("recommended_talking_points", []),
        tickets_considered=len(tickets),
        prompt_version="account_brief_v1",
    )
