"""Test suite for ResuMatch AI.

The LLM layer is monkeypatched so the suite runs offline, deterministically and
without spending Groq credits.
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402
from app import ats, nlp, scoring  # noqa: E402
from app.extractor import ExtractionError, extract_text  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_data"
RESUME = (SAMPLE_DIR / "sample_resume.txt").read_text(encoding="utf-8")
JD = (SAMPLE_DIR / "sample_job_description.txt").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    """Keep every test offline — no real Groq calls."""
    monkeypatch.setattr(
        main.llm,
        "generate_insights",
        lambda **kwargs: {"enabled": False, "error": "stubbed in tests"},
    )


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Every test shares the TestClient's IP, so clear the window between tests."""
    main.limiter._hits.clear()
    yield
    main.limiter._hits.clear()


@pytest.fixture
def client():
    return TestClient(main.app)


# --------------------------------------------------------------------------- #
# Health & docs
# --------------------------------------------------------------------------- #
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "model" in body


def test_openapi_schema_builds(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/api/analyze" in r.json()["paths"]


def test_index_serves_ui(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "ResuMatch" in r.text


# --------------------------------------------------------------------------- #
# Keyword extraction & matching
# --------------------------------------------------------------------------- #
def test_extract_jd_keywords_finds_core_skills():
    keywords = dict(nlp.extract_jd_keywords(JD))
    for expected in ("python", "fastapi", "aws", "docker"):
        assert expected in keywords, f"{expected} should be extracted from the JD"
    assert all(0 <= v <= 1 for v in keywords.values())


def test_aliases_collapse_to_one_canonical_term():
    assert nlp.canonical("k8s") == "kubernetes"
    assert nlp.canonical("golang") == "go"
    assert nlp.canonical("LLMs") == "llm"


def test_match_keywords_splits_matched_and_missing():
    kws = nlp.extract_jd_keywords(JD)
    result = nlp.match_keywords(RESUME, kws)

    matched = {k["keyword"] for k in result["matched"]}
    missing = {k["keyword"] for k in result["missing"]}

    assert "python" in matched          # resume clearly has it
    assert "kubernetes" in missing      # resume clearly lacks it
    assert not (matched & missing)      # a term is never in both
    assert 0 <= result["coverage"] <= 100


def test_empty_jd_yields_no_keywords():
    assert nlp.extract_jd_keywords("") == []


def test_keyword_extraction_is_deterministic_across_hash_seeds():
    """SKILL_VOCAB is a set — unsorted traversal + score ties would make the
    top-N cut depend on PYTHONHASHSEED, so identical input could score differently."""
    import json
    import subprocess

    snippet = (
        "import json,sys;sys.path.insert(0,'.');"
        "from app import nlp;"
        f"print(json.dumps(nlp.extract_jd_keywords({JD!r})))"
    )
    root = Path(__file__).resolve().parents[1]
    outputs = set()
    for seed in ("0", "1", "42"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        proc = subprocess.run(
            [sys.executable, "-c", snippet], cwd=root, env=env,
            capture_output=True, text=True, check=True,
        )
        outputs.add(json.dumps(json.loads(proc.stdout)))

    assert len(outputs) == 1, "keyword extraction differs between hash seeds"


# --------------------------------------------------------------------------- #
# ATS checks
# --------------------------------------------------------------------------- #
def test_ats_detects_good_resume():
    report = ats.run_checks(RESUME)
    by_id = {c["id"]: c for c in report["checks"]}

    assert by_id["contact"]["status"] == "pass"      # email + phone present
    assert by_id["profiles"]["status"] == "pass"     # linkedin + github present
    assert by_id["sections"]["status"] == "pass"     # experience/education/skills
    assert by_id["metrics"]["status"] == "pass"      # plenty of %s and numbers
    assert report["score"] > 70
    assert len(report["bullets"]) >= 8


def test_ats_flags_a_bad_resume():
    bad = "I am a hard worker looking for a job. " * 20
    report = ats.run_checks(bad)
    by_id = {c["id"]: c for c in report["checks"]}

    assert by_id["contact"]["status"] == "fail"
    assert by_id["metrics"]["status"] == "fail"
    assert report["score"] < 40


def test_ats_score_is_bounded():
    for text in (RESUME, "short text " * 30, ""):
        score = ats.run_checks(text)["score"]
        assert 0 <= score <= 100


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def test_combine_weights_and_bands():
    perfect = scoring.combine(100, 100, 100)
    assert perfect["overall"] == 100
    assert perfect["band"] == "strong"

    zero = scoring.combine(0, 0, 0)
    assert zero["overall"] == 0
    assert zero["band"] == "weak"

    # 50/30/20 weighting
    assert scoring.combine(100, 0, 0)["overall"] == 50
    assert scoring.combine(0, 100, 0)["overall"] == 30
    assert scoring.combine(0, 0, 100)["overall"] == 20


def test_experience_signal_penalises_shortfall():
    junior = "Software Engineer 2023 - Present. One year of experience."
    senior_jd = "We need 8+ years of experience as a Principal Engineer."
    score, _ = scoring.experience_signal(junior, senior_jd)
    assert score < 70


def test_experience_signal_counts_present_as_today():
    """'2019 – Present' must count up to the current year, not the last printed year."""
    resume = "Software Engineer, Acme Corp. Jan 2019 - Present. Built backend services."
    jd = "Looking for an engineer with 5+ years of experience."
    score, note = scoring.experience_signal(resume, jd)
    assert score >= 78, f"open-ended tenure should satisfy the bar, got {score} ({note})"


def test_experience_signal_prefers_stated_years():
    resume = "Backend engineer with 7 years of experience. Worked 2023 - 2024 at Acme."
    jd = "We need 6+ years of experience."
    score, _ = scoring.experience_signal(resume, jd)
    assert score >= 90


def test_pick_weak_bullets_ranks_vague_ones_first():
    bullets = [
        "Reduced pipeline runtime by 45% using Spark and Airflow orchestration",
        "Responsible for maintaining the internal reporting dashboards daily",
    ]
    ranked = scoring.pick_weak_bullets(bullets)
    assert ranked[0].startswith("Responsible for")


# --------------------------------------------------------------------------- #
# Extractor
# --------------------------------------------------------------------------- #
def test_extract_txt_roundtrip():
    text = extract_text("resume.txt", RESUME.encode("utf-8"))
    assert "PRIYA SHARMA" in text


def test_extract_rejects_unknown_extension():
    with pytest.raises(ExtractionError, match="Unsupported file type"):
        extract_text("resume.pages", b"x" * 500)


def test_extract_rejects_empty_file():
    with pytest.raises(ExtractionError, match="empty"):
        extract_text("resume.txt", b"")


def test_extract_rejects_near_empty_text():
    with pytest.raises(ExtractionError, match="almost no text"):
        extract_text("resume.txt", b"too short")


# --------------------------------------------------------------------------- #
# API endpoints
# --------------------------------------------------------------------------- #
def test_analyze_text_happy_path(client):
    r = client.post("/api/analyze-text", data={"resume_text": RESUME, "job_description": JD})
    assert r.status_code == 200

    body = r.json()
    assert 0 <= body["score"]["overall"] <= 100
    assert body["score"]["band"] in {"strong", "moderate", "weak"}
    assert body["keywords"]["matched"]
    assert len(body["ats"]["checks"]) == 9
    assert body["insights"]["enabled"] is False  # stubbed
    assert body["job_title_guess"] == "Senior AI/ML Engineer"


def test_analyze_file_upload(client):
    files = {"resume": ("resume.txt", RESUME.encode("utf-8"), "text/plain")}
    r = client.post("/api/analyze", files=files, data={"job_description": JD})
    assert r.status_code == 200
    assert r.json()["filename"] == "resume.txt"


def test_analyze_rejects_short_job_description(client):
    r = client.post("/api/analyze-text", data={"resume_text": RESUME, "job_description": "dev"})
    assert r.status_code == 422
    assert "too short" in r.json()["detail"]


def test_analyze_rejects_short_resume(client):
    r = client.post("/api/analyze-text", data={"resume_text": "hi", "job_description": JD})
    assert r.status_code == 422


def test_analyze_rejects_bad_file_type(client):
    files = {"resume": ("resume.pages", b"x" * 500, "application/octet-stream")}
    r = client.post("/api/analyze", files=files, data={"job_description": JD})
    assert r.status_code == 422


def test_rate_limiter_allows_then_blocks():
    from app.ratelimit import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60)
    assert all(limiter.check("1.2.3.4")[0] for _ in range(3))

    allowed, retry_after = limiter.check("1.2.3.4")
    assert allowed is False
    assert retry_after > 0

    # Buckets are per-key, so one visitor cannot exhaust another's allowance.
    assert limiter.check("5.6.7.8")[0] is True


def test_rate_limited_endpoint_returns_429(monkeypatch, client):
    monkeypatch.setattr(main.limiter, "max_requests", 2)
    monkeypatch.setattr(main.limiter, "window", 60)
    main.limiter._hits.clear()

    payload = {"resume_text": RESUME, "job_description": JD}
    assert client.post("/api/analyze-text", data=payload).status_code == 200
    assert client.post("/api/analyze-text", data=payload).status_code == 200

    blocked = client.post("/api/analyze-text", data=payload)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers

    main.limiter._hits.clear()


def test_analyze_rejects_oversized_upload(client):
    big = b"x" * (main.settings.max_upload_bytes + 1)
    files = {"resume": ("resume.txt", big, "text/plain")}
    r = client.post("/api/analyze", files=files, data={"job_description": JD})
    assert r.status_code == 413
