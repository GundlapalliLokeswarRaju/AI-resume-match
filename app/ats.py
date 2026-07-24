"""ATS (Applicant Tracking System) readiness checks.

Each rule inspects the extracted resume text and returns pass / warn / fail with a
short, actionable explanation. Weights sum to the 0-100 ATS score.
"""

import re

from .nlp import ACTION_VERBS, tokenize

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
# Grouping varies by country (+91 98765 43210, (555) 123-4567, +1-555-123-4567),
# so match any digit/separator run and then verify the raw digit count.
PHONE_CANDIDATE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
URL_RE = re.compile(r"(?:linkedin\.com/in/|github\.com/)[\w-]+", re.I)
DATE_RE = re.compile(
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4}"
    r"|\b(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|present|current)"
    r"|\b\d{1,2}/(?:19|20)\d{2}",
    re.I,
)
QUANTIFIED_RE = re.compile(r"\d+\s*(?:%|percent|x\b|k\b|m\b|million|billion|users|hours|days)|\$\s?\d")
BULLET_RE = re.compile(r"^\s*[•▪◦‣·*\-–—]\s+(.+)$", re.M)

SECTION_KEYWORDS = {
    "experience": ("experience", "employment", "work history", "professional background"),
    "education": ("education", "academic", "qualification", "degree", "university", "b.tech", "bachelor"),
    "skills": ("skills", "technical skills", "technologies", "competencies", "tech stack"),
}


def _check(cid: str, label: str, status: str, detail: str, weight: float) -> dict:
    return {"id": cid, "label": label, "status": status, "detail": detail, "weight": weight}


def _has_phone(text: str) -> bool:
    """A phone number is a digit run of 10-15 digits once separators are stripped."""
    for candidate in PHONE_CANDIDATE_RE.findall(text):
        if 10 <= sum(c.isdigit() for c in candidate) <= 15:
            return True
    return False


def run_checks(text: str) -> dict:
    """Run every ATS rule and fold the results into a 0-100 score."""
    lower = text.lower()
    words = tokenize(text)
    word_count = len(words)
    bullets = [b.strip() for b in BULLET_RE.findall(text)]
    checks: list[dict] = []

    # --- Contact details -------------------------------------------------
    has_email = bool(EMAIL_RE.search(text))
    has_phone = _has_phone(text)
    if has_email and has_phone:
        checks.append(_check("contact", "Contact information", "pass",
                             "Email and phone number are both detectable.", 10))
    elif has_email or has_phone:
        found, absent = ("email", "phone number") if has_email else ("phone number", "email")
        checks.append(_check("contact", "Contact information", "warn",
                             f"Found your {found} but no {absent}. Recruiters filter on both.", 10))
    else:
        checks.append(_check("contact", "Contact information", "fail",
                             "No email or phone detected — parsers will drop your application.", 10))

    # --- Online profiles -------------------------------------------------
    profiles = {m.split(".com/")[0].lower() for m in URL_RE.findall(text)}
    if len(profiles) >= 2:
        checks.append(_check("profiles", "LinkedIn & GitHub links", "pass",
                             "Both a LinkedIn and a GitHub/portfolio link are present.", 6))
    elif profiles:
        checks.append(_check("profiles", "LinkedIn & GitHub links", "warn",
                             "Only one profile link found — add the other to strengthen credibility.", 6))
    else:
        checks.append(_check("profiles", "LinkedIn & GitHub links", "fail",
                             "No LinkedIn or GitHub link found. Add both near your contact details.", 6))

    # --- Standard sections -----------------------------------------------
    present = [name for name, kws in SECTION_KEYWORDS.items() if any(k in lower for k in kws)]
    absent = [name for name in SECTION_KEYWORDS if name not in present]
    if not absent:
        checks.append(_check("sections", "Standard section headings", "pass",
                             "Experience, Education and Skills sections all detected.", 14))
    elif len(absent) == 1:
        checks.append(_check("sections", "Standard section headings", "warn",
                             f"Missing a clear '{absent[0].title()}' heading.", 14))
    else:
        checks.append(_check("sections", "Standard section headings", "fail",
                             f"Missing headings: {', '.join(s.title() for s in absent)}. "
                             "ATS parsers segment resumes by these exact words.", 14))

    # --- Dates -----------------------------------------------------------
    date_hits = len(DATE_RE.findall(text))
    if date_hits >= 2:
        checks.append(_check("dates", "Employment dates", "pass",
                             f"{date_hits} date ranges found in a parseable format.", 10))
    elif date_hits == 1:
        checks.append(_check("dates", "Employment dates", "warn",
                             "Only one date range detected. Date every role and project.", 10))
    else:
        checks.append(_check("dates", "Employment dates", "fail",
                             "No dates found. Use a 'Mar 2023 – Present' style for every role.", 10))

    # --- Bullet points ---------------------------------------------------
    if len(bullets) >= 8:
        checks.append(_check("bullets", "Bullet-point formatting", "pass",
                             f"{len(bullets)} bullets — good scannable structure.", 10))
    elif len(bullets) >= 3:
        checks.append(_check("bullets", "Bullet-point formatting", "warn",
                             f"Only {len(bullets)} bullets. Aim for 3-5 per role.", 10))
    else:
        checks.append(_check("bullets", "Bullet-point formatting", "fail",
                             "Almost no bullet points. Dense paragraphs get skimmed past.", 10))

    # --- Action verbs ----------------------------------------------------
    verb_hits = sum(1 for w in words if w in ACTION_VERBS)
    if verb_hits >= 8:
        checks.append(_check("verbs", "Strong action verbs", "pass",
                             f"{verb_hits} strong action verbs (led, built, optimized...).", 12))
    elif verb_hits >= 4:
        checks.append(_check("verbs", "Strong action verbs", "warn",
                             f"Only {verb_hits} action verbs. Open every bullet with one.", 12))
    else:
        checks.append(_check("verbs", "Strong action verbs", "fail",
                             "Very few action verbs. Replace 'responsible for' with 'led', 'built', 'shipped'.", 12))

    # --- Quantified impact -----------------------------------------------
    quantified = len(QUANTIFIED_RE.findall(text))
    if quantified >= 5:
        checks.append(_check("metrics", "Quantified achievements", "pass",
                             f"{quantified} measurable results found.", 16))
    elif quantified >= 2:
        checks.append(_check("metrics", "Quantified achievements", "warn",
                             f"Only {quantified} quantified results. Numbers are the #1 differentiator.", 16))
    else:
        checks.append(_check("metrics", "Quantified achievements", "fail",
                             "No metrics detected. Add %, time saved, scale or revenue to each bullet.", 16))

    # --- Length ----------------------------------------------------------
    if 350 <= word_count <= 900:
        checks.append(_check("length", "Resume length", "pass",
                             f"{word_count} words — right in the one-page/two-page sweet spot.", 10))
    elif word_count < 350:
        checks.append(_check("length", "Resume length", "warn",
                             f"Only {word_count} words. Thin resumes read as inexperienced.", 10))
    else:
        checks.append(_check("length", "Resume length", "warn",
                             f"{word_count} words is long. Trim to the most relevant 2 pages.", 10))

    # --- Parse hygiene ---------------------------------------------------
    weird_ratio = sum(1 for c in text if ord(c) > 0x2500) / max(len(text), 1)
    if weird_ratio > 0.01:
        checks.append(_check("hygiene", "Parse cleanliness", "warn",
                             "Lots of icon/glyph characters — these often come from graphics-heavy "
                             "templates that ATS parsers mangle.", 12))
    else:
        checks.append(_check("hygiene", "Parse cleanliness", "pass",
                             "Text extracted cleanly with no parsing artefacts.", 12))

    points = {"pass": 1.0, "warn": 0.55, "fail": 0.0}
    earned = sum(c["weight"] * points[c["status"]] for c in checks)
    total = sum(c["weight"] for c in checks)
    score = round(earned / total * 100, 1) if total else 0.0

    return {"score": score, "checks": checks, "bullets": bullets, "word_count": word_count}
