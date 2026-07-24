"""Groq LLM client — the qualitative half of the analysis.

Designed to degrade gracefully: if no API key is configured, or the call fails, the
API still returns a full deterministic report with `insights.enabled = false`.
"""

import json
import logging
import re

from .config import get_settings
from .prompts import SYSTEM_PROMPT, build_analysis_prompt

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)


class LlmError(RuntimeError):
    """Raised when the model call fails or returns unusable output."""


def _strip_fences(raw: str) -> str:
    """Models sometimes wrap JSON in markdown fences despite instructions."""
    cleaned = _FENCE_RE.sub("", raw.strip())
    # Fall back to the outermost {...} block if there is still stray prose.
    if not cleaned.startswith("{"):
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start : end + 1]
    return cleaned


def _coerce_str_list(value, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value[:limit]:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):  # model occasionally returns {"point": "..."}
            for v in item.values():
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())
                    break
    return out


def _coerce_bullets(value, limit: int = 5) -> list[dict]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value[:limit]:
        if not isinstance(item, dict):
            continue
        original = str(item.get("original", "")).strip()
        improved = str(item.get("improved", "")).strip()
        if not (original and improved):
            continue
        out.append(
            {
                "original": original,
                "improved": improved,
                "why": str(item.get("why", "")).strip() or "Stronger verb and clearer impact.",
            }
        )
    return out


def generate_insights(
    resume_text: str,
    jd_text: str,
    missing_keywords: list[str],
    matched_keywords: list[str],
    weak_bullets: list[str],
) -> dict:
    """Call Groq and normalise the response into the LlmInsights shape."""
    settings = get_settings()

    if not settings.llm_enabled:
        return {
            "enabled": False,
            "error": "No GROQ_API_KEY configured — showing rule-based analysis only. "
            "Add your key to .env and restart to enable AI insights.",
        }

    try:
        from groq import Groq
    except ImportError as exc:  # pragma: no cover - dependency is in requirements
        return {"enabled": False, "error": f"groq package not installed: {exc}"}

    prompt = build_analysis_prompt(
        resume_text, jd_text, missing_keywords, matched_keywords, weak_bullets
    )

    try:
        client = Groq(api_key=settings.groq_api_key, timeout=settings.groq_timeout)
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.groq_temperature,
            max_tokens=settings.groq_max_tokens,
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("Groq call failed: %s", exc)
        return {"enabled": False, "model": settings.groq_model, "error": f"Groq request failed: {exc}"}

    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as exc:
        logger.warning("Groq returned non-JSON output: %s", raw[:400])
        return {
            "enabled": False,
            "model": settings.groq_model,
            "error": f"Model returned malformed JSON: {exc}",
        }

    if not isinstance(data, dict):
        return {"enabled": False, "model": settings.groq_model, "error": "Model did not return an object."}

    return {
        "enabled": True,
        "model": settings.groq_model,
        "summary": str(data.get("summary", "")).strip() or None,
        "strengths": _coerce_str_list(data.get("strengths")),
        "gaps": _coerce_str_list(data.get("gaps")),
        "rewritten_bullets": _coerce_bullets(data.get("rewritten_bullets")),
        "tailored_summary": str(data.get("tailored_summary", "")).strip() or None,
        "interview_questions": _coerce_str_list(data.get("interview_questions")),
    }
