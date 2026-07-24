"""Pydantic request/response models — these drive the auto-generated OpenAPI docs."""

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["pass", "warn", "fail"]


class KeywordHit(BaseModel):
    keyword: str
    in_resume: bool
    resume_count: int = 0
    importance: float = Field(..., description="0-1 weight derived from the job description")


class KeywordAnalysis(BaseModel):
    matched: list[KeywordHit]
    missing: list[KeywordHit]
    coverage: float = Field(..., description="Weighted share of JD keywords present in the resume (0-100)")


class AtsCheck(BaseModel):
    id: str
    label: str
    status: Severity
    detail: str
    weight: float


class AtsReport(BaseModel):
    score: float = Field(..., description="0-100 ATS-friendliness score")
    checks: list[AtsCheck]


class ScoreBreakdown(BaseModel):
    keyword_match: float
    ats_readiness: float
    experience_signal: float
    overall: float
    verdict: str
    band: Literal["strong", "moderate", "weak"]


class BulletRewrite(BaseModel):
    original: str
    improved: str
    why: str


class LlmInsights(BaseModel):
    enabled: bool
    model: str | None = None
    summary: str | None = None
    strengths: list[str] = []
    gaps: list[str] = []
    rewritten_bullets: list[BulletRewrite] = []
    tailored_summary: str | None = None
    interview_questions: list[str] = []
    error: str | None = None


class AnalyzeResponse(BaseModel):
    filename: str | None = None
    resume_chars: int
    job_title_guess: str | None = None
    score: ScoreBreakdown
    keywords: KeywordAnalysis
    ats: AtsReport
    insights: LlmInsights
    elapsed_ms: int


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_enabled: bool
    model: str
