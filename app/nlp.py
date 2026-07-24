"""Deterministic keyword extraction and resume/JD matching.

No model calls here — this layer is fast, free and reproducible, which keeps the
score stable even when the LLM is unavailable.
"""

import re
from collections import Counter, defaultdict

STOPWORDS = {
    "a", "about", "above", "across", "after", "all", "also", "an", "and", "any", "are", "as", "at",
    "be", "been", "being", "both", "but", "by", "can", "could", "do", "does", "doing", "each",
    "etc", "for", "from", "had", "has", "have", "he", "her", "here", "him", "his", "how", "i",
    "if", "in", "into", "is", "it", "its", "just", "may", "me", "more", "most", "must", "my",
    "no", "not", "of", "on", "one", "only", "or", "other", "our", "out", "over", "own", "per",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "up",
    "us", "very", "was", "we", "well", "were", "what", "when", "where", "which", "while", "who",
    "why", "will", "with", "within", "would", "you", "your",
    # resume/JD boilerplate that is never a real requirement
    "ability", "candidate", "role", "team", "teams", "work", "working", "job", "position",
    "experience", "years", "year", "strong", "good", "great", "excellent", "responsibilities",
    "requirements", "qualifications", "preferred", "plus", "bonus", "including", "include",
    "ideal", "looking", "join", "company", "opportunity", "benefits", "salary", "apply",
    "applicants", "employment", "please", "you'll", "we're", "must-have", "nice",
}

# Canonical skill vocabulary. Multi-word entries are matched as phrases.
SKILL_VOCAB = {
    # languages
    "python", "java", "javascript", "typescript", "go", "golang", "rust", "c++", "c#", "sql",
    "bash", "scala", "kotlin", "swift", "ruby", "php", "r", "matlab",
    # web / api
    "fastapi", "django", "flask", "react", "next.js", "node.js", "express", "spring boot",
    "rest api", "graphql", "grpc", "websocket", "microservices", "html", "css", "tailwind",
    # data / ml
    "machine learning", "deep learning", "nlp", "natural language processing", "computer vision",
    "pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy", "hugging face",
    "transformers", "llm", "large language models", "rag", "prompt engineering", "langchain",
    "vector database", "embeddings", "generative ai", "mlops", "feature engineering",
    "data analysis", "data science", "statistics", "a/b testing", "time series",
    "recommendation systems", "xgboost", "spark", "hadoop", "airflow", "dbt", "etl",
    "data pipeline", "power bi", "tableau", "looker", "excel",
    # infra / cloud
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "terraform", "ansible",
    "jenkins", "ci/cd", "github actions", "gitlab", "linux", "nginx", "serverless", "lambda",
    "cloudformation", "prometheus", "grafana", "datadog",
    # databases
    "postgresql", "postgres", "mysql", "mongodb", "redis", "elasticsearch", "cassandra",
    "dynamodb", "snowflake", "bigquery", "redshift", "sqlite", "pinecone", "faiss", "chroma",
    # practices / soft
    "agile", "scrum", "kanban", "jira", "git", "unit testing", "pytest", "tdd", "code review",
    "system design", "api design", "documentation", "stakeholder management", "mentoring",
    "cross-functional", "communication", "leadership", "problem solving", "ownership",
}

# Map surface forms to one canonical token so "K8s" and "Kubernetes" score as one skill.
ALIASES = {
    "k8s": "kubernetes",
    "golang": "go",
    "js": "javascript",
    "ts": "typescript",
    "postgres": "postgresql",
    "ml": "machine learning",
    "dl": "deep learning",
    "natural language processing": "nlp",
    "large language models": "llm",
    "llms": "llm",
    "google cloud": "gcp",
    "gen ai": "generative ai",
    "genai": "generative ai",
    "ci cd": "ci/cd",
    "cicd": "ci/cd",
    "nodejs": "node.js",
    "node js": "node.js",
    "nextjs": "next.js",
    "sklearn": "scikit-learn",
    "huggingface": "hugging face",
    "restful api": "rest api",
    "rest apis": "rest api",
    "apis": "rest api",
}

ACTION_VERBS = {
    "achieved", "architected", "automated", "built", "created", "cut", "decreased", "delivered",
    "deployed", "designed", "developed", "drove", "engineered", "enhanced", "established",
    "generated", "implemented", "improved", "increased", "initiated", "launched", "led",
    "migrated", "optimized", "orchestrated", "owned", "developed", "reduced", "refactored",
    "resolved", "scaled", "shipped", "spearheaded", "streamlined", "trained",
}

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#./-]*")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def canonical(term: str) -> str:
    term = term.strip().lower()
    return ALIASES.get(term, term)


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _phrase_count(haystack: str, phrase: str) -> int:
    """Count phrase occurrences with word-ish boundaries (handles c++, ci/cd, node.js)."""
    pattern = r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])"
    return len(re.findall(pattern, haystack))


def extract_jd_keywords(jd_text: str, limit: int = 30) -> list[tuple[str, float]]:
    """Return [(keyword, importance 0-1)] ranked by how central the term is to the JD.

    Iteration and sorting are both deterministic: SKILL_VOCAB is a set, so unsorted
    traversal plus score ties would let Python's per-process hash seed decide which
    keywords survive the `limit` cut — the same resume would score differently
    between runs.
    """
    text = normalize(jd_text)

    scores: defaultdict[str, float] = defaultdict(float)

    # 1) Known skills carry the most signal.
    for skill in sorted(SKILL_VOCAB):
        count = _phrase_count(text, skill)
        if count:
            # Multi-word skills ("prompt engineering") are more discriminating than
            # single tokens, so nudge them above the tie line.
            specificity = 1.0 + 0.15 * skill.count(" ")
            scores[canonical(skill)] += count * 3.0 * specificity

    # 2) Alias surface forms feed the same canonical bucket.
    for alias, target in sorted(ALIASES.items()):
        count = _phrase_count(text, alias)
        if count:
            scores[canonical(target)] += count * 3.0

    # 3) Frequent domain nouns the vocabulary does not know about yet.
    tokens = [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 2 and not t.isdigit()]
    for token, count in Counter(tokens).items():
        if count >= 2:
            scores[canonical(token)] += count * 0.8

    # 4) Repeated two-word phrases catch things like "incident response".
    for i in range(len(tokens) - 1):
        bigram = f"{tokens[i]} {tokens[i + 1]}"
        scores[canonical(bigram)] += 0.5

    # Drop bigrams that only appeared once and noisy fragments.
    for key in list(scores):
        if " " in key and scores[key] <= 1.0 and key not in SKILL_VOCAB:
            del scores[key]

    if not scores:
        return []

    # Alphabetical secondary key keeps tied keywords in a stable, seed-independent order.
    top = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    peak = top[0][1] or 1.0
    return [(term, round(min(1.0, raw / peak), 3)) for term, raw in top]


def match_keywords(resume_text: str, jd_keywords: list[tuple[str, float]]) -> dict:
    """Check each JD keyword against the resume and compute weighted coverage."""
    resume = normalize(resume_text)

    matched, missing = [], []
    weight_total = weight_hit = 0.0

    for term, importance in jd_keywords:
        count = _phrase_count(resume, term)
        # Try alias surface forms too — resume may write "K8s" where JD wrote "Kubernetes".
        if not count:
            for alias, target in ALIASES.items():
                if canonical(target) == term:
                    count = _phrase_count(resume, alias)
                    if count:
                        break

        entry = {
            "keyword": term,
            "in_resume": bool(count),
            "resume_count": count,
            "importance": importance,
        }
        weight_total += importance
        if count:
            weight_hit += importance
            matched.append(entry)
        else:
            missing.append(entry)

    coverage = (weight_hit / weight_total * 100) if weight_total else 0.0
    matched.sort(key=lambda e: -e["importance"])
    missing.sort(key=lambda e: -e["importance"])

    return {"matched": matched, "missing": missing, "coverage": round(coverage, 1)}


def guess_job_title(jd_text: str) -> str | None:
    """Best-effort job title from the first meaningful line of the JD."""
    for line in jd_text.strip().splitlines():
        line = line.strip(" #*-—:")
        if 3 <= len(line) <= 80 and not line.lower().startswith(("about", "we are", "job desc")):
            return line
    return None
