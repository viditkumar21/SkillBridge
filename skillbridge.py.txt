from sentence_transformers import SentenceTransformer, util
import pandas as pd
import re

# Load the SBERT model for sentence similarity
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')  # Lightweight and effective SBERT model

# Predefined set of keywords for common skills/topics
skill_keywords = {
    "python", "node.js", "rest", "docker", "aws", "c++", "react", "css", "ci/cd", "machine learning", "sql", "java", "linux"
}

# Function to clean and extract keywords from text
def extract_keywords(text):
    # Lowercase and remove punctuation
    words = re.findall(r'\b\w+\b', text.lower())
    return set(word for word in words if word in skill_keywords)

# Function to identify gaps and provide links for study materials
def identify_gaps_with_links(job_desc, resume):
    job_keywords = extract_keywords(job_desc)
    resume_keywords = extract_keywords(resume)
    
    # Identify gap topics (present in job description but not in resume)
    gaps = job_keywords - resume_keywords
    
    # Dictionary of study material links
    study_material_links = {
        "python": "https://www.learnpython.org/",
        "node.js": "https://nodejs.dev/learn",
        "rest": "https://restfulapi.net/",
        "docker": "https://www.docker.com/101-tutorial",
        "aws": "https://aws.amazon.com/training/",
        "c++": "https://www.learncpp.com/",
        "react": "https://reactjs.org/docs/getting-started.html",
        "css": "https://developer.mozilla.org/en-US/docs/Web/CSS",
        "ci/cd": "https://www.redhat.com/en/topics/devops/what-is-ci-cd",
        "machine learning": "https://www.coursera.org/learn/machine-learning",
        "sql": "https://www.w3schools.com/sql/",
        "java": "https://www.javatpoint.com/java-tutorial",
        "linux": "https://www.edx.org/learn/linux"
    }
    
    gap_topics = ", ".join(gaps)
    study_links_combined = ", ".join(study_material_links[topic] for topic in gaps if topic in study_material_links)
    
    return gap_topics, study_links_combined

# Function to calculate match score using SBERT for job description and resume
def predict_match_score_percentage_sbert(job_desc, resume):
    # Encode sentences to get their embeddings
    job_embedding = model.encode(job_desc, convert_to_tensor=True)
    resume_embedding = model.encode(resume, convert_to_tensor=True)
    
    # Calculate cosine similarity between job description and resume embeddings
    similarity = util.pytorch_cos_sim(job_embedding, resume_embedding).item()
    return similarity * 100  # Convert similarity to percentage

# Load input CSV file
input_file_path = "job_openings_data.csv"  # Update with your actual file path
df = pd.read_csv(input_file_path)

# Calculate match scores using SBERT for each row in the CSV and add gap topics and links
df["Match Score (%)"] = df.apply(
    lambda row: predict_match_score_percentage_sbert(row["job_description"], row["resume"]),
    axis=1
)

# Identify gaps and add study links using the updated gap identification function
df[["Gap Topics", "Study Material Link"]] = df.apply(
    lambda row: pd.Series(identify_gaps_with_links(row["job_description"], row["resume"])),
    axis=1
)

# Sort results by Match Score in descending order
df = df.sort_values(by="Match Score (%)", ascending=False)

# Save the results to a new CSV file
output_file_path = "output_file_sbert.csv"  # Update with desired output path
df.to_csv(output_file_path, index=False)

print(f"Match scores using SBERT, gap topics, and study material links have been saved to {output_file_path}")
