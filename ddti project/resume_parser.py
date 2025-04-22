import os
import fitz  # PyMuPDF
from docx import Document
import spacy
from spacy.matcher import PhraseMatcher
import re
import unicodedata

def sanitize_text(text):
    """Normalize Unicode characters and replace problematic ones with ASCII equivalents"""
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\x00-\x7F]+', '-', text)
    return text

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file using PyMuPDF"""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return sanitize_text(text)
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return ""

def extract_text_from_docx(docx_path):
    """Extract text from a DOCX file using python-docx"""
    try:
        doc = Document(docx_path)
        text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())
        return sanitize_text(text)
    except Exception as e:
        print(f"Error extracting DOCX: {e}")
        return ""

def extract_resume_text(file_path):
    """Extract text from the provided resume file (PDF or DOCX)"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext == '.docx':
        return extract_text_from_docx(file_path)
    else:
        return ""

def parse_resume_sections(text):
    """Parse resume into sections (Education, Experience, Skills)"""
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)
    sections = {"Education": [], "Experience": [], "Skills": []}
    current_section = None

    section_keywords = {
        "Education": ["education", "academic", "degree", "university"],
        "Experience": ["experience", "work history", "employment", "professional"],
        "Skills": ["skills", "competencies", "abilities"]
    }

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        for section, keywords in section_keywords.items():
            if any(re.search(r'\b' + k + r'\b', line, re.IGNORECASE) for k in keywords):
                current_section = section
                break
        if current_section and line not in sections[current_section]:
            sections[current_section].append(line)

    return sections

def extract_skills_from_text(text):
    """Extract skills from resume text using spaCy"""
    try:
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text)
        matcher = PhraseMatcher(nlp.vocab)
        
        # Expanded skills database
        skills_db = [
            "Python", "Java", "SQL", "Excel", "Power BI", "Tableau", "HTML", 
            "CSS", "JavaScript", "React", "Git", "Pandas", "Scikit-learn", 
            "TensorFlow", "Numpy", "communication", "teamwork", "leadership", 
            "marketing", "finance", "project management", "Agile", "Scrum",
            "cloud computing", "AWS", "Docker", "SEO", "Google Analytics"
        ]
        
        # Add skills as patterns
        patterns = [nlp(skill) for skill in skills_db]
        matcher.add("SKILLS", patterns)
        
        found = set()
        matches = matcher(doc)
        for match_id, start, end in matches:
            found.add(doc[start:end].text)
        
        # Fallback regex for robustness
        for skill in skills_db:
            if re.search(r'\b' + re.escape(skill) + r'\b', text, re.IGNORECASE):
                found.add(skill)
        
        return list(found) if found else ["No skills detected"]
    except Exception as e:
        print(f"Error extracting skills: {e}")
        return ["Error extracting skills"]