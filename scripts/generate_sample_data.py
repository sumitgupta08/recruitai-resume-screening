#!/usr/bin/env python3
"""
Sample Dataset Generator for RecruitAI.

Generates realistic test resumes (as text) and job descriptions
for development and testing purposes.

Usage:
    python scripts/generate_sample_data.py
    python scripts/generate_sample_data.py --count 20 --output ./sample_data
"""
import argparse
import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

# ── Sample data pools ────────────────────────────────────────
NAMES = [
    "Priya Sharma", "James O'Brien", "Mei-Ling Chen", "Arjun Kapoor",
    "Sofia Rossi", "Marcus Johnson", "Fatima Al-Hassan", "Dmitri Volkov",
    "Amara Diallo", "Chen Wei", "Isabella Novak", "Kwame Mensah",
    "Nadia Petersen", "Ravi Nair", "Elena Kovacs", "Omar Farouk",
    "Yuki Tanaka", "Laura Bianchi", "Samuel Torres", "Aisha Okonkwo",
]

SKILLS_BACKEND = ["Python", "FastAPI", "Django", "Flask", "PostgreSQL", "MySQL",
                  "Redis", "Docker", "Kubernetes", "AWS", "GCP", "REST API",
                  "Microservices", "CI/CD", "Git"]
SKILLS_ML = ["Python", "TensorFlow", "PyTorch", "scikit-learn", "Pandas", "NumPy",
             "Hugging Face", "BERT", "spaCy", "OpenCV", "SQL", "Apache Spark"]
SKILLS_FRONTEND = ["React", "TypeScript", "JavaScript", "Vue.js", "Next.js",
                   "Node.js", "GraphQL", "CSS", "HTML", "Docker", "Git"]
SKILLS_DATA = ["SQL", "Python", "Apache Spark", "Kafka", "Airflow", "dbt",
               "Snowflake", "BigQuery", "Pandas", "Tableau", "PostgreSQL"]

COMPANIES = ["TechCorp", "DataSystems Inc", "CloudNative Ltd", "AIVentures",
             "FinTech Pro", "StartupXYZ", "GlobalSoft", "InnovateLabs",
             "DeepMind Works", "ScaleUp Solutions"]

UNIVERSITIES = ["MIT", "Stanford University", "UC Berkeley", "Carnegie Mellon",
                "IIT Delhi", "University of Cambridge", "ETH Zurich",
                "University of Toronto", "NUS Singapore", "TU Munich"]

LOCATIONS = ["San Francisco, CA", "New York, NY", "London, UK", "Berlin, Germany",
             "Bangalore, India", "Remote", "Singapore", "Toronto, Canada",
             "Amsterdam, Netherlands", "Sydney, Australia"]

DEGREES = ["B.Sc. Computer Science", "M.Sc. Computer Science",
           "B.Tech. Information Technology", "M.Sc. Data Science",
           "B.Sc. Mathematics", "Ph.D. Machine Learning", "MBA + B.Sc. CS"]


def random_date_range(years_ago_max=15, years_ago_min=0):
    end = datetime.now() - timedelta(days=365 * years_ago_min)
    start = end - timedelta(days=365 * random.randint(1, 4))
    return start.strftime("%b %Y"), end.strftime("%b %Y")


def generate_resume_text(name: str, skill_pool: list, exp_years: int, degree: str) -> str:
    """Generate a realistic resume as plain text."""
    clean = name.lower().replace(' ', '.').replace("'", '')
    email = f"{clean}@email.com"
    phone = f"+1 {random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
    location = random.choice(LOCATIONS)
    skills = random.sample(skill_pool, min(len(skill_pool), random.randint(6, 12)))
    company1 = random.choice(COMPANIES)
    company2 = random.choice([c for c in COMPANIES if c != company1])
    university = random.choice(UNIVERSITIES)
    grad_year = datetime.now().year - exp_years - random.randint(0, 2)

    s1, e1 = random_date_range(exp_years, max(0, exp_years - 3))
    s2, e2 = random_date_range(max(0, exp_years - 3) + 1, 0)

    resume = f"""{name}
{email} | {phone} | {location}
LinkedIn: linkedin.com/in/{name.lower().replace(' ', '-').replace("'", '')}

SUMMARY
Experienced software professional with {exp_years}+ years of industry experience.
Passionate about building scalable systems and delivering high-quality solutions.

EXPERIENCE

Senior Software Engineer — {company2}
{s2} – Present
• Led development of microservices architecture serving 1M+ requests/day
• Reduced deployment time by 60% through CI/CD pipeline optimisation
• Mentored team of 4 junior engineers
• Technologies: {', '.join(random.sample(skills, min(len(skills), 5)))}

Software Engineer — {company1}
{s1} – {e1}
• Developed and maintained backend APIs for core product features
• Improved database query performance by 40% through indexing and query optimisation
• Collaborated with cross-functional teams on product requirements
• Technologies: {', '.join(random.sample(skills, min(len(skills), 4)))}

EDUCATION

{degree}
{university} — {grad_year}
GPA: {round(random.uniform(3.2, 4.0), 2)}/4.0

SKILLS
{', '.join(skills)}

PROJECTS

Open Source Contributions
• Contributed to {random.choice(['FastAPI', 'spaCy', 'scikit-learn', 'PyTorch'])} with bug fixes and documentation
• Built {random.choice(['REST API framework', 'ML pipeline toolkit', 'data visualisation library'])} (500+ GitHub stars)

Personal Project — {random.choice(['Real-time Analytics Dashboard', 'NLP Text Classifier', 'Distributed Cache System'])}
• {random.choice(['Achieved 99.9% uptime', 'Reduced latency by 50%', 'Processed 10GB+ data daily'])}
• Technologies: {', '.join(random.sample(skills, min(len(skills), 3)))}

CERTIFICATIONS
• {random.choice(['AWS Certified Solutions Architect', 'Google Professional Data Engineer', 'CKA - Certified Kubernetes Administrator', 'TensorFlow Developer Certificate'])}
"""
    return resume.strip()


JOBS = [
    {
        "title": "Senior Backend Engineer",
        "company": "TechCorp",
        "description": """We are looking for a Senior Backend Engineer to join our platform team.
You will design and build scalable APIs, work closely with the data team, and help architect
our next-generation microservices infrastructure. You will own critical backend systems
that process millions of requests daily. We value clean code, strong testing culture,
and collaborative problem solving.""",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "AWS"],
        "preferred_skills": ["Kubernetes", "Go", "Apache Kafka"],
        "required_experience_years": 5,
        "required_education": "Bachelor's",
        "location": "Remote",
    },
    {
        "title": "Machine Learning Engineer",
        "company": "DataAI Inc",
        "description": """Join our ML platform team to build production ML systems at scale.
You will work on model training pipelines, feature stores, model serving infrastructure,
and MLOps tooling. We use transformer models, fine-tuning, and vector databases extensively.
The ideal candidate has strong Python skills and experience taking models from research to production.""",
        "required_skills": ["Python", "PyTorch", "scikit-learn", "Docker", "SQL", "Apache Spark"],
        "preferred_skills": ["Kubernetes", "Hugging Face", "Airflow", "MLflow"],
        "required_experience_years": 3,
        "required_education": "Master's",
        "location": "San Francisco, CA",
    },
    {
        "title": "Full-Stack Developer",
        "company": "Startify",
        "description": """We need a versatile Full-Stack Developer who can work across our entire tech stack.
You will build React frontends, Node.js APIs, and work with our PostgreSQL database.
We are a fast-moving startup so you need to be comfortable with ambiguity and able to
ship features quickly without sacrificing quality.""",
        "required_skills": ["React", "TypeScript", "Node.js", "PostgreSQL", "Docker"],
        "preferred_skills": ["GraphQL", "Redis", "AWS", "Next.js"],
        "required_experience_years": 2,
        "required_education": "Bachelor's",
        "location": "New York, NY",
    },
    {
        "title": "Data Engineer",
        "company": "AnalyticsPro",
        "description": """Build and maintain our data infrastructure serving analytics for 50M+ users.
You will design ETL pipelines, maintain our Snowflake data warehouse, orchestrate workflows
with Airflow, and work closely with data scientists and analysts. Strong SQL and Python
skills are essential.""",
        "required_skills": ["Python", "SQL", "Apache Spark", "Airflow", "dbt", "Snowflake"],
        "preferred_skills": ["Kafka", "BigQuery", "Terraform", "Kubernetes"],
        "required_experience_years": 3,
        "required_education": "Bachelor's",
        "location": "London, UK",
    },
]


def main():
    parser = argparse.ArgumentParser(description="Generate sample RecruitAI test data")
    parser.add_argument("--count", type=int, default=10, help="Number of resumes to generate")
    parser.add_argument("--output", default="./sample_data", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    resumes_dir = output_dir / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)

    # Generate resumes
    skill_pools = [SKILLS_BACKEND, SKILLS_ML, SKILLS_FRONTEND, SKILLS_DATA]
    generated_resumes = []

    for i in range(args.count):
        name = random.choice(NAMES)
        skill_pool = random.choice(skill_pools)
        exp_years = random.randint(1, 12)
        degree = random.choice(DEGREES)

        text = generate_resume_text(name, skill_pool, exp_years, degree)
        file_name = f"resume_{i+1:03d}_{name.lower().replace(' ', '_').replace(chr(39), '')}.txt"
        file_path = resumes_dir / file_name

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

        generated_resumes.append({
            "file": file_name,
            "candidate": name,
            "experience_years": exp_years,
            "degree": degree,
        })

    # Write job descriptions JSON
    jobs_path = output_dir / "job_descriptions.json"
    with open(jobs_path, "w") as f:
        json.dump(JOBS, f, indent=2)

    # Write manifest
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "resume_count": args.count,
        "job_count": len(JOBS),
        "resumes": generated_resumes,
        "jobs": [j["title"] for j in JOBS],
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"✓ Generated {args.count} resumes → {resumes_dir}")
    print(f"✓ Generated {len(JOBS)} job descriptions → {jobs_path}")
    print(f"✓ Manifest → {output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
