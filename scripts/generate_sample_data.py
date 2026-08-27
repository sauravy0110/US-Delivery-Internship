"""
Generates a sample dataset (data/tickets.json, data/accounts.json) matching
DATA_SCHEMA.md, for local development and testing.

Run: python scripts/generate_sample_data.py
"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(7)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

COMPANIES = [
    "Initech", "Globex", "Umbrella Corp", "Soylent Inc", "Hooli",
    "Stark Industries", "Wayne Enterprises", "Wonka Industries",
    "Cyberdyne Systems", "Aperture Labs",
]
PRODUCTS = ["DataBridge Pro", "CloudSync", "AnalyticsHub", "SecureVault", "WorkflowEngine"]
PRODUCT_AREAS = {
    "DataBridge Pro": ["Connectors", "Sync Engine", "Data Mapping"],
    "CloudSync": ["File Sync", "Backup", "Conflict Resolution"],
    "AnalyticsHub": ["Dashboards", "Reporting API", "Data Export"],
    "SecureVault": ["Access Control", "Encryption", "Audit Logs"],
    "WorkflowEngine": ["Automation Rules", "Approvals", "Triggers"],
}
CATEGORIES = ["Bug", "Feature Request", "How-To", "Performance", "Billing", "Integration", "Onboarding", "Data Loss"]
URGENCY_WEIGHTS = [("P1", 0.05), ("P2", 0.20), ("P3", 0.45), ("P4", 0.30)]
STATUSES = ["Open", "In Progress", "Pending Customer", "Resolved", "Closed"]
PLAN_TIERS = ["Starter", "Professional", "Business", "Enterprise"]
CHANNELS = ["email", "portal", "chat", "phone"]
AGENTS = ["Sarah Chen", "Marcus Lee", "Priya Nair", "Diego Alvarez", "Emma Fischer"]
TAMS = ["Olivia Grant", "James Whitfield", "Anika Sharma", "Tomás Rivera"]
REGIONS = ["US-East", "US-West", "US-Central", "EU-West", "APAC"]
INDUSTRIES = ["Financial Services", "Healthcare", "Retail", "Manufacturing", "Technology",
              "Media", "Education", "Government", "Logistics", "Energy"]
HEALTH_STATUSES = ["Healthy", "At Risk", "Churning", "New"]
USAGE_TRENDS = ["Increasing", "Stable", "Declining", "Inactive"]

BODY_TEMPLATES = {
    "Bug": "We're seeing {product} throw an unexpected error in {area}. Error: '{err}'. "
           "This started around {when} and is affecting {n} users. Environment: Production.",
    "Performance": "{product} has been very slow in the {area} module for the last {when}. "
                    "Page loads/reports that used to take seconds now take minutes, affecting {n} users.",
    "Integration": "Our {area} integration in {product} stopped syncing with our downstream system {when}. "
                    "No error shown in the UI but data is stale.",
    "Billing": "We noticed a discrepancy on our latest invoice for {product}. Could someone confirm "
               "our seat count and plan tier ({plan})?",
    "How-To": "Could you point us to documentation on how to configure {area} in {product}? "
              "We can't find it in the current docs.",
    "Feature Request": "It would be great if {product} supported bulk actions in {area}. "
                        "Our team of {n} does this manually today.",
    "Onboarding": "We're a new customer setting up {product}. Could someone walk us through "
                  "initial {area} configuration?",
    "Data Loss": "We believe we've lost records in {area} within {product} after {when}. "
                 "This is critical — please advise urgently.",
}

ERRORS = ["ERR_CONNECTION_TIMEOUT after 30s", "ERR_AUTH_TOKEN_EXPIRED", "ERR_SYNC_CONFLICT_422",
          "ERR_RATE_LIMIT_EXCEEDED", "ERR_SCHEMA_MISMATCH"]
WHENS = ["yesterday morning", "the last 48 hours", "since the last release", "this week", "since Monday"]

ESCALATION_NOTE_POOL = [
    "Customer expressed frustration with response times in last sync",
    "Decision maker considering competing vendor evaluation",
    "Champion left the company — no replacement identified yet",
    "Executive sponsor requested a call to discuss renewal concerns",
    "Positive feedback on latest feature release",
    "Requested case study collaboration — strong advocate",
    "Flagged repeated P1s as a trust issue heading into renewal",
]


def weighted_choice(pairs):
    items, weights = zip(*pairs)
    return random.choices(items, weights=weights, k=1)[0]


def gen_accounts(n=12):
    accounts = []
    for i in range(n):
        acc_id = f"ACC-{3000 + i}"
        health = random.choice(HEALTH_STATUSES)
        accounts.append({
            "account_id": acc_id,
            "company": COMPANIES[i % len(COMPANIES)],
            "tam": random.choice(TAMS),
            "plan_tier": random.choice(PLAN_TIERS),
            "arr_usd": random.choice([36000, 60000, 120000, 240000, 480000]),
            "seats_licensed": (s := random.choice([25, 50, 150, 350])),
            "seats_active": int(s * random.uniform(0.4, 0.95)),
            "products": random.sample(PRODUCTS, k=random.randint(1, 3)),
            "health_status": health,
            "usage_trend": random.choice(USAGE_TRENDS),
            "open_tickets": random.randint(0, 8),
            "p1_tickets_last_30d": random.randint(0, 3),
            "customer_since": (datetime(2021, 1, 1) + timedelta(days=random.randint(0, 1200))).strftime("%Y-%m-%d"),
            "renewal_date": (datetime(2026, 9, 1) + timedelta(days=random.randint(0, 300))).strftime("%Y-%m-%d"),
            "last_qbr_date": (datetime(2026, 5, 1) + timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%d"),
            "primary_contact": {"name": "Alex Morgan", "title": "VP Engineering"},
            "escalation_notes": random.sample(ESCALATION_NOTE_POOL, k=random.randint(0, 3)),
            "nps_score": random.choice([None, 2, 4, 6, 7, 8, 9]),
            "last_login_days_ago": random.randint(0, 45),
            "integrations_active": random.sample(["Salesforce", "Snowflake", "Slack", "Jira", "Workday"], k=random.randint(0, 3)),
            "region": random.choice(REGIONS),
            "industry": random.choice(INDUSTRIES),
        })
    return accounts


def gen_tickets(accounts, n=60):
    tickets = []
    now = datetime(2026, 8, 26, tzinfo=timezone.utc)
    for i in range(n):
        product = random.choice(PRODUCTS)
        area = random.choice(PRODUCT_AREAS[product])
        category = random.choice(CATEGORIES)
        urgency = weighted_choice(URGENCY_WEIGHTS)
        # ~85% of tickets reference a real account; rest are intentionally orphaned
        account = random.choice(accounts) if random.random() < 0.85 else None
        created = now - timedelta(days=random.randint(0, 120), hours=random.randint(0, 23))
        body = BODY_TEMPLATES.get(category, BODY_TEMPLATES["Bug"]).format(
            product=product, area=area, err=random.choice(ERRORS),
            when=random.choice(WHENS), n=random.randint(3, 80),
            plan=random.choice(PLAN_TIERS),
        )
        tickets.append({
            "ticket_id": f"TKT-{10000 + i}",
            "account_id": account["account_id"] if account else f"ACC-{9000 + i}",
            "company": account["company"] if account else "Unknown Co",
            "subject": f"{category}: {area} issue in {product}",
            "body": body,
            "product": product,
            "product_area": area,
            "category": category,
            "urgency": urgency,
            "status": random.choice(STATUSES),
            "plan_tier": account["plan_tier"] if account else random.choice(PLAN_TIERS),
            "assigned_agent": random.choice(AGENTS),
            "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updated_at": (created + timedelta(hours=random.randint(1, 72))).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tags": [product.lower().replace(" ", "-"), area.lower().replace(" ", "-"), urgency.lower()],
            "channel": random.choice(CHANNELS),
            "satisfaction_score": random.choice([None, None, 1, 2, 3, 4, 5]),
        })
    return tickets


if __name__ == "__main__":
    accounts = gen_accounts()
    tickets = gen_tickets(accounts)
    (DATA_DIR / "accounts.json").write_text(json.dumps(accounts, indent=2))
    (DATA_DIR / "tickets.json").write_text(json.dumps(tickets, indent=2))
    print(f"Wrote {len(accounts)} sample accounts and {len(tickets)} sample tickets to {DATA_DIR}")
