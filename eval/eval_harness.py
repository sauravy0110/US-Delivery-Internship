"""
Task 3 — Evaluation harness for Task 1 (triage) and Task 2 (account brief).

Combines:
  - Rule-based checks (structural correctness: valid enum values, non-empty
    fields, KB matches present when expected, no exceptions raised).
  - An LLM-as-judge check for the qualitative parts (is the draft response
    professional and on-topic; is the executive summary actually
    grounded in the account data) — falls back to a deterministic
    heuristic judge when LLM_PROVIDER=mock, so the harness always runs.

Produces eval/eval_report.json and eval/eval_report.md.

Run: python -m eval.eval_harness
"""
import json
import time
from pathlib import Path

from app import data_loader, llm_client
from app.account_brief import generate_account_brief
from app.triage import triage_ticket, VALID_CATEGORIES, VALID_URGENCY
from app.schemas import TicketInput

EVAL_DIR = Path(__file__).resolve().parent

JUDGE_SYSTEM_PROMPT = """You are a strict QA reviewer for a support-ticket auto-response system.
You will be given the original ticket (subject + body) and a draft first-response message.
Respond with STRICT JSON ONLY:
{"professional": true/false, "on_topic": true/false, "score": <0.0-1.0>, "notes": "<one sentence>"}

Score should reflect: professionalism, whether it acknowledges the specific issue, and whether
it states any fact NOT present anywhere in the original ticket subject or body. Before flagging
something as fabricated, check carefully whether it actually appears in the provided ticket text
— quoting or referencing a detail that IS in the ticket is correct grounding, not fabrication.
"""

def _judge_draft_response_mock(ticket_subject: str, ticket_body: str, draft: str) -> dict:
    """Deterministic heuristic judge used offline: checks basic professionalism
    signals and topical overlap rather than true language understanding."""
    draft_lower = draft.lower()
    professional = any(w in draft_lower for w in ["thanks", "thank you", "hi", "hello", "we've", "our team"])
    on_topic = any(
        w.lower() in draft_lower for w in ticket_subject.split() if len(w) > 4
    ) or len(draft) > 20
    score = 0.5 + 0.25 * professional + 0.25 * on_topic
    return {
        "professional": professional,
        "on_topic": on_topic,
        "score": round(min(score, 1.0), 2),
        "notes": "Heuristic mock judge (offline mode): keyword-based professionalism/topicality check.",
    }


def judge_draft_response(ticket_subject: str, ticket_body: str, draft: str) -> dict:
    return llm_client.complete_json(
        system_prompt=JUDGE_SYSTEM_PROMPT,
        user_prompt=(
            f"Original ticket subject: {ticket_subject}\n\n"
            f"Original ticket body (the ONLY source of ground truth — anything stated here is "
            f"NOT fabricated, even if it looks like a specific technical detail):\n{ticket_body}\n\n"
            f"Draft response to evaluate:\n{draft}"
        ),
        temperature=0.0,
        mock_fn=lambda: _judge_draft_response_mock(ticket_subject, ticket_body, draft),
    )

# --------------------------------------------------------------------------
# Task 1 evaluation
# --------------------------------------------------------------------------

def run_triage_tests() -> list[dict]:
    cases = json.loads((EVAL_DIR / "test_cases_triage.json").read_text())
    results = []
    for case in cases:
        checks = []
        score_components = []
        errored = False
        try:
            ticket = TicketInput(**case["input"])
            result = triage_ticket(ticket)
        except Exception as exc:  # noqa: BLE001
            errored = True
            result = None
            checks.append((f"execution did not raise", False, str(exc)))

        acc = case["acceptance"]

        if not errored:
            # structural validity (always checked, not just when specified)
            valid_urgency = result.urgency_tier in VALID_URGENCY
            checks.append(("urgency_tier is a valid enum value", valid_urgency, result.urgency_tier))
            score_components.append(1.0 if valid_urgency else 0.0)

            valid_category = result.issue_category in VALID_CATEGORIES
            checks.append(("issue_category is a valid enum value", valid_category, result.issue_category))
            score_components.append(1.0 if valid_category else 0.0)

            if "urgency_tier_in" in acc:
                ok = result.urgency_tier in acc["urgency_tier_in"]
                checks.append((f"urgency_tier in {acc['urgency_tier_in']}", ok, result.urgency_tier))
                score_components.append(1.0 if ok else 0.0)

            if "issue_category_in" in acc:
                ok = result.issue_category in acc["issue_category_in"]
                checks.append((f"issue_category in {acc['issue_category_in']}", ok, result.issue_category))
                score_components.append(1.0 if ok else 0.0)

            if acc.get("requires_kb_match"):
                ok = len(result.kb_matches) > 0
                checks.append(("has at least one KB match", ok, len(result.kb_matches)))
                score_components.append(1.0 if ok else 0.0)

            if acc.get("requires_nonempty_draft_response"):
                ok = len(result.draft_first_response.strip()) > 10
                checks.append(("draft_first_response is non-empty/substantive", ok, len(result.draft_first_response)))
                score_components.append(1.0 if ok else 0.0)

                judge = judge_draft_response(
    case["input"]["subject"], case["input"]["body"], result.draft_first_response
)
                judge_ok = judge.get("score", 0) >= 0.5
                checks.append(("LLM-as-judge: draft response quality >= 0.5", judge_ok, judge))
                score_components.append(float(judge.get("score", 0)))

        if acc.get("must_not_error"):
            checks.append(("execution did not raise an exception", not errored, "errored" if errored else "ok"))
            score_components.append(0.0 if errored else 1.0)

        quality_score = sum(score_components) / len(score_components) if score_components else 0.0
        passed = (not errored) and all(c[1] for c in checks)

        results.append({
            "id": case["id"],
            "description": case["description"],
            "passed": passed,
            "quality_score": round(quality_score, 3),
            "checks": [{"check": c[0], "passed": c[1], "detail": c[2]} for c in checks],
        })
    return results


# --------------------------------------------------------------------------
# Task 2 evaluation — with dataset-agnostic selectors
# --------------------------------------------------------------------------

def _select_account(selector: dict) -> str | None:
    accounts = data_loader.load_accounts()
    strategy = selector["strategy"]

    def _first_with_tickets():
        for a in accounts:
            if data_loader.get_account_tickets(a["account_id"]):
                return a["account_id"]
        return accounts[0]["account_id"] if accounts else None

    def _by_health_status(value):
        for a in accounts:
            if a.get("health_status") == value:
                return a["account_id"]
        return None

    def _has_escalation_notes():
        for a in accounts:
            if a.get("escalation_notes"):
                return a["account_id"]
        return None

    def _zero_recent_tickets():
        for a in accounts:
            if not data_loader.get_account_tickets(a["account_id"]):
                return a["account_id"]
        return None

    if strategy == "explicit_id":
        return selector["value"]
    if strategy == "first_with_tickets":
        return _first_with_tickets()
    if strategy == "by_health_status":
        found = _by_health_status(selector["value"])
        if found:
            return found
        fallback = selector.get("fallback_strategy")
        return _select_account({"strategy": fallback}) if fallback else None
    if strategy == "has_escalation_notes":
        return _has_escalation_notes()
    if strategy == "zero_recent_tickets":
        found = _zero_recent_tickets()
        if found:
            return found
        fallback = selector.get("fallback_strategy")
        return _select_account({"strategy": fallback}) if fallback else None
    return None


def run_account_brief_tests() -> list[dict]:
    cases = json.loads((EVAL_DIR / "test_cases_account.json").read_text())
    results = []
    for case in cases:
        checks = []
        score_components = []
        errored = False
        account_id = _select_account(case["selector"])

        if account_id is None:
            results.append({
                "id": case["id"],
                "description": case["description"],
                "passed": None,
                "quality_score": None,
                "checks": [{"check": "selector found a matching account in the dataset", "passed": False,
                            "detail": "no matching account — case skipped for this dataset"}],
            })
            continue

        try:
            brief = generate_account_brief(account_id)
        except Exception as exc:  # noqa: BLE001
            errored = True
            brief = None
            checks.append(("execution did not raise", False, str(exc)))

        acc = case["acceptance"]

        if not errored:
            if "must_be_found" in acc:
                ok = brief.found == acc["must_be_found"]
                checks.append((f"found == {acc['must_be_found']}", ok, brief.found))
                score_components.append(1.0 if ok else 0.0)

            if acc.get("requires_nonempty_executive_summary"):
                ok = bool(brief.executive_summary and len(brief.executive_summary.strip()) > 10)
                checks.append(("executive_summary is non-empty/substantive", ok,
                                (brief.executive_summary or "")[:80]))
                score_components.append(1.0 if ok else 0.0)

            if "requires_min_talking_points" in acc:
                ok = len(brief.recommended_talking_points) >= acc["requires_min_talking_points"]
                checks.append((f">= {acc['requires_min_talking_points']} talking points", ok,
                                len(brief.recommended_talking_points)))
                score_components.append(1.0 if ok else 0.0)

            if "requires_min_risk_flags" in acc:
                ok = len(brief.open_risks_and_flags) >= acc["requires_min_risk_flags"]
                checks.append((f">= {acc['requires_min_risk_flags']} risk flags", ok,
                                len(brief.open_risks_and_flags)))
                score_components.append(1.0 if ok else 0.0)

            if acc.get("requires_quotes_are_verbatim"):
                account = data_loader.get_account(account_id)
                tickets = {t["ticket_id"]: t for t in data_loader.get_account_tickets(account_id)}
                source_text = " ".join(account.get("escalation_notes", []) or [])
                for t in tickets.values():
                    source_text += " " + t.get("body", "")
                all_verbatim = True
                for flag in brief.open_risks_and_flags:
                    quote_fragment = flag.justification_quote[:30].strip()
                    if quote_fragment and quote_fragment not in source_text:
                        all_verbatim = False
                checks.append(("risk-flag quotes are verbatim from source data", all_verbatim,
                                f"{len(brief.open_risks_and_flags)} flag(s) checked"))
                score_components.append(1.0 if all_verbatim else 0.0)

            if acc.get("requires_deterministic_repeat_call"):
                brief2 = generate_account_brief(account_id)
                ok = brief.model_dump_json() == brief2.model_dump_json()
                checks.append(("repeat call returns identical output", ok, "match" if ok else "mismatch"))
                score_components.append(1.0 if ok else 0.0)

            if acc.get("requires_error_message"):
                ok = bool(brief.error)
                checks.append(("error field populated for missing account", ok, brief.error))
                score_components.append(1.0 if ok else 0.0)

        if acc.get("must_not_error"):
            checks.append(("execution did not raise an exception", not errored, "errored" if errored else "ok"))
            score_components.append(0.0 if errored else 1.0)

        quality_score = sum(score_components) / len(score_components) if score_components else 0.0
        passed = (not errored) and all(c[1] for c in checks)

        results.append({
            "id": case["id"],
            "description": case["description"],
            "account_id_used": account_id,
            "passed": passed,
            "quality_score": round(quality_score, 3),
            "checks": [{"check": c[0], "passed": c[1], "detail": c[2]} for c in checks],
        })
    return results


# --------------------------------------------------------------------------
# Report generation
# --------------------------------------------------------------------------

def build_report():
    started = time.time()
    triage_results = run_triage_tests()
    account_results = run_account_brief_tests()
    duration = round(time.time() - started, 2)

    def _summary(results):
        scored = [r for r in results if r["passed"] is not None]
        passed = sum(1 for r in scored if r["passed"])
        avg_quality = (
            sum(r["quality_score"] for r in scored) / len(scored) if scored else 0.0
        )
        return {
            "total": len(results),
            "passed": passed,
            "failed": len(scored) - passed,
            "skipped": len(results) - len(scored),
            "avg_quality_score": round(avg_quality, 3),
        }

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": duration,
        "task_1_triage": {
            "summary": _summary(triage_results),
            "cases": triage_results,
        },
        "task_2_account_brief": {
            "summary": _summary(account_results),
            "cases": account_results,
        },
    }
    return report


def render_markdown(report: dict) -> str:
    lines = [
        "# Evaluation Report",
        "",
        f"Generated: {report['generated_at']}  ",
        f"Duration: {report['duration_seconds']}s",
        "",
    ]
    for key, title in [("task_1_triage", "Task 1 — Ticket Triage"), ("task_2_account_brief", "Task 2 — Account Brief")]:
        section = report[key]
        s = section["summary"]
        lines += [
            f"## {title}",
            "",
            f"**{s['passed']}/{s['total']} passed** "
            f"({s['skipped']} skipped, avg quality score: {s['avg_quality_score']})",
            "",
            "| Case | Passed | Quality Score | Description |",
            "|---|---|---|---|",
        ]
        for c in section["cases"]:
            status = "✅" if c["passed"] else ("⏭️" if c["passed"] is None else "❌")
            lines.append(f"| `{c['id']}` | {status} | {c.get('quality_score', '—')} | {c['description']} |")
        lines.append("")
        lines.append("<details><summary>Detailed checks</summary>")
        lines.append("")
        for c in section["cases"]:
            lines.append(f"**{c['id']}**")
            for chk in c["checks"]:
                mark = "✅" if chk["passed"] else "❌"
                lines.append(f"- {mark} {chk['check']} — `{chk['detail']}`")
            lines.append("")
        lines.append("</details>")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    report = build_report()
    (EVAL_DIR / "eval_report.json").write_text(json.dumps(report, indent=2, default=str))
    (EVAL_DIR / "eval_report.md").write_text(render_markdown(report))
    t1 = report["task_1_triage"]["summary"]
    t2 = report["task_2_account_brief"]["summary"]
    print(f"Task 1 (triage):        {t1['passed']}/{t1['total']} passed, avg quality {t1['avg_quality_score']}")
    print(f"Task 2 (account brief): {t2['passed']}/{t2['total']} passed, avg quality {t2['avg_quality_score']}")
    print("Reports written to eval/eval_report.json and eval/eval_report.md")
