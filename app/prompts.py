"""Prompt construction for the Groq-hosted LLM pass."""

SYSTEM_PROMPT = """You are a senior technical recruiter and resume coach with 15 years of \
experience hiring for software, data and AI roles. You give blunt, specific, actionable feedback \
— never generic filler like "tailor your resume" or "highlight your skills".

Rules:
- Every claim you make must reference something concrete from the resume or job description.
- Rewritten bullets must follow: strong action verb + what was built + technology + measurable result.
- If the resume has no metric for a bullet, invent a clearly-marked placeholder like "[X%]" rather \
than a fabricated number.
- Never invent experience, employers, or credentials the candidate does not have.

Respond with ONLY a valid JSON object. No markdown fences, no commentary before or after."""

RESPONSE_SCHEMA = """{
  "summary": "2-3 sentence verdict on this candidate's fit for this specific role",
  "strengths": ["3-5 specific strengths, each tied to evidence in the resume"],
  "gaps": ["3-5 specific gaps vs. the job description, most important first"],
  "rewritten_bullets": [
    {
      "original": "a weak bullet copied verbatim from the resume",
      "improved": "the rewritten version",
      "why": "one sentence on what changed and why it lands better"
    }
  ],
  "tailored_summary": "a 2-3 sentence professional summary the candidate can paste at the top of their resume for THIS role",
  "interview_questions": ["4-6 questions this candidate will likely be asked, based on their gaps and the JD"]
}"""


def build_analysis_prompt(
    resume_text: str,
    jd_text: str,
    missing_keywords: list[str],
    matched_keywords: list[str],
    weak_bullets: list[str],
) -> str:
    missing = ", ".join(missing_keywords[:15]) or "none detected"
    matched = ", ".join(matched_keywords[:15]) or "none detected"
    bullets = "\n".join(f"- {b}" for b in weak_bullets[:12]) or "(no bullet points detected)"

    return f"""Analyse this candidate against the job description.

=== JOB DESCRIPTION ===
{jd_text}

=== RESUME ===
{resume_text}

=== AUTOMATED PRE-ANALYSIS ===
Keywords from the JD already present in the resume: {matched}
Keywords from the JD missing from the resume: {missing}

Candidate's current bullet points (rewrite the 3-4 weakest of these):
{bullets}

=== YOUR TASK ===
Return a JSON object with exactly this shape:
{RESPONSE_SCHEMA}

Pick rewritten_bullets ONLY from the bullet list above — copy the "original" verbatim.
Prioritise gaps that map to the missing keywords listed above."""
