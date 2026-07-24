# LinkedIn post — ResuMatch AI

Live demo: https://fastapi-5464a195.fastapicloud.dev
Docs: https://fastapi-5464a195.fastapicloud.dev/docs

Screenshot suggestions (attach 2–3):
1. The results view — score gauge + red/green keyword chips + an AI bullet rewrite.
2. The /docs Swagger page (shows it's a real API, not just a UI).
3. Optional: the terminal showing `28 passed`.

---

## VERSION A — build-in-public / technical (recommended)

I built and deployed an AI Resume Analyzer this week. 🎯

ResuMatch AI takes your resume + a job description and returns an explainable match score:
keyword-gap analysis, a 9-point ATS readiness report, and LLM-generated bullet rewrites.

🔗 Try it live: https://fastapi-5464a195.fastapicloud.dev

The design decision I'm most happy with: TWO independent layers.

→ A deterministic layer (keyword extraction, ATS rules, experience matching) that's free,
instant, and 100% reproducible.
→ An LLM layer on top (Groq + LLaMA 3.3 70B) for the qualitative coaching.

Why it matters: if the API key is missing, rate-limited, or the model returns malformed JSON,
the app STILL returns a complete scored report. The AI is an enhancement, never a
single point of failure. That's also what let me test the whole thing offline and for free.

Two bugs worth sharing:

1️⃣ My keyword scores weren't reproducible. The skill vocabulary was a Python set, and most
skills tied on score — so which keywords made the top-N cut depended on the process hash seed.
The same resume could score differently between runs. Fixed with sorted traversal + a
deterministic tiebreak, then pinned it with a test that runs extraction under 3 different
hash seeds and asserts identical output.

2️⃣ My phone-number check assumed US formatting and silently failed on "+91 98765 43210".
Made it format-agnostic.

Stack: FastAPI · Pydantic v2 · Groq · pypdf · python-docx · vanilla JS (no build step) ·
28 tests · deployed on FastAPI Cloud with the API key as a managed secret.

Everything — the score weighting, the ATS rules, the anti-hallucination prompt (the model
inserts [X%] placeholders instead of inventing numbers) — is in the repo.

What would you add next? I'm considering multi-resume comparison and a Chrome extension.

#FastAPI #Python #AI #LLM #MachineLearning #BuildInPublic #Groq #WebDevelopment


---

## VERSION B — shorter / recruiter-friendly

Ever wondered why your resume gets auto-rejected? I built a tool that shows you. 🎯

ResuMatch AI scores your resume against any job description:
✅ Weighted keyword-gap analysis (what the ATS is actually filtering on)
✅ A 9-point ATS readiness report — contact info, dates, metrics, action verbs
✅ AI-generated rewrites for your weakest bullets
✅ A tailored professional summary you can paste straight in

🔗 Try it free: https://fastapi-5464a195.fastapicloud.dev

Built with FastAPI and Groq (LLaMA 3.3 70B), deployed on FastAPI Cloud.

The part I'm proud of: it's engineered to degrade gracefully. Even if the AI layer is
unavailable, you still get a full rule-based analysis — the app never just breaks. 28 tests,
all running offline.

Feedback very welcome — what would make this genuinely useful in your job search?

#FastAPI #Python #AI #ResumeTips #JobSearch #LLM #BuildInPublic


---

## Reply-to-your-own-comment (drop the tech detail here to keep the post clean)

Tech notes for anyone curious 👇
• Score = 50% keyword match + 30% ATS readiness + 20% experience fit
• Groq key stored as a cloud secret, never committed
• Rule-based layer is fully deterministic — pinned by a hash-seed test
• Public demo is rate-limited (10 analyses / 10 min / IP) to protect the shared quota
• Full source + API docs: https://github.com/GundlapalliLokeswarRaju/AI-resume-match


---

## PINNED FIRST COMMENT (post this as the very first comment, then pin it)

Post the first comment yourself the moment the post goes live — LinkedIn's algorithm
rewards early engagement, and it keeps the demo link out of the main body (link-in-body
posts get throttled). Then click the ⋯ on your comment and "Pin".

Pick ONE:

▶ Short version:
Try it here 👉 https://fastapi-5464a195.fastapicloud.dev
Code + API docs 👉 https://github.com/GundlapalliLokeswarRaju/AI-resume-match
Tip: hit "Load sample job description", upload any resume, and you'll get a score in ~3s.
Would love your feedback 🙏

▶ With a question to spark comments:
Live demo 👉 https://fastapi-5464a195.fastapicloud.dev
Source 👉 https://github.com/GundlapalliLokeswarRaju/AI-resume-match

Quick question for the recruiters and hiring managers here: what's the ONE thing on a
resume that makes you keep reading past the first 6 seconds? Building that into v2. 👇


---

## Notes for the demo screenshots

• A ready-made sample resume PDF is at `sample_data/sample_resume.pdf` — drag it into the
  upload box so the file-upload path shows in your screenshots.
• Flow: open the live URL → "Load sample job description" → upload the PDF → "Analyze".
• Best shots: (1) the results view with the score gauge + red/green keyword chips + an AI
  bullet rewrite, (2) the /docs Swagger page.
