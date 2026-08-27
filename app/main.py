"""
FastAPI app exposing:
  POST /triage            — Task 1: ticket triage
  GET  /account-brief/{id} — Task 2: TAM account health brief
  GET  /health             — liveness check

Run with: uvicorn app.main:app --reload
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.schemas import TicketInput, TriageResult, AccountBrief
from app.triage import triage_ticket
from app.account_brief import generate_account_brief

app = FastAPI(
    title="US Delivery Internal AI Tools",
    description="Ticket triage agent + TAM account health summariser (internal tooling)",
    version="1.0.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResult)
def triage_endpoint(ticket: TicketInput):
    try:
        return triage_ticket(ticket)
    except Exception as exc:  # noqa: BLE001 — surfaced deliberately to the caller
        raise HTTPException(status_code=500, detail=f"Triage failed: {exc}") from exc


@app.get("/account-brief/{account_id}", response_model=AccountBrief)
def account_brief_endpoint(account_id: str):
    brief = generate_account_brief(account_id)
    if not brief.found:
        return JSONResponse(status_code=404, content=brief.model_dump())
    return brief
