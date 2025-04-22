from fpdf import FPDF
import os
import logging
import unicodedata
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sanitize_text(text):
    """Normalize Unicode characters and replace problematic ones with ASCII equivalents"""
    if not isinstance(text, str):
        text = str(text)
    try:
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        text = re.sub(r'[^\x00-\x7F]+', '-', text)
        return text
    except Exception as e:
        logger.error(f"Error sanitizing text: {str(e)}")
        return ""

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Career Counselor Skill Bridge Report', 0, 1, 'C')

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf_report(data, output_path):
    """Generate a PDF report from analysis data"""
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)

    try:
        # Title
        pdf.cell(0, 10, f'Analysis for: {sanitize_text(data["filename"])}', 0, 1)
        pdf.ln(5)

        # ATS Score
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f'ATS Compatibility Score: {data["ats_score"]}/100', 0, 1)
        pdf.set_font('Arial', '', 12)
        pdf.ln(5)

        # Skills
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Extracted Skills:', 0, 1)
        pdf.set_font('Arial', '', 12)
        for skill in data["skills"]:
            pdf.cell(0, 10, f'- {sanitize_text(skill)}', 0, 1)
        pdf.ln(5)

        # Sections
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Resume Sections:', 0, 1)
        pdf.set_font('Arial', '', 12)
        for section, content in data["sections"].items():
            if content:
                pdf.cell(0, 10, sanitize_text(section), 0, 1)
                for item in content:
                    pdf.cell(0, 10, f'  - {sanitize_text(item)}', 0, 1)
        pdf.ln(5)

        # Recommendations
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Recommendations:', 0, 1)
        pdf.set_font('Arial', '', 12)
        if data["result"].get("top_jobs"):
            pdf.cell(0, 10, 'Top Job Roles:', 0, 1)
            for job in data["result"]["top_jobs"]:
                if isinstance(job, str):
                    job_text = sanitize_text(job)
                else:
                    job_text = f'{sanitize_text(job.get("name", "Unknown Job"))}: {sanitize_text(job.get("explanation", "No explanation provided"))}'
                pdf.cell(0, 10, f'- {job_text}', 0, 1)
        else:
            pdf.cell(0, 10, '- No job roles recommended.', 0, 1)
        if data["job_postings"]:
            pdf.cell(0, 10, 'Job Postings:', 0, 1)
            for job in data["job_postings"]:
                pdf.cell(0, 10, f'- {sanitize_text(job["title"])} ({sanitize_text(job["url"])})', 0, 1)
        if data["result"].get("resume_feedback"):
            pdf.cell(0, 10, 'Resume Feedback:', 0, 1)
            for feedback in data["result"]["resume_feedback"]:
                pdf.cell(0, 10, f'- {sanitize_text(feedback)}', 0, 1)
        if data["result"].get("ats_tips"):
            pdf.cell(0, 10, 'ATS Tips:', 0, 1)
            for tip in data["result"]["ats_tips"]:
                pdf.cell(0, 10, f'- {sanitize_text(tip)}', 0, 1)
        if data["result"].get("courses"):
            pdf.cell(0, 10, 'Recommended Courses:', 0, 1)
            for course in data["result"]["courses"]:
                pdf.cell(0, 10, f'- {sanitize_text(course)}', 0, 1)
        if data["result"].get("dream_pathway", {}).get("skills") or data["result"].get("dream_pathway", {}).get("courses"):
            pdf.cell(0, 10, f'Dream Role Pathway ({sanitize_text(data["dream_role"])}):', 0, 1)
            pdf.cell(0, 10, 'Skills to Learn:', 0, 1)
            for skill in data["result"]["dream_pathway"].get("skills", []):
                pdf.cell(0, 10, f'- {sanitize_text(skill)}', 0, 1)
            pdf.cell(0, 10, 'Courses:', 0, 1)
            for course in data["result"]["dream_pathway"].get("courses", []):
                pdf.cell(0, 10, f'- {sanitize_text(course)}', 0, 1)

        pdf.output(output_path)
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        raise