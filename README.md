# ResuMatch AI — Resume × Job Description Analyzer

An AI-powered resume analyzer built with **FastAPI** and **Groq**. Upload a resume, paste a
job description, and get an explainable match score, an ATS compliance report, a weighted
keyword-gap analysis, and LLM-generated bullet rewrites.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-F55036)
![Tests](https://img.shields.io/badge/tests-28_passing-35d07f)
![License](https://img.shields.io/badge/license-MIT-blue)

**🔗 Live demo:** [fastapi-5464a195.fastapicloud.dev](https://fastapi-5464a195.fastapicloud.dev) ·
[interactive API docs](https://fastapi-5464a195.fastapicloud.dev/docs)

> The public demo is rate-limited to 10 analyses per 10 minutes per IP to protect the shared
> API quota. Clone and run locally with your own key for unlimited use.

---

## Why this exists

Roughly three out of four resumes are filtered by an Applicant Tracking System before a
human reads them. Most rejections are mechanical: a missing keyword, an unparseable layout,
no dates, no numbers. ResuMatch AI scores a resume the way that pipeline does — and then
uses an LLM to explain, in specifics, what to change.

## Architecture

The analysis runs in two independent layers, which is the core design decision:

```
                    ┌──────────────────────────────────────────┐
  PDF / DOCX / TXT  │  extractor.py   pypdf · python-docx      │
  ────────────────► │  text normalisation, table extraction    │
                    └────────────────────┬─────────────────────┘
                                         │
                ┌────────────────────────┴───────────────────────┐
                │                                                │
    ┌───────────▼────────────┐                     ┌─────────────▼─────────────┐
    │  DETERMINISTIC LAYER   │                     │       LLM LAYER           │
    │  free · instant · 100% │                     │  Groq · LLaMA 3.3 70B     │
    │  reproducible          │                     │                           │
    │                        │                     │  • fit summary            │
    │  nlp.py    keyword     │                     │  • strengths / gaps       │
    │            extraction  │  ── pre-analysis ─► │  • bullet rewrites        │
    │  ats.py    9 ATS rules │     feeds prompt    │  • tailored summary       │
    │  scoring.py  blending  │                     │  • interview questions    │
    └───────────┬────────────┘                     └─────────────┬─────────────┘
                │                                                │
                └────────────────────┬───────────────────────────┘
                                     ▼
                          AnalyzeResponse (Pydantic)
```

**The deterministic layer never depends on the LLM.** If the Groq key is missing, rate-limited
or the model returns malformed JSON, the API still returns a complete scored report with
`insights.enabled = false`. That is what makes the service testable offline and safe to demo.

### Score composition

| Component | Weight | What it measures |
|---|---|---|
| Keyword match | 50% | Weighted coverage of skills the JD actually emphasises |
| ATS readiness | 30% | 9 parseability and structure rules |
| Experience signal | 20% | Years and seniority alignment vs. the posting |

Keyword importance is **not** a flat list — terms are scored by frequency in the JD, boosted
3× when they appear in a curated skill vocabulary, and collapsed through an alias table so
`K8s`/`Kubernetes` and `LLMs`/`LLM` count once.

---

## Quick start

```bash
git clone <your-repo-url>
cd fastapi
pip install -r requirements.txt

cp .env.example .env      # then paste your Groq key into .env
uvicorn main:app --reload
```

Open **http://127.0.0.1:8000** for the UI, or **/docs** for interactive Swagger docs.

Get a free Groq API key at [console.groq.com/keys](https://console.groq.com/keys).
Without a key the app still runs — you get the full rule-based report and a notice where the
AI insights would be.

---

## API

### `POST /api/analyze`
Multipart upload.

| Field | Type | Notes |
|---|---|---|
| `resume` | file | PDF, DOCX, TXT or MD — max 5 MB |
| `job_description` | string | 50+ characters |

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -F "resume=@sample_data/sample_resume.txt" \
  -F "job_description=$(cat sample_data/sample_job_description.txt)"
```

### `POST /api/analyze-text`
Same analysis from pasted text — useful for scanned PDFs.

```bash
curl -X POST http://127.0.0.1:8000/api/analyze-text \
  -F "resume_text=..." -F "job_description=..."
```

### `GET /api/health`
Liveness plus whether the Groq key is wired up.

<details>
<summary><b>Sample response</b></summary>

```json
{
  "filename": "sample_resume.txt",
  "job_title_guess": "Senior AI/ML Engineer",
  "score": {
    "keyword_match": 61.3,
    "ats_readiness": 88.6,
    "experience_signal": 78.0,
    "overall": 72.8,
    "verdict": "Moderate match — worth applying after you close the gaps below.",
    "band": "moderate"
  },
  "keywords": {
    "matched": [{ "keyword": "python", "in_resume": true, "resume_count": 4, "importance": 1.0 }],
    "missing": [{ "keyword": "kubernetes", "in_resume": false, "importance": 0.71 }],
    "coverage": 61.3
  },
  "ats": {
    "score": 88.6,
    "checks": [
      { "id": "metrics", "label": "Quantified achievements", "status": "pass",
        "detail": "7 measurable results found.", "weight": 16 }
    ]
  },
  "insights": {
    "enabled": true,
    "model": "llama-3.3-70b-versatile",
    "rewritten_bullets": [
      { "original": "Responsible for the team's PostgreSQL schema design",
        "improved": "Owned PostgreSQL schema design and query optimization, cutting p95 query time by [X%]",
        "why": "Replaces a passive phrase with ownership language and an impact metric." }
    ]
  },
  "elapsed_ms": 1840
}
```
</details>

---

## ATS rules

| Rule | Weight | Fails when |
|---|---|---|
| Contact information | 10 | No email or phone (international formats supported) |
| LinkedIn & GitHub links | 6 | Neither profile URL present |
| Standard section headings | 14 | Experience / Education / Skills missing |
| Employment dates | 10 | No parseable date ranges |
| Bullet-point formatting | 10 | Fewer than 3 bullets |
| Strong action verbs | 12 | Fewer than 4 verbs from a 35-verb list |
| Quantified achievements | 16 | No %, $, scale or time metrics |
| Resume length | 10 | Outside the 350–900 word band |
| Parse cleanliness | 12 | Heavy glyph/icon usage from graphic templates |

---

## Testing

```bash
pytest -q
```

28 tests covering keyword extraction, alias collapsing, hash-seed determinism, every ATS rule,
score-weight maths, file-extraction failure modes, per-IP rate limiting, and all API endpoints
including 413/422/429 error paths. The Groq call is monkeypatched, so the suite runs
**offline and free**.

```
28 passed in 3.30s
```

---

## Deployment

Deployed on [FastAPI Cloud](https://fastapicloud.com):

```bash
fastapi cloud login
fastapi cloud env set GROQ_API_KEY <your-key> --secret   # never baked into the image
fastapi deploy
```

The Groq key is stored as a **cloud secret**, not committed and not shipped in the build.
`pyproject.toml` pins the entrypoint (`main:app`) and the package set so the build is
reproducible.

## Project layout

```
fastapi/
├── main.py                 FastAPI app, routes, pipeline orchestration
├── app/
│   ├── config.py           Pydantic settings from .env
│   ├── schemas.py          Response models → drives OpenAPI docs
│   ├── extractor.py        PDF / DOCX / TXT → clean text
│   ├── nlp.py              Keyword extraction, alias table, matching
│   ├── ats.py              9 weighted ATS rules
│   ├── scoring.py          Score blending, weak-bullet ranking
│   ├── prompts.py          System prompt + JSON schema contract
│   ├── llm.py              Groq client, response normalisation
│   └── ratelimit.py        Per-IP sliding-window limiter
├── static/                 Single-page UI (vanilla JS, no build step)
├── tests/test_api.py       28 tests
├── pyproject.toml          Entrypoint + build config for FastAPI Cloud
└── sample_data/            Ready-to-use resume + job description
```

## Tech stack

**FastAPI** · **Pydantic v2** · **Groq (LLaMA 3.3 70B)** · **pypdf** · **python-docx** ·
**pytest** · vanilla JS front-end with zero build step.

## License

MIT
