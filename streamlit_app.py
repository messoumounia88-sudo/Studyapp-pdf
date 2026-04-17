
import streamlit as st
import os
import tempfile
import re
from pathlib import Path

# PDF generation
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak, ListFlowable, ListItem
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

# Document reading
import docx
import fitz  # PyMuPDF

# AI enrichment
from openai import OpenAI

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="StudyPDF Generator",
    page_icon="📚",
    layout="centered"
)

# ─── Styles ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f9f9f9; }
    h1 { color: #1a3a5c; }
    .stButton > button {
        background-color: #1a3a5c;
        color: white;
        border-radius: 8px;
        padding: 0.6em 1.4em;
        font-size: 16px;
        font-weight: bold;
    }
    .stButton > button:hover { background-color: #2a5298; }
    .upload-box { border: 2px dashed #1a3a5c; border-radius: 10px; padding: 20px; }
</style>
""", unsafe_allow_html=True)

# ─── Header ─────────────────────────────────────────────────────────────────
st.title("📚 StudyPDF Generator")
st.markdown("Upload any course document (PDF, DOCX, or TXT) and get a **fully structured, deeply explained study guide** as a PDF — with AI-enriched explanations where needed.")
st.divider()

# ─── Settings ───────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    course_title = st.text_input("📖 Course / Subject Title", placeholder="e.g. US History 1945–2021")
with col2:
    author_label = st.text_input("🎓 Institution / Year", placeholder="e.g. L3 S2 · 2025–2026")

ai_enrich = st.toggle("🤖 Enrich with AI explanations (requires OpenAI API key)", value=False)

if ai_enrich:
    api_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")
else:
    api_key = ""

st.divider()

# ─── File uploader ───────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "📂 Upload your course file",
    type=["pdf", "docx", "txt"],
    help="Supports PDF, Word (.docx), and plain text files"
)

# ─── Extraction ──────────────────────────────────────────────────────────────
def extract_text(file, suffix):
    if suffix == ".txt":
        return file.read().decode("utf-8")
    elif suffix == ".docx":
        doc = docx.Document(file)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    elif suffix == ".pdf":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file.read())
            tmp_path = tmp.name
        text = ""
        with fitz.open(tmp_path) as doc:
            for page in doc:
                text += page.get_text()
        os.unlink(tmp_path)
        return text

# ─── Lesson parser ───────────────────────────────────────────────────────────
def parse_lessons(text):
    pattern = r"(?:LESSON\s+\d+|Lesson\s+\d+|CHAPTER\s+\d+|Chapter\s+\d+|UNIT\s+\d+|Unit\s+\d+)"
    splits = re.split(f"({pattern})", text)
    lessons = []
    if len(splits) <= 1:
        chunks = [text[i:i+3000] for i in range(0, len(text), 3000)]
        for i, chunk in enumerate(chunks):
            lessons.append({"label": f"SECTION {i+1}", "title": f"Part {i+1}", "content": chunk})
        return lessons
    i = 1
    while i < len(splits) - 1:
        label = splits[i].strip()
        body = splits[i+1] if i+1 < len(splits) else ""
        lines = [l.strip() for l in body.strip().split("\n") if l.strip()]
        title = lines[0] if lines else label
        content = "\n".join(lines[1:]) if len(lines) > 1 else ""
        lessons.append({"label": label.upper(), "title": title, "content": content})
        i += 2
    return lessons

# ─── AI enrichment ───────────────────────────────────────────────────────────
def enrich_with_ai(lesson_title, lesson_content, api_key):
    client = OpenAI(api_key=api_key)
    prompt = f"""You are an expert academic tutor. Given raw course notes for the lesson titled "{lesson_title}", 
rewrite and expand them into a deeply explained, well-structured academic lesson. 

Rules:
- Keep ALL original facts, dates, names, and data
- Add clear causal explanations: WHY things happened, not just WHAT happened
- Add context and consequences for each major event
- Use clear section headings (start with ##)
- Use bullet points (start with -) for lists of items
- Keep an academic but accessible tone
- Aim for completeness: a student should fully understand the lesson from your output alone

Raw notes:
{lesson_content[:4000]}

Output the expanded lesson now:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2500,
        temperature=0.4
    )
    return response.choices[0].message.content

# ─── PDF builder ─────────────────────────────────────────────────────────────
def build_pdf(lessons, course_title, author_label, output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=2.2*cm, leftMargin=2.2*cm,
        topMargin=2.5*cm, bottomMargin=2.5*cm
    )

    cover_title = ParagraphStyle("CoverTitle", fontSize=24, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1a3a5c"), spaceAfter=10, alignment=TA_CENTER)
    cover_sub = ParagraphStyle("CoverSub", fontSize=13, fontName="Helvetica",
        textColor=colors.HexColor("#555555"), spaceAfter=8, alignment=TA_CENTER)
    lesson_hdr = ParagraphStyle("LHdr", fontSize=14, fontName="Helvetica-Bold",
        textColor=colors.white, backColor=colors.HexColor("#1a3a5c"),
        spaceAfter=10, spaceBefore=16, borderPad=8, leading=20)
    section_hdr = ParagraphStyle("SHdr", fontSize=11, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1a3a5c"), spaceAfter=4, spaceBefore=10)
    body_s = ParagraphStyle("Body", fontSize=10, fontName="Helvetica",
        textColor=colors.HexColor("#222222"), spaceAfter=6, leading=15, alignment=TA_JUSTIFY)
    bullet_s = ParagraphStyle("Bul", fontSize=10, fontName="Helvetica",
        textColor=colors.HexColor("#333333"), spaceAfter=3, leading=14, leftIndent=16)

    story = []

    # Cover
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph(course_title or "Complete Course Study Guide", cover_title))
    story.append(Paragraph("Structured Study Notes — All Lessons", cover_sub))
    if author_label:
        story.append(Paragraph(author_label, cover_sub))
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a3a5c")))
    story.append(PageBreak())

    for lesson in lessons:
        story.append(Paragraph(f"{lesson['label']} — {lesson['title']}", lesson_hdr))
        story.append(Spacer(1, 0.2*cm))

        content = lesson.get("enriched") or lesson["content"]
        current_section_bullets = []

        def flush_bullets():
            for bt in current_section_bullets:
                story.append(Paragraph(f"• {bt}", bullet_s))
            current_section_bullets.clear()

        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("## ") or line.startswith("### "):
                flush_bullets()
                heading = line.lstrip("#").strip()
                story.append(Paragraph(f"— {heading}", section_hdr))
            elif line.startswith("- ") or line.startswith("* "):
                current_section_bullets.append(line[2:].strip())
            elif line.startswith("**") and line.endswith("**"):
                flush_bullets()
                story.append(Paragraph(f"<b>{line[2:-2]}</b>", body_s))
            else:
                flush_bullets()
                cleaned = line.replace("**", "").replace("*", "").replace("__", "")
                story.append(Paragraph(cleaned, body_s))

        flush_bullets()
        story.append(PageBreak())

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3a5c")))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("End of Study Guide", cover_sub))
    doc.build(story)

# ─── Main action ─────────────────────────────────────────────────────────────
if uploaded_file:
    st.success(f"✅ File uploaded: **{uploaded_file.name}**")

    if st.button("🚀 Generate Study PDF"):
        suffix = Path(uploaded_file.name).suffix.lower()

        with st.spinner("📖 Reading and parsing your document..."):
            raw_text = extract_text(uploaded_file, suffix)
            lessons = parse_lessons(raw_text)
            st.info(f"Found **{len(lessons)} lesson(s)** in your document.")

        if ai_enrich and api_key:
            prog = st.progress(0, text="🤖 Enriching lessons with AI...")
            for i, lesson in enumerate(lessons):
                prog.progress((i + 1) / len(lessons), text=f"🤖 Processing: {lesson['title'][:40]}...")
                try:
                    lessons[i]["enriched"] = enrich_with_ai(lesson["title"], lesson["content"], api_key)
                except Exception as e:
                    st.warning(f"AI enrichment failed for lesson {i+1}: {e}")
                    lessons[i]["enriched"] = None
            prog.empty()

        with st.spinner("📄 Building your PDF..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                build_pdf(lessons, course_title, author_label, tmp_pdf.name)
                tmp_pdf_path = tmp_pdf.name

        with open(tmp_pdf_path, "rb") as f:
            pdf_bytes = f.read()
        os.unlink(tmp_pdf_path)

        st.success("✅ Your study PDF is ready!")
        fname = (course_title.replace(" ", "_") if course_title else "StudyGuide") + ".pdf"
        st.download_button(
            label="📥 Download your Study PDF",
            data=pdf_bytes,
            file_name=fname,
            mime="application/pdf"
        )
else:
    st.info("👆 Upload a file above to get started.")

st.divider()
st.caption("StudyPDF Generator · Powered by ReportLab + OpenAI · Built for students")
