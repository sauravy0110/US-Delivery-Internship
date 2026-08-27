"""
Prints the list of models actually available to your Groq API key right now.
Groq deprecates/renames models periodically, so this is more reliable than
trusting a hardcoded model string in this (or any) codebase.

Run: python scripts/list_groq_models.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import requests

api_key = os.getenv("GROQ_API_KEY", "")
if not api_key:
    print("GROQ_API_KEY is not set in .env — nothing to check.")
    sys.exit(1)

resp = requests.get(
    "https://api.groq.com/openai/v1/models",
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=15,
)
if resp.status_code != 200:
    print(f"Request failed ({resp.status_code}): {resp.text}")
    sys.exit(1)

models = resp.json().get("data", [])
print(f"{len(models)} model(s) available to this key:\n")
for m in sorted(models, key=lambda x: x.get("id", "")):
    print(f"  {m.get('id')}")

print("\nSet LLM_MODEL in .env to any id above.")
