"""ResuMatch AI — FastAPI service that scores a resume against a job description.

Run locally:
    uvicorn main:app --reload
Then open http://127.0.0.1:8000
"""

import logging
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import ats, llm, nlp, scoring
from app.config import get_settings
from app.extractor import ExtractionError, extract_text
from app.ratelimit import SlidingWindowLimiter, make_dependency
from app.schemas import AnalyzeResponse, HealthResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("resumatch")

settings = get_settings()
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="ResuMatch AI",
    version=settings.version,
    description=(
        "AI-powered resume analyzer. Upload a resume and paste a job description to get an "
        "ATS readiness score, weighted keyword-gap analysis, and LLM-generated rewrites "
        "powered by Groq.\n\n"
        "**Endpoints:** `POST /api/analyze` (file upload) · `POST /api/analyze-text` (JSON/form text)"
    ),
    contact={"name": "ResuMatch AI"},
    license_info={"name": "MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Every analysis spends Groq quota, so meter the two endpoints that call the model.
limiter = SlidingWindowLimiter(
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)
rate_limit = Depends(make_dependency(limiter))


# --------------------------------------------------------------------------- #
# Core analysis pipeline
# --------------------------------------------------------------------------- #
def _analyze(resume_text: str, jd_text: str, filename: str | None) -> AnalyzeResponse:
    started = time.perf_counter()

    resume_text = resume_text[: settings.max_resume_chars]
    jd_text = jd_text[: settings.max_jd_chars]

    # 1. Deterministic layer — always runs, always free.
    jd_keywords = nlp.extract_jd_keywords(jd_text)
    keyword_result = nlp.match_keywords(resume_text, jd_keywords)
    ats_result = ats.run_checks(resume_text)
    exp_score, _exp_note = scoring.experience_signal(resume_text, jd_text)
    score = scoring.combine(keyword_result["coverage"], ats_result["score"], exp_score)

    # 2. LLM layer — optional, degrades to a message if the key is absent.
    weak_bullets = scoring.pick_weak_bullets(ats_result["bullets"])
    insights = llm.generate_insights(
        resume_text=resume_text,
        jd_text=jd_text,
        missing_keywords=[k["keyword"] for k in keyword_result["missing"]],
        matched_keywords=[k["keyword"] for k in keyword_result["matched"]],
        weak_bullets=weak_bullets,
    )

    return AnalyzeResponse(
        filename=filename,
        resume_chars=len(resume_text),
        job_title_guess=nlp.guess_job_title(jd_text),
        score=score,
        keywords=keyword_result,
        ats={"score": ats_result["score"], "checks": ats_result["checks"]},
        insights=insights,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


def _validate_jd(job_description: str) -> str:
    jd = (job_description or "").strip()
    if len(jd) < 50:
        raise HTTPException(
            status_code=422,
            detail="Job description is too short — paste at least a few sentences (50+ characters).",
        )
    return jd


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
async def index():
    page = STATIC_DIR / "index.html"
    if page.exists():
        return FileResponse(page)
    return JSONResponse({"message": "ResuMatch AI is running. See /docs for the API."})


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
async def health():
    """Liveness probe plus whether the Groq key is wired up."""
    return HealthResponse(
        status="ok",
        version=settings.version,
        llm_enabled=settings.llm_enabled,
        model=settings.groq_model,
    )


@app.post(
    "/api/analyze",
    response_model=AnalyzeResponse,
    tags=["analysis"],
    dependencies=[rate_limit],
)
async def analyze_file(
    resume: UploadFile = File(..., description="Resume file: PDF, DOCX, TXT or MD"),
    job_description: str = Form(..., description="Full job description text"),
):
    """Analyze an uploaded resume file against a job description."""
    jd = _validate_jd(job_description)

    data = await resume.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Limit is {settings.max_upload_bytes // (1024 * 1024)} MB.",
        )

    try:
        resume_text = extract_text(resume.filename or "", data)
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    logger.info("Analyzing %s (%d chars) against JD (%d chars)", resume.filename, len(resume_text), len(jd))
    return _analyze(resume_text, jd, resume.filename)


@app.post(
    "/api/analyze-text",
    response_model=AnalyzeResponse,
    tags=["analysis"],
    dependencies=[rate_limit],
)
async def analyze_text(
    resume_text: str = Form(..., description="Resume as plain text"),
    job_description: str = Form(..., description="Full job description text"),
):
    """Analyze pasted resume text — handy for scanned PDFs and quick API testing."""
    jd = _validate_jd(job_description)
    text = (resume_text or "").strip()
    if len(text) < 100:
        raise HTTPException(status_code=422, detail="Resume text is too short (100+ characters needed).")
    return _analyze(text, jd, None)
