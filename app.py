from flask import Flask, render_template, request, redirect, url_for
from PyPDF2 import PdfReader
import requests
import os

app = Flask(__name__)

# =========================
# CONFIG
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# WARNING: Move this to an environment variable before deploying!
# Set it with: export GROQ_API_KEY="your_key_here"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")

# Store PDF text globally (demo-level memory)
pdf_text = ""
pdf_filename = ""


# =========================
# GROQ API HELPER
# =========================
def ask_groq(prompt, system_prompt="You are a helpful AI study assistant."):
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.4,
                "max_tokens": 1024
            },
            timeout=30
        )
        result = response.json()
        if "choices" in result:
            return result["choices"][0]["message"]["content"]
        else:
            return f"Error from API: {result.get('error', {}).get('message', 'Unknown error')}"
    except requests.exceptions.Timeout:
        return "Request timed out. Please try again."
    except Exception as e:
        return f"Something went wrong: {str(e)}"


# =========================
# HOME
# =========================
@app.route("/")
def home():
    return render_template("index.html", has_pdf=bool(pdf_text), pdf_filename=pdf_filename)


# =========================
# SUMMARY PAGE
# =========================
@app.route("/summary")
def summary_page():
    return render_template("summary.html")


@app.route("/upload", methods=["POST"])
def upload():
    global pdf_text, pdf_filename

    file = request.files["pdf"]

    if file.filename == "":
        return render_template("index.html", error="No file selected. Please choose a PDF.", has_pdf=False)

    if not file.filename.lower().endswith(".pdf"):
        return render_template("index.html", error="Only PDF files are supported.", has_pdf=False)

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)
    pdf_filename = file.filename

    # Extract text from ALL pages (up to 12,000 chars for better accuracy)
    pdf_text = ""
    try:
        reader = PdfReader(filepath)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pdf_text += text + "\n"
        pdf_text = pdf_text[:12000]
    except Exception as e:
        return render_template("summary.html", summary=f"Could not read PDF: {str(e)}", pdf_filename=pdf_filename)

    if not pdf_text.strip():
        return render_template("summary.html",
            summary="No readable text found in this PDF. It may be a scanned image-only PDF.",
            pdf_filename=pdf_filename)

    prompt = f"""Summarize the following study material clearly and concisely.

Format your response EXACTLY like this:
## Main Topic
[One sentence describing what this document is about]

## Key Points
- [Point 1]
- [Point 2]
- [Add more as needed]

## Important Terms
- **Term**: Brief explanation
- [Add more as needed]

## Quick Summary
[2-3 sentences wrapping up the core idea]

STUDY MATERIAL:
{pdf_text}"""

    summary = ask_groq(prompt, system_prompt="You are an expert study assistant. Always respond with well-structured, clear, exam-ready summaries.")

    return render_template("summary.html", summary=summary, pdf_filename=pdf_filename)


# =========================
# CHAT (AI TUTOR)
# =========================
@app.route("/chat")
def chat():
    return render_template("chat.html", has_pdf=bool(pdf_text), pdf_filename=pdf_filename)


@app.route("/ask", methods=["POST"])
def ask():
    global pdf_text

    question = request.form["question"].strip()

    if not question:
        return render_template("chat.html", error="Please enter a question.", has_pdf=bool(pdf_text))

    if pdf_text:
        system_prompt = """You are a smart and helpful AI tutor.
Answer clearly and accurately using the student's uploaded notes as the primary source.
If the question needs general knowledge to supplement the notes, use it and mention so.
Format answers with proper structure: bullet points, numbered steps, or short paragraphs."""

        prompt = f"""The student has uploaded these study notes:

--- NOTES START ---
{pdf_text}
--- NOTES END ---

Student's question: {question}

Give a clear, accurate, well-structured answer using the notes as your primary source."""
    else:
        system_prompt = """You are SmartStudy AI, a helpful and knowledgeable tutor.
Answer questions clearly, accurately, and in a well-structured way."""

        prompt = f"""Student question: {question}

Give a clear, accurate, well-structured answer."""

    answer = ask_groq(prompt, system_prompt=system_prompt)

    return render_template("chat.html", question=question, answer=answer, has_pdf=bool(pdf_text), pdf_filename=pdf_filename)


# =========================
# WRITER PAGE
# =========================
@app.route("/writer")
def writer():
    return render_template("writer.html")


@app.route("/write", methods=["POST"])
def write():
    topic = request.form["topic"].strip()

    if not topic:
        return render_template("writer.html", error="Please enter a topic.")

    prompt = f"""Write a clear, exam-ready explanation about: {topic}

Format your response like this:

## {topic}

### Definition
[Clear, simple definition]

### Key Concepts
- [Concept 1 with brief explanation]
- [Concept 2]

### Explanation
[Detailed but clear explanation in 2-4 paragraphs]

### Examples
- [Practical example 1]
- [Practical example 2]

### Key Takeaway
[1-2 sentence exam tip]"""

    output = ask_groq(prompt, system_prompt="You are an expert academic writer and tutor. Write clear, accurate, exam-ready explanations.")

    return render_template("writer.html", result=output, topic=topic)


# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    app.run(debug=True)
