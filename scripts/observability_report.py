"""
Prints a quick observability summary from logs/events.jsonl:
call counts, failure counts, and p50/p95 latency per event type.

Run: python scripts/observability_report.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import observability

if __name__ == "__main__":
    summary = observability.summarize()
    if summary.get("total_events", 0) == 0:
        print("No events logged yet — run some triage/account-brief calls first.")
        sys.exit(0)

    print(f"Total events: {summary['total_events']}\n")
    print(f"{'event_type':<28} {'count':>6} {'failures':>9} {'p50 ms':>8} {'p95 ms':>8}")
    for event_type, stats in summary["by_event_type"].items():
        print(f"{event_type:<28} {stats['count']:>6} {stats['failures']:>9} "
              f"{str(stats['p50_latency_ms']):>8} {str(stats['p95_latency_ms']):>8}")
