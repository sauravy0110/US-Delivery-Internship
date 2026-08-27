"""
Loads the mock dataset (tickets.json, accounts.json) and provides the
account<->ticket join described in DATA_SCHEMA.md, including graceful
handling of orphaned account_ids (documented as intentional in the schema).
"""
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

from app import config


@lru_cache(maxsize=1)
def load_tickets() -> list[dict]:
    with open(config.TICKETS_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_accounts() -> list[dict]:
    with open(config.ACCOUNTS_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def account_map() -> dict:
    return {a["account_id"]: a for a in load_accounts()}


def get_account(account_id: str) -> Optional[dict]:
    """Returns None (not an exception) for unknown accounts — callers must
    handle this explicitly, matching the schema's documented data gaps."""
    return account_map().get(account_id)


def get_account_tickets(account_id: str, days: int = 90) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for t in load_tickets():
        if t.get("account_id") != account_id:
            continue
        try:
            created = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if created > cutoff:
            out.append(t)
    return sorted(out, key=lambda t: t["created_at"], reverse=True)
