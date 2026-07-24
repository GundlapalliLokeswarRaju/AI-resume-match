"""Generate a clean, ATS-friendly PDF resume for demoing the file-upload path.

    python sample_data/make_sample_pdf.py

Produces sample_data/sample_resume.pdf — a text-based (not scanned) PDF so pypdf
can extract it, matching the plain-text sample_resume.txt.
"""

from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).parent / "sample_resume.pdf"

styles = getSampleStyleSheet()
name = ParagraphStyle("name", parent=styles["Title"], fontSize=20, spaceAfter=2, alignment=TA_CENTER)
contact = ParagraphStyle("contact", parent=styles["Normal"], fontSize=9.5, alignment=TA_CENTER,
                         textColor="#333333", spaceAfter=10)
section = ParagraphStyle("section", parent=styles["Heading2"], fontSize=12, spaceBefore=12,
                        spaceAfter=4, textColor="#1a3a6b")
role = ParagraphStyle("role", parent=styles["Normal"], fontSize=10.5, spaceAfter=0, leading=14)
dates = ParagraphStyle("dates", parent=styles["Normal"], fontSize=9, textColor="#555555", spaceAfter=3)
body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.5, leading=13)
bullet = ParagraphStyle("bullet", parent=styles["Normal"], fontSize=9.5, leading=13)


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(t, bullet), leftIndent=12, value="•") for t in items],
        bulletType="bullet", start="•", leftIndent=14,
    )


def hr():
    return Paragraph('<para><font color="#cccccc">' + "_" * 95 + "</font></para>", body)


story = [
    Paragraph("PRIYA SHARMA", name),
    Paragraph(
        "Bengaluru, India &nbsp;|&nbsp; priya.sharma@email.com &nbsp;|&nbsp; +91 98765 43210<br/>"
        "linkedin.com/in/priyasharma-dev &nbsp;|&nbsp; github.com/priyasharma",
        contact,
    ),

    Paragraph("PROFESSIONAL SUMMARY", section), hr(),
    Paragraph(
        "Backend engineer with 4 years of experience building Python services and data "
        "pipelines. Comfortable across the stack from API design to deployment.", body),

    Paragraph("EXPERIENCE", section), hr(),
    Paragraph("<b>Software Engineer</b> — Nexora Technologies", role),
    Paragraph("Mar 2022 – Present", dates),
    bullets([
        "Built and shipped 12 REST API microservices in Python and FastAPI, serving 1.2M requests per day at p99 latency under 180ms.",
        "Reduced data pipeline runtime by 45% by rewriting batch jobs in Spark and moving orchestration to Airflow.",
        "Responsible for the team's PostgreSQL schema design and query optimization.",
        "Deployed services to AWS using Docker and GitHub Actions CI/CD, cutting release time from 2 hours to 15 minutes.",
        "Mentored 3 junior engineers through code review and pairing.",
    ]),
    Spacer(1, 6),
    Paragraph("<b>Junior Developer</b> — Datalane Systems", role),
    Paragraph("Jul 2020 – Feb 2022", dates),
    bullets([
        "Worked on internal reporting dashboards using Python and SQL.",
        "Helped with migration of legacy scripts to a scheduled ETL framework.",
        "Wrote unit tests with pytest, raising service coverage from 40% to 82%.",
    ]),

    Paragraph("PROJECTS", section), hr(),
    Paragraph("<b>Document Search Engine</b>", role),
    bullets([
        "Built a semantic search prototype over 50k internal documents using sentence embeddings and FAISS, improving retrieval precision by 30%.",
    ]),
    Spacer(1, 4),
    Paragraph("<b>Sentiment Classifier</b>", role),
    bullets([
        "Trained a text classification model with scikit-learn achieving 91% F1 on a customer feedback dataset of 40k labelled reviews.",
    ]),

    Paragraph("EDUCATION", section), hr(),
    Paragraph("<b>B.Tech, Computer Science</b> — Visvesvaraya Technological University, 2020 &nbsp;|&nbsp; CGPA 8.4 / 10", body),

    Paragraph("TECHNICAL SKILLS", section), hr(),
    Paragraph(
        "<b>Languages:</b> Python, SQL, JavaScript, Bash<br/>"
        "<b>Frameworks:</b> FastAPI, Flask, Django<br/>"
        "<b>Data:</b> PostgreSQL, Redis, Spark, Airflow, pandas, NumPy<br/>"
        "<b>ML:</b> scikit-learn, FAISS, embeddings<br/>"
        "<b>Cloud &amp; DevOps:</b> AWS, Docker, Git, GitHub Actions, Linux<br/>"
        "<b>Practices:</b> Agile, Scrum, unit testing, code review", body),
]

doc = SimpleDocTemplate(
    str(OUT), pagesize=LETTER,
    leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    title="Priya Sharma — Resume",
)
doc.build(story)
print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes)")
