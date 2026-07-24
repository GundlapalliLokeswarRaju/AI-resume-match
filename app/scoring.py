"""Combine keyword coverage, ATS readiness and experience signals into one score."""

import re
from datetime import date

SENIORITY_PATTERNS = {
    "intern": 0, "trainee": 0, "fresher": 0,
    "junior": 1, "associate": 1,
    "mid": 2, "engineer ii": 2,
    "senior": 3, "sr.": 3, "lead": 4, "staff": 4, "principal": 5, "head of": 5, "director": 5,
}

YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)", re.I)


def _years_required(jd_text: str) -> int | None:
    hits = [int(m) for m in YEARS_RE.findall(jd_text) if int(m) <= 25]
    return min(hits) if hits else None


def _years_evidenced(resume_text: str) -> int | None:
    """Estimate total experience, preferring an explicit claim over a date span."""
    # A stated "4 years of experience" is more reliable than inferring from dates.
    stated = [int(m) for m in YEARS_RE.findall(resume_text) if int(m) <= 40]
    if stated:
        return max(stated)

    years = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-4]\d)\b", resume_text)]
    years = [y for y in years if 1985 <= y <= 2035]
    if not years:
        return None

    # "2022 – Present" means the role runs to today, not to the last printed year.
    end = max(years)
    if re.search(r"\b(present|current|now|ongoing|till date)\b", resume_text, re.I):
        end = max(end, date.today().year)

    span = end - min(years)
    return span if 0 <= span <= 40 else None


def experience_signal(resume_text: str, jd_text: str) -> tuple[float, str]:
    """Score 0-100 for how well seniority/tenure lines up with the JD."""
    score = 70.0
    notes = []

    required = _years_required(jd_text)
    evidenced = _years_evidenced(resume_text)

    if required is not None and evidenced is not None:
        if evidenced >= required:
            score = 95.0
            notes.append(f"~{evidenced}y of history vs. {required}y required")
        elif evidenced >= required - 1:
            score = 78.0
            notes.append(f"~{evidenced}y vs. {required}y required — borderline but arguable")
        else:
            score = max(35.0, 70.0 - (required - evidenced) * 10)
            notes.append(f"~{evidenced}y vs. {required}y required — under the bar")
    elif required is not None:
        notes.append(f"JD asks for {required}y; no clear date range found in the resume")
        score = 60.0
    else:
        notes.append("No explicit years-of-experience requirement in the JD")

    jd_low, resume_low = jd_text.lower(), resume_text.lower()
    jd_level = max((v for k, v in SENIORITY_PATTERNS.items() if k in jd_low), default=None)
    resume_level = max((v for k, v in SENIORITY_PATTERNS.items() if k in resume_low), default=None)

    if jd_level is not None and resume_level is not None:
        delta = resume_level - jd_level
        if delta >= 0:
            score = min(100.0, score + 5)
        elif delta <= -2:
            score = max(30.0, score - 15)
            notes.append("resume reads more junior than the target title")

    return round(score, 1), "; ".join(notes)


def combine(keyword_coverage: float, ats_score: float, exp_score: float) -> dict:
    """Weighted blend. Keyword match dominates because that is what recruiters filter on."""
    overall = keyword_coverage * 0.50 + ats_score * 0.30 + exp_score * 0.20
    overall = round(overall, 1)

    if overall >= 75:
        band, verdict = "strong", "Strong match — apply, and lead with your relevant wins."
    elif overall >= 55:
        band, verdict = "moderate", "Moderate match — worth applying after you close the gaps below."
    else:
        band, verdict = "weak", "Weak match — significant rework needed before this application lands."

    return {
        "keyword_match": round(keyword_coverage, 1),
        "ats_readiness": round(ats_score, 1),
        "experience_signal": round(exp_score, 1),
        "overall": overall,
        "verdict": verdict,
        "band": band,
    }


def pick_weak_bullets(bullets: list[str], limit: int = 12) -> list[str]:
    """Rank bullets worst-first so the LLM spends its rewrites where they matter."""
    from .nlp import ACTION_VERBS

    def weakness(b: str) -> float:
        score = 0.0
        words = b.lower().split()
        if not words:
            return 99.0
        if words[0].rstrip(",.") not in ACTION_VERBS:
            score += 2.0
        if not re.search(r"\d", b):
            score += 2.5
        if re.search(r"responsible for|worked on|helped with|involved in|duties includ", b, re.I):
            score += 3.0
        if len(words) < 8:
            score += 1.0
        return score

    return [b for b in sorted(bullets, key=weakness, reverse=True) if len(b.split()) >= 4][:limit]
