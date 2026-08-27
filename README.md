# US Delivery Internal AI Tools

Internal AI tooling for a SaaS support organization.

This project implements two workflows:

1. Ticket Triage Agent
2. TAM (Technical Account Manager) Account Brief Generator

Built as part of the US Delivery Intern technical assessment.

---

## Features

### Ticket Triage Agent

Given a support ticket, the system:

- Classifies the product area
- Identifies the issue category
- Assigns an urgency tier (P1–P4)
- Retrieves relevant knowledge-base content using RAG
- Recommends the appropriate responder team
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
- Groq API
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
ui/
```

---

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local environment file:

```bash
cp .env.example .env
```

Configure your API key:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_api_key
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
  "health_status": "At Risk",
  "usage_trend": "Inactive",
  "arr_usd": 500000,
  "open_tickets": 7
}
```

---

## Evaluation

Run the evaluation harness:

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

- SentenceTransformers embeddings with FAISS vector search
- Automatic TF-IDF fallback when embeddings are unavailable
- Retrieval backend selection is logged through observability events

### Account Briefs

- Deterministic outputs for evaluation consistency
- Evidence-backed risk identification
- Graceful handling of unknown account IDs

### LLM Layer

- Provider abstraction through environment variables
- Supports Groq, OpenAI, Gemini, and Mock providers
- No code changes required when switching providers

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

## Loom Walkthrough

Loom video: _Add link before submission_

---

## Notes

- Uses only the provided assessment datasets.
- No external customer data is accessed.
- Secrets are loaded from environment variables and are never committed to source control.
- Required environment variables are documented in `.env.example`.
- Evaluation outputs are included in `eval/eval_report.md` and `eval/eval_report.json`.
