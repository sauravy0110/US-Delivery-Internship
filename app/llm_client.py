"""
LLM client wrapper — provider-agnostic.

Groq, OpenAI, and Gemini are all reachable through the same OpenAI
chat-completions wire format (Gemini and Groq both expose an
OpenAI-compatible endpoint), so ONE HTTP call path serves all three real
providers; only base_url / api_key / default model differ (see
app.config.PROVIDER_CONFIGS). Switching providers is therefore a pure .env
change, never a code change.

A fourth provider, "mock", is a fully offline, deterministic, rule-based
stand-in — used by the eval harness / CI so it never depends on an API key
or network access, and by reviewers who want to sanity-check the pipeline
instantly.

Every call is wrapped in app.observability.log_call so latency, provider,
and JSON-parse failures are captured for the observability report.
"""
import json
import os
import re
import time
from typing import Optional

from app import config, observability


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    """Best-effort extraction of a JSON object from an LLM response, tolerant
    of markdown code fences and leading/trailing prose."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text.strip()).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise LLMError(f"Could not parse JSON from LLM response:\n{text[:500]}")


def _call_openai_compatible(provider: str, system_prompt: str, user_prompt: str,
                             temperature: float, seed: int) -> str:
    cfg = config.PROVIDER_CONFIGS[provider]
    api_key = os.getenv(cfg["api_key_env"], "")
    if not api_key or api_key.strip() in ("", "your_groq_api_key_here",
                                           "your_openai_api_key_here", "your_gemini_api_key_here"):
        raise LLMError(
            f"{cfg['api_key_env']} is not set. Add a valid key to .env, "
            f"or set LLM_PROVIDER=mock to run offline."
        )
    expected_prefixes = {"groq": "gsk_", "openai": "sk-", "gemini": "AIza"}
    prefix = expected_prefixes.get(provider)
    if prefix and not api_key.startswith(prefix):
        raise LLMError(
            f"{cfg['api_key_env']} does not match the expected format for {provider} "
            f"(should start with '{prefix}'). Verify the key was copied from the correct "
            f"provider's dashboard."
        )
    from openai import OpenAI, RateLimitError  # imported lazily so `mock` mode needs no network deps

    client = OpenAI(api_key=api_key, base_url=cfg["base_url"])
    model = config.LLM_MODEL if config.LLM_MODEL else cfg["default_model"]

    kwargs = dict(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    if cfg.get("supports_json_mode"):
        kwargs["response_format"] = {"type": "json_object"}
    if provider != "gemini":  # Gemini's OpenAI-compat layer doesn't support `seed`
        kwargs["seed"] = seed

    max_retries = 4
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content
        except RateLimitError as exc:
            if attempt == max_retries - 1:
                raise
            # Respect the provider's suggested retry delay when present (Groq includes
            # "try again in Xs" in the response body); otherwise back off exponentially.
            wait_seconds = 2 ** attempt
            body_text = ""
            try:
                body_text = exc.response.text
            except Exception:  # noqa: BLE001
                body_text = str(exc.body) if getattr(exc, "body", None) else str(exc)
            match = re.search(r"try again in ([\d.]+)s", body_text)
            if match:
                wait_seconds = float(match.group(1)) + 0.5
            observability.log_event("llm.rate_limited_retry", provider=provider,
                                     attempt=attempt + 1, wait_seconds=wait_seconds)
            time.sleep(wait_seconds)


def _mock_complete(system_prompt: str, user_prompt: str) -> str:
    return json.dumps({"_mock": True, "note": "No mock_fn supplied for this call."})


def complete_json(
    system_prompt: str,
    user_prompt: str,
    temperature: Optional[float] = None,
    seed: Optional[int] = None,
    mock_fn=None,
) -> dict:
    """Call the configured LLM provider and return a parsed JSON dict.

    mock_fn: optional zero-arg callable returning a dict, used when
    LLM_PROVIDER=mock. Each task module supplies its own deterministic
    heuristic so mock mode still exercises real pipeline logic (KB
    retrieval, prompt assembly, schema validation) end-to-end.
    """
    temperature = config.LLM_TEMPERATURE if temperature is None else temperature
    seed = config.LLM_SEED if seed is None else seed
    provider = config.LLM_PROVIDER

    with observability.log_call("llm.complete_json", provider=provider) as ev:
        if provider == "mock":
            if mock_fn is not None:
                result = mock_fn()
            else:
                result = _extract_json(_mock_complete(system_prompt, user_prompt))
            ev["mode"] = "mock"
            return result

        if provider in config.PROVIDER_CONFIGS:
            raw = _call_openai_compatible(provider, system_prompt, user_prompt, temperature, seed)
            try:
                result = _extract_json(raw)
            except LLMError:
                ev["json_parse_failed"] = True
                raise
            ev["mode"] = "live"
            return result

        raise LLMError(
            f"Unknown LLM_PROVIDER '{provider}' "
            f"(expected one of {list(config.PROVIDER_CONFIGS)} or 'mock')."
        )
