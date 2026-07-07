import json
import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML


def generate_resume_pdf(resume_data: dict, output_path: str = "output/resume.pdf") -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    template_dir = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("resume_template.html")

    html_content = template.render(resume=resume_data)

    HTML(string=html_content).write_pdf(output_path)

    return output_path


if __name__ == "__main__":
    sample = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1-555-0100",
        "summary": "Senior DevOps Engineer with 8+ years of experience.",
        "skills": ["AWS", "Terraform", "Kubernetes", "Docker"],
        "experience": [
            {
                "company": "TechCorp",
                "role": "Senior DevOps Engineer",
                "duration": "2021 - Present",
                "bullets": ["Managed AWS infra for 10M+ requests/day"]
            }
        ],
        "education": {"degree": "B.S. CS", "school": "UC Berkeley", "year": "2018"}
    }
    print(generate_resume_pdf(sample))
