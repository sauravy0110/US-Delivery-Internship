# US Delivery Internal AI Tools

Internal AI tooling for a SaaS support organization.

This project implements:

1. Ticket Triage Agent
2. TAM (Technical Account Manager) Account Brief Generator

Built as part of the US Delivery Intern technical assessment.

---

## Features

### Ticket Triage Agent

Given a support ticket, the system:

- Classifies product area
- Identifies issue category
- Assigns urgency (P1–P4)
- Retrieves relevant knowledge-base articles using RAG
- Recommends the responder team
- Generates a draft customer response

### TAM Account Brief Generator

Given an account ID, the system:

- Summarizes account health
- Highlights risks and escalation signals
- Produces evidence-backed risk flags
- Generates recommended talking points
- Handles missing account records gracefully

---

## Tech Stack

- FastAPI
- Groq LLM API
- SentenceTransformers
- FAISS
- Scikit-learn (TF-IDF fallback)
- Pydantic

---

## Project Structure

```text
app/
├── main.py
├── triage.py
├── account_brief.py
├── kb_retrieval.py
├── llm_client.py
├── data_loader.py
├── schemas.py
├── config.py
└── observability.py

data/
knowledge-base/
eval/
logs/
```

---

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create environment file:

```bash
cp .env.example .env
```

Fill in your Groq API key:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

---

## Sample Run — Task 1 (Ticket Triage)

Request:

```json
{
  "ticket_id": "TKT-10000",
  "subject": "Request: bulk archive entries in DataBridge Pro Data Ingestion",
  "body": "Currently DataBridge Pro only allows individual archive entries in the Data Ingestion module. As our usage has scaled to 116 users we urgently need bulk operations."
}
```

Response:

```json
{
  "product_area": "DataBridge Pro - Data Ingestion",
  "issue_category": "Feature Request",
  "urgency_tier": "P3",
  "recommended_responder_team": "DataBridge Pro Product Management"
}
```

---

## Sample Run — Task 2 (Account Brief)

Request:

```http
GET /account-brief/ACC-3336
```

Response:

```json
{
  "account_id": "ACC-3336",
  "company": "Omni Consumer Products",
  "found": true,
  "tickets_considered": 0
}
```

Key account details from dataset:

```json
{
  "health_status": "At Risk",
  "usage_trend": "Inactive",
  "arr_usd": 500000,
  "open_tickets": 7
}
```

---

## Evaluation

Run:

```bash
python -m eval.eval_harness
```

Latest results:

```text
Task 1 — Ticket Triage: 6/6 passed
Task 2 — Account Brief: 6/6 passed

Overall: 12/12 passed
```

Evaluation reports are included in:

```text
eval/eval_report.md
eval/eval_report.json
```

---

## Design Decisions

### Retrieval

- Primary backend: SentenceTransformers + FAISS
- Automatic fallback to TF-IDF if embeddings are unavailable
- Backend selection is logged through observability events

### Account Briefs

- Deterministic outputs for evaluation consistency
- Evidence-backed risk flags only
- Graceful handling of missing account records

### LLM Layer

- Provider abstraction through environment variables
- Supports Groq, OpenAI, Gemini, and Mock providers
- No application code changes required when switching providers

### Observability

Structured JSONL logs capture:

- LLM latency
- Retrieval backend usage
- Failures and exceptions
- Request-level telemetry

---

## API Endpoints

### Health Check

```http
GET /health
```

### Ticket Triage

```http
POST /triage
```

### Account Brief

```http
GET /account-brief/{account_id}
```

---

## Notes

- Uses only the provided assessment datasets.
- No external customer data is accessed.
- Secrets are loaded from environment variables and are never committed to source control.