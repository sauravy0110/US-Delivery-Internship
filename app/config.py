"""
Central configuration. All values are read from environment variables so
that no credentials or environment-specific values are ever hard-coded.
See .env.example for the full list of supported variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
KB_DIR = BASE_DIR / "knowledge-base"

TICKETS_PATH = DATA_DIR / "tickets.json"
ACCOUNTS_PATH = DATA_DIR / "accounts.json"

# "groq" | "openai" | "gemini" (all free-tier-friendly, OpenAI-compatible) | "mock" (offline, deterministic)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_SEED = int(os.getenv("LLM_SEED", "42"))

# All three real providers speak the OpenAI chat-completions wire format, so a single
# HTTP client implementation in llm_client.py serves all of them — only the base_url,
# api_key, and default model name differ. This makes the provider a pure config swap.
PROVIDER_CONFIGS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "default_model": "openai/gpt-oss-120b",
        "supports_json_mode": True,
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "supports_json_mode": True,
    },
    "gemini": {
        # Gemini's OpenAI-compatibility layer
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "default_model": "gemini-2.0-flash",
        "supports_json_mode": True,
    },
}

# Retained for any code/tests that still reference these directly.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = PROVIDER_CONFIGS["groq"]["base_url"]

# KB retrieval backend: "embeddings" (SentenceTransformers + FAISS, preferred) with an
# automatic, logged fallback to "tfidf" if the embedding model can't be loaded.
KB_RETRIEVAL_MODE = os.getenv("KB_RETRIEVAL_MODE", "embeddings").lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Observability: structured JSONL event log (latency, provider, success/fallback) for
# every LLM call and every retrieval-backend decision. See app/observability.py.
LOG_DIR = BASE_DIR / "logs"
EVENTS_LOG_PATH = LOG_DIR / "events.jsonl"

# Prompt version identifiers (bonus: prompt versioning + changelog).
# Bump these whenever prompt wording changes and add a line to CHANGELOG below.
PROMPT_VERSIONS = {
    "triage_v1": "2026-08-26 — initial triage classification + draft-response prompt",
    "account_brief_v1": "2026-08-26 — initial 3-section account brief prompt with quote-justified risk flags",
}
