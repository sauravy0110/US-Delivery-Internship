"""
Minimal observability layer: every LLM call and every retrieval-backend
decision is written as one JSON line to logs/events.jsonl. Deliberately not
a full tracing/metrics stack (Prometheus, OpenTelemetry, etc.) — for an
internal tool at this scale that would be overengineering; a queryable
append-only event log is enough to answer the questions that actually
matter in production: how often are we falling back to a default, what's
p50/p95 latency, how often does the LLM return unparseable JSON.

Usage:
    with log_call("triage.llm_call", prompt_version="triage_v1") as ev:
        ev["provider"] = "groq"
        ... do the work ...
        ev["success"] = True

`summarize()` gives a quick aggregate view (see scripts/observability_report.py).
"""
import json
import time
import traceback
from contextlib import contextmanager
from pathlib import Path

from app import config

config.LOG_DIR.mkdir(exist_ok=True)


def _write(event: dict):
    event["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(config.EVENTS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")


@contextmanager
def log_call(event_type: str, **fields):
    """Context manager: times the wrapped block and logs one event on exit,
    including the exception if one was raised (re-raised afterward — this
    logger observes, it never swallows errors)."""
    event = {"event_type": event_type, "success": True, **fields}
    start = time.time()
    try:
        yield event
    except Exception as exc:  # noqa: BLE001
        event["success"] = False
        event["error"] = str(exc)
        event["traceback"] = traceback.format_exc(limit=3)
        raise
    finally:
        event["latency_ms"] = round((time.time() - start) * 1000, 1)
        _write(event)


def log_event(event_type: str, **fields):
    """One-shot event log for things that aren't naturally a timed block
    (e.g. a guardrail fallback substitution)."""
    _write({"event_type": event_type, **fields})


def read_events() -> list[dict]:
    if not config.EVENTS_LOG_PATH.exists():
        return []
    events = []
    for line in config.EVENTS_LOG_PATH.read_text().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def summarize() -> dict:
    events = read_events()
    if not events:
        return {"total_events": 0}

    by_type: dict = {}
    for e in events:
        t = e["event_type"]
        by_type.setdefault(t, {"count": 0, "failures": 0, "latencies_ms": []})
        by_type[t]["count"] += 1
        if e.get("success") is False:
            by_type[t]["failures"] += 1
        if "latency_ms" in e:
            by_type[t]["latencies_ms"].append(e["latency_ms"])

    summary = {"total_events": len(events), "by_event_type": {}}
    for t, stats in by_type.items():
        lat = sorted(stats["latencies_ms"])
        p50 = lat[len(lat) // 2] if lat else None
        p95 = lat[int(len(lat) * 0.95)] if lat else None
        summary["by_event_type"][t] = {
            "count": stats["count"],
            "failures": stats["failures"],
            "p50_latency_ms": p50,
            "p95_latency_ms": p95,
        }
    return summary
