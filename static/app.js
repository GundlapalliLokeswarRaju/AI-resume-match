/* ResuMatch AI — front-end controller */

const $ = (id) => document.getElementById(id);

const state = { mode: "file", file: null, lastResult: null };

const SAMPLE_JD = `Senior AI/ML Engineer

We are hiring a Senior AI/ML Engineer to build and ship production LLM systems.

Responsibilities:
- Design and deploy RAG pipelines over large internal document sets
- Build and maintain FastAPI microservices serving ML models at scale
- Fine-tune and evaluate large language models for domain-specific tasks
- Own MLOps: CI/CD, monitoring, and model versioning on AWS
- Partner cross-functionally with product and data teams

Requirements:
- 5+ years of experience in machine learning or backend engineering
- Expert-level Python; strong SQL
- Hands-on experience with PyTorch, Hugging Face Transformers and LangChain
- Production experience with Docker, Kubernetes and AWS
- Experience with vector databases (Pinecone, FAISS or Chroma) and embeddings
- Solid grasp of prompt engineering and LLM evaluation
- Familiarity with PostgreSQL, Redis and REST API design

Nice to have:
- Experience with Airflow or Spark data pipelines
- Contributions to open-source ML projects
- Experience mentoring junior engineers`;

/* ---------------- health badge ---------------- */
async function loadHealth() {
  const badge = $("llmBadge");
  try {
    const r = await fetch("/api/health");
    const h = await r.json();
    if (h.llm_enabled) {
      badge.textContent = "AI enabled · " + h.model.split("/").pop();
      badge.className = "badge";
    } else {
      badge.textContent = "rule-based only";
      badge.className = "badge badge-off";
      badge.title = "Add GROQ_API_KEY to .env to enable AI insights";
    }
  } catch {
    badge.textContent = "offline";
    badge.className = "badge badge-off";
  }
}

/* ---------------- input mode tabs ---------------- */
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    state.mode = tab.dataset.mode;
    $("fileMode").classList.toggle("hidden", state.mode !== "file");
    $("textMode").classList.toggle("hidden", state.mode !== "text");
  });
});

/* ---------------- file handling ---------------- */
const dropzone = $("dropzone");
const fileInput = $("fileInput");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
});
["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("drag"); })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("drag"); })
);
dropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) setFile(fileInput.files[0]);
});

function setFile(file) {
  const ok = /\.(pdf|docx|txt|md)$/i.test(file.name);
  if (!ok) return showError("Unsupported file type. Use PDF, DOCX, TXT or MD.");
  if (file.size > 5 * 1024 * 1024) return showError("File is larger than 5 MB.");
  state.file = file;
  const chip = $("fileChip");
  chip.querySelector(".fc-name").textContent =
    `${file.name} · ${(file.size / 1024).toFixed(0)} KB`;
  chip.classList.remove("hidden");
  dropzone.classList.add("hidden");
  hideError();
}

$("fileChip").querySelector(".fc-clear").addEventListener("click", () => {
  state.file = null;
  fileInput.value = "";
  $("fileChip").classList.add("hidden");
  dropzone.classList.remove("hidden");
});

/* ---------------- JD helpers ---------------- */
$("jdText").addEventListener("input", (e) => {
  $("jdCount").textContent = `${e.target.value.length.toLocaleString()} characters`;
});
$("sampleBtn").addEventListener("click", () => {
  $("jdText").value = SAMPLE_JD;
  $("jdCount").textContent = `${SAMPLE_JD.length.toLocaleString()} characters`;
});

/* ---------------- errors ---------------- */
function showError(msg) {
  const el = $("errorMsg");
  el.textContent = msg;
  el.classList.remove("hidden");
}
function hideError() { $("errorMsg").classList.add("hidden"); }

/* ---------------- analyze ---------------- */
$("analyzeBtn").addEventListener("click", analyze);

async function analyze() {
  hideError();
  const jd = $("jdText").value.trim();
  if (jd.length < 50) return showError("Paste a job description first (at least 50 characters).");

  const body = new FormData();
  body.append("job_description", jd);
  let endpoint;

  if (state.mode === "file") {
    if (!state.file) return showError("Upload your resume file, or switch to the “Paste text” tab.");
    endpoint = "/api/analyze";
    body.append("resume", state.file);
  } else {
    const text = $("resumeText").value.trim();
    if (text.length < 100) return showError("Paste your resume text (at least 100 characters).");
    endpoint = "/api/analyze-text";
    body.append("resume_text", text);
  }

  $("inputCard").classList.add("hidden");
  $("results").classList.add("hidden");
  $("loadingCard").classList.remove("hidden");
  const stopProgress = runProgress();

  try {
    const res = await fetch(endpoint, { method: "POST", body });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
    stopProgress(100);
    state.lastResult = data;
    setTimeout(() => {
      $("loadingCard").classList.add("hidden");
      render(data);
    }, 350);
  } catch (err) {
    stopProgress(0);
    $("loadingCard").classList.add("hidden");
    $("inputCard").classList.remove("hidden");
    showError(err.message);
  }
}

function runProgress() {
  const steps = [
    [10, "Extracting text from your resume…"],
    [30, "Parsing the job description…"],
    [50, "Matching keywords and weighting importance…"],
    [68, "Running ATS compliance checks…"],
    [85, "Asking the model for tailored feedback…"],
  ];
  let i = 0;
  const tick = setInterval(() => {
    if (i >= steps.length) return;
    const [pct, label] = steps[i++];
    $("progressBar").style.width = pct + "%";
    $("loadingText").textContent = label;
  }, 750);
  return (final) => {
    clearInterval(tick);
    $("progressBar").style.width = final + "%";
  };
}

/* ---------------- rendering ---------------- */
function colorFor(score) {
  if (score >= 75) return getComputedStyle(document.documentElement).getPropertyValue("--good");
  if (score >= 55) return getComputedStyle(document.documentElement).getPropertyValue("--warn");
  return getComputedStyle(document.documentElement).getPropertyValue("--bad");
}

function render(d) {
  $("results").classList.remove("hidden");

  // gauge
  const s = d.score;
  const arc = $("gaugeArc");
  const circumference = 515;
  arc.style.stroke = colorFor(s.overall);
  requestAnimationFrame(() => {
    arc.style.strokeDashoffset = circumference * (1 - s.overall / 100);
  });
  animateNumber($("overallScore"), s.overall);

  const pill = $("bandPill");
  pill.textContent = s.band + " match";
  pill.className = "band-pill band-" + s.band;
  $("verdictText").textContent = s.verdict;

  const bits = [];
  if (d.job_title_guess) bits.push(`Target: ${d.job_title_guess}`);
  if (d.filename) bits.push(d.filename);
  bits.push(`analyzed in ${d.elapsed_ms} ms`);
  $("metaLine").textContent = bits.join(" · ");

  setMetric("Keyword", s.keyword_match);
  setMetric("Ats", s.ats_readiness);
  setMetric("Exp", s.experience_signal);

  // keywords
  const k = d.keywords;
  $("kwSub").textContent =
    `${k.matched.length} of ${k.matched.length + k.missing.length} job-description keywords found · ${k.coverage}% weighted coverage`;
  renderChips($("missingChips"), k.missing, "chip-miss", "Nothing missing — excellent coverage.");
  renderChips($("matchedChips"), k.matched, "chip-hit", "No overlap detected yet.");

  // ATS
  const icons = { pass: "✓", warn: "!", fail: "✕" };
  $("atsChecks").innerHTML = d.ats.checks
    .map(
      (c) => `<li>
        <span class="ck-icon ck-${c.status}">${icons[c.status]}</span>
        <div>
          <p class="ck-label">${esc(c.label)}</p>
          <p class="ck-detail">${esc(c.detail)}</p>
        </div>
      </li>`
    )
    .join("");

  renderInsights(d.insights);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setMetric(key, value) {
  $("m" + key).textContent = value + "%";
  const bar = $("bar" + key);
  requestAnimationFrame(() => { bar.style.width = value + "%"; });
}

function renderChips(el, items, cls, emptyMsg) {
  if (!items.length) {
    el.innerHTML = `<span class="empty">${emptyMsg}</span>`;
    return;
  }
  el.innerHTML = items
    .slice(0, 18)
    .map((i) => {
      const stars = i.importance >= 0.66 ? "high" : i.importance >= 0.33 ? "med" : "low";
      return `<span class="chip ${cls}" title="Importance: ${stars}">${esc(i.keyword)}${
        i.resume_count ? ` <b>×${i.resume_count}</b>` : ""
      }</span>`;
    })
    .join("");
}

function renderInsights(ai) {
  $("modelBadge").textContent = ai.enabled ? ai.model : "unavailable";
  $("modelBadge").className = ai.enabled ? "badge" : "badge badge-off";

  if (!ai.enabled) {
    $("aiBody").innerHTML = `<div class="notice">
      <strong>AI insights are off.</strong><br>${esc(ai.error || "The model call did not complete.")}
      <br><br>Add <code>GROQ_API_KEY=your_key</code> to the <code>.env</code> file and restart the server.
      Everything above is rule-based and works without a key.
    </div>`;
    return;
  }

  let html = "";
  if (ai.summary) html += `<div class="ai-summary">${esc(ai.summary)}</div>`;

  html += `<div class="ai-grid">
    <div>
      <p class="section-h">Strengths</p>
      <ul class="ai-list list-good">${ai.strengths.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    </div>
    <div>
      <p class="section-h">Gaps to close</p>
      <ul class="ai-list list-bad">${ai.gaps.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    </div>
  </div>`;

  if (ai.rewritten_bullets?.length) {
    html += `<p class="section-h">Suggested bullet rewrites</p>`;
    html += ai.rewritten_bullets
      .map(
        (b) => `<div class="rewrite">
          <p class="rw-before">${esc(b.original)}</p>
          <p class="rw-after">${esc(b.improved)}</p>
          <p class="rw-why">${esc(b.why)}</p>
        </div>`
      )
      .join("");
  }

  if (ai.tailored_summary) {
    html += `<p class="section-h" style="margin-top:22px">Tailored professional summary</p>
      <div class="tailored">
        <span id="tailoredText">${esc(ai.tailored_summary)}</span><br>
        <button class="copy-btn" id="copyBtn">Copy to clipboard</button>
      </div>`;
  }

  if (ai.interview_questions?.length) {
    html += `<p class="section-h" style="margin-top:22px">Likely interview questions</p>
      <ul class="ai-list list-q">${ai.interview_questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>`;
  }

  $("aiBody").innerHTML = html;

  const copyBtn = $("copyBtn");
  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(ai.tailored_summary).then(() => {
        copyBtn.textContent = "Copied ✓";
        setTimeout(() => (copyBtn.textContent = "Copy to clipboard"), 1800);
      });
    });
  }
}

function animateNumber(el, target) {
  const duration = 1000;
  const start = performance.now();
  function frame(now) {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = (target * eased).toFixed(t === 1 ? 1 : 0);
    if (t < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

function esc(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

/* ---------------- footer actions ---------------- */
$("resetBtn").addEventListener("click", () => {
  $("results").classList.add("hidden");
  $("inputCard").classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
});

$("jsonBtn").addEventListener("click", () => {
  if (!state.lastResult) return;
  const existing = document.getElementById("jsonDump");
  if (existing) return existing.remove();
  const pre = document.createElement("pre");
  pre.className = "json card";
  pre.id = "jsonDump";
  pre.textContent = JSON.stringify(state.lastResult, null, 2);
  $("results").appendChild(pre);
  pre.scrollIntoView({ behavior: "smooth" });
});

loadHealth();
