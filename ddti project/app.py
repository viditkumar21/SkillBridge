from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
import os
import json
import google.generativeai as genai
from resume_parser import extract_resume_text, extract_skills_from_text, parse_resume_sections
from report_generator import generate_pdf_report
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import uuid
import logging
import unicodedata

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
UPLOAD_FOLDER = 'Uploads'
REPORTS_FOLDER = 'Reports'
PROGRESS_FILE = 'progress.json'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['REPORTS_FOLDER'] = REPORTS_FOLDER

# Create folders if they don't exist
for folder in [UPLOAD_FOLDER, REPORTS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Load Gemini API key
try:
    with open("gemini-key.txt", "r") as f:
        GEMINI_API_KEY = f.read().strip()
except FileNotFoundError:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Gemini API key not found. Set it in gemini-key.txt or GEMINI_API_KEY env variable.")
genai.configure(api_key=GEMINI_API_KEY)

# Load job roles
with open("job_roles.json", "r") as f:
    job_roles = json.load(f)

# Load or initialize progress
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, "r") as f:
        progress = json.load(f)
else:
    progress = {}

def sanitize_text(text):
    """Normalize Unicode characters and replace problematic ones with ASCII equivalents"""
    if not isinstance(text, str):
        text = str(text)
    # Normalize Unicode (e.g., convert en dash '\u2013' to '-')
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    # Replace any remaining non-ASCII characters
    text = re.sub(r'[^\x00-\x7F]+', '-', text)
    return text

def calculate_ats_score(text, skills):
    """Calculate ATS compatibility score (0-100)"""
    score = 0
    job_keywords = set()
    for job in job_roles.values():
        job_keywords.update(job["required_skills"])
    matched_keywords = len([s for s in skills if s in job_keywords])
    score += min((matched_keywords / len(job_keywords)) * 50, 50) if job_keywords else 0
    if re.search(r'\b(increased|improved|reduced|generated|saved)\b.*\b(\d+%|\$\d+|\d+.*(users|clients))\b', text, re.IGNORECASE):
        score += 30
    if len(parse_resume_sections(text)) > 1:
        score += 20
    return round(score)

def match_jobs(skills):
    """Match skills to job roles using cosine similarity"""
    documents = [", ".join(skills)] + [", ".join(job["required_skills"]) for job in job_roles.values()]
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(documents)
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    top_indices = similarity.argsort()[-2:][::-1]
    return [list(job_roles.keys())[i] for i in top_indices]

def get_skill_gap(skills, dream_role):
    """Calculate skill gap for dream role"""
    if dream_role in job_roles:
        required = set(job_roles[dream_role]["required_skills"])
        current = set(skills)
        missing = list(required - current)
        return {"current": len(current & required), "total": len(required), "missing": missing}
    return {"current": 0, "total": 0, "missing": []}

@app.route('/')
def index():
    return render_template('index.html', progress=progress)

@app.route('/upload', methods=['POST'])
def upload_file():
    # Validate file presence
    if 'resume' not in request.files:
        return render_template('index.html', error="No file uploaded. Please select a file.", progress=progress)

    file = request.files['resume']
    if file.filename == '':
        return render_template('index.html', error="No file selected. Please choose a file.", progress=progress)

    # Validate file extension
    allowed_extensions = {'.pdf', '.docx'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return render_template('index.html', error="Invalid file type. Please upload a PDF or DOCX file.", progress=progress)

    # Save file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Extract text, sections, and skills
    resume_text = extract_resume_text(filepath)
    if not resume_text:
        return render_template('index.html', error="Failed to extract text from resume. Try another file.", progress=progress)
    
    sections = parse_resume_sections(resume_text)
    skills = extract_skills_from_text(resume_text)
    dream_role = request.form.get('dream_role', '').strip()
    ats_score = calculate_ats_score(resume_text, skills)

    # Match jobs
    matched_jobs = match_jobs(skills) if skills and "No skills detected" not in skills else []

    # Skill gap for visualization
    skill_gap = get_skill_gap(skills, dream_role) if dream_role in job_roles else {}

    # Mock job postings (replace with API in production)
    job_postings = [
        {"title": f"{matched_jobs[0]} at Tech Corp", "url": "https://example.com/job1"} if matched_jobs else {"title": "No jobs matched", "url": "#"},
        {"title": f"{matched_jobs[1]} at Data Inc", "url": "https://example.com/job2"} if len(matched_jobs) > 1 else {"title": "No jobs matched", "url": "#"}
    ]

    # Create Gemini prompt
    prompt = f"""
    Return a JSON object with:
    - top_jobs: List of 2 job roles with a brief explanation (use {matched_jobs} if available, else suggest based on skills).
    - resume_feedback: 3 specific suggestions to improve the resume based on sections: {json.dumps(sections)}.
    - courses: 3 course recommendations to enhance skills: {skills}.
    - dream_pathway: If a dream role ({dream_role}) is provided, list 3 skills to learn and 2 courses for it; otherwise, return empty.
    - ats_tips: 2 tips to improve ATS score based on current score ({ats_score}).
    Be friendly and concise.
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        result = json.loads(response.text.strip('```json\n').strip('```'))
        # Sanitize result text fields
        for job in result.get("top_jobs", []):
            if isinstance(job, dict):
                job["name"] = sanitize_text(job.get("name", ""))
                job["explanation"] = sanitize_text(job.get("explanation", ""))
        result["resume_feedback"] = [sanitize_text(fb) for fb in result.get("resume_feedback", [])]
        result["courses"] = [sanitize_text(c) for c in result.get("courses", [])]
        if "dream_pathway" in result:
            result["dream_pathway"]["skills"] = [sanitize_text(s) for s in result["dream_pathway"].get("skills", [])]
            result["dream_pathway"]["courses"] = [sanitize_text(c) for c in result["dream_pathway"].get("courses", [])]
        result["ats_tips"] = [sanitize_text(t) for t in result.get("ats_tips", [])]
    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")
        # Convert matched_jobs to dictionary format
        top_jobs = [{"name": sanitize_text(job), "explanation": sanitize_text(f"Suitable based on skills: {', '.join(skills)}")} for job in matched_jobs] if matched_jobs else []
        result = {
            "top_jobs": top_jobs,
            "resume_feedback": [sanitize_text("Unable to generate feedback due to API error.")],
            "courses": [],
            "dream_pathway": {},
            "ats_tips": [sanitize_text("Check for API connectivity issues."), sanitize_text("Ensure resume has relevant keywords.")]
        }
        error = f"Error generating content: {str(e)}"

    # Update progress
    user_id = str(uuid.uuid4())[:8]  # Simple user ID for demo
    progress[user_id] = {
        "skills": [sanitize_text(s) for s in skills],
        "courses": result.get("courses", []),
        "completed_courses": []
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)

    # Sanitize data for PDF report
    sanitized_data = {
        "filename": sanitize_text(filename),
        "skills": [sanitize_text(s) for s in skills],
        "sections": {k: [sanitize_text(c) for c in v] for k, v in sections.items()},
        "ats_score": ats_score,
        "result": result,
        "job_postings": [{"title": sanitize_text(j["title"]), "url": sanitize_text(j["url"])} for j in job_postings],
        "dream_role": sanitize_text(dream_role)
    }

    # Generate PDF report
    report_path = os.path.join(app.config['REPORTS_FOLDER'], f"report_{filename}.pdf")
    try:
        generate_pdf_report(sanitized_data, report_path)
    except Exception as e:
        logger.error(f"PDF generation error: {str(e)}")
        error = f"Failed to generate PDF report: {str(e)}"

    return render_template(
        'index.html',
        filename=filename,
        skills=skills,
        sections=sections,
        ats_score=ats_score,
        result=result,
        job_postings=job_postings,
        skill_gap=skill_gap,
        report_path=report_path,
        user_id=user_id,
        progress=progress,
        error=error if 'error' in locals() else None
    )

@app.route('/update_progress/<user_id>', methods=['POST'])
def update_progress(user_id):
    course = request.form.get('course')
    if user_id in progress and course in progress[user_id]["courses"]:
        progress[user_id]["completed_courses"].append(sanitize_text(course))
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress, f)
    return render_template('index.html', progress=progress)

@app.route('/download_report/<path:report_path>')
def download_report(report_path):
    return send_file(report_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)