from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import requests
import json
import os
from datetime import datetime

st.set_page_config(page_title="Job Application Coach", page_icon="💼", layout="wide")

st.markdown("""
<style>
.main-header {
    background: linear-gradient(90deg, #1a365d, #2b6cb0, #4299e1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.5rem;
    font-weight: bold;
    text-align: center;
}
.job-card {
    background: #f7fafc;
    border-left: 4px solid #2b6cb0;
    padding: 1rem;
    border-radius: 8px;
    margin: 0.5rem 0;
}
.tip-card {
    background: #f0fff4;
    border-left: 4px solid #38a169;
    padding: 1rem;
    border-radius: 8px;
    margin: 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">Job Application Coach</h1>', unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#666;'>Find AWS DevOps jobs on WeWorkRemotely and get a tailored resume</p>", unsafe_allow_html=True)

GATEWAY_ENDPOINT = os.environ.get("GATEWAY_ENDPOINT", "")
TOKEN_URL = os.environ.get("TOKEN_URL", "")
CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET", "")


def get_m2m_token():
    """Get machine-to-machine JWT from Cognito using client_credentials grant."""
    response = requests.post(
        TOKEN_URL,
        data=f"grant_type=client_credentials&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def call_gateway(action: str, payload: dict) -> dict:
    """Call AgentCore Gateway with M2M JWT auth."""
    token = get_m2m_token()
    st.write(f"Token acquired. Calling gateway: {action}...")
    response = requests.post(
        f"{GATEWAY_ENDPOINT}/job-application-coach/invocations",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"action": action, **payload},
        timeout=300,
    )
    st.write(f"Gateway response status: {response.status_code}")
    response.raise_for_status()
    data = response.json()
    st.write("Raw response:", data)
    return data.get("result", data)


# Step 1: Find Jobs
st.markdown("### Step 1: Find AWS DevOps Jobs")

if st.button("Search WeWorkRemotely", type="primary", use_container_width=True):
    with st.spinner("Searching for AWS DevOps jobs on WeWorkRemotely..."):
        try:
            result = call_gateway("find_jobs", {"search_term": "aws devops"})
            st.session_state.jobs = result.get("jobs", [])
            excluded = result.get("excluded_companies", [])
            if excluded:
                st.info(f"Hiding jobs from: {', '.join(excluded)} (based on your preferences)")
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.info("Make sure GATEWAY_ENDPOINT and Cognito env vars are set.")

# Display job listings
if "jobs" in st.session_state and st.session_state.jobs:
    st.markdown("### Found Jobs:")
    for i, job in enumerate(st.session_state.jobs):
        col_job, col_btn = st.columns([4, 1])
        with col_job:
            st.markdown(f"""
            <div class="job-card">
                <strong>{job.get('title', 'N/A')}</strong><br>
                <span style="color:#4a5568;">{job.get('company', 'N/A')}</span><br>
                <a href="{job.get('url', '#')}" target="_blank">View listing</a>
            </div>
            """, unsafe_allow_html=True)
        with col_btn:
            if st.button("Not Interested", key=f"exclude_{i}"):
                company = job.get("company", "")
                if company:
                    try:
                        call_gateway("exclude_company", {"company": company})
                        st.session_state.jobs = [
                            j for j in st.session_state.jobs
                            if j.get("company", "").lower() != company.lower()
                        ]
                        st.success(f"'{company}' excluded. Won't show in future searches.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

    # Step 2: Pick a job and tailor resume
    st.markdown("---")
    st.markdown("### Step 2: Tailor Your Resume")

    job_options = [f"{j['title']} at {j['company']}" for j in st.session_state.jobs]
    selected_idx = st.selectbox("Select a job to apply for:", range(len(job_options)), format_func=lambda i: job_options[i])

    if st.button("Tailor My Resume", type="primary"):
        selected_job = st.session_state.jobs[selected_idx]
        with st.spinner(f"Tailoring resume for {selected_job['title']} at {selected_job['company']}..."):
            try:
                result = call_gateway("tailor_resume", {"job_url": selected_job["url"]})

                resume_data = result.get("resume", {})
                interview_tips = result.get("interview_tips", [])

                st.session_state.resume_data = resume_data
                st.session_state.interview_tips = interview_tips

            except Exception as e:
                st.error(f"Error: {str(e)}")

# Display results
if "resume_data" in st.session_state:
    st.markdown("---")
    st.markdown("### Your Tailored Resume")

    resume = st.session_state.resume_data
    st.markdown(f"**{resume.get('name', '')}** | {resume.get('email', '')} | {resume.get('phone', '')}")
    st.markdown(f"*{resume.get('summary', '')}*")

    st.markdown("**Skills:** " + ", ".join(resume.get("skills", [])))

    for exp in resume.get("experience", []):
        st.markdown(f"**{exp['role']}** at {exp['company']} ({exp['duration']})")
        for bullet in exp.get("bullets", []):
            st.markdown(f"- {bullet}")

    # Generate PDF
    st.markdown("---")
    if st.button("Generate Professional PDF", type="primary"):
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
            from job_application_coach.pdf_generator import generate_resume_pdf
            pdf_path = generate_resume_pdf(resume, "output/tailored_resume.pdf")
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            st.download_button(
                label="Download Resume PDF",
                data=pdf_bytes,
                file_name="tailored_resume.pdf",
                mime="application/pdf",
            )
            st.success("PDF generated successfully!")
        except Exception as e:
            st.error(f"PDF generation error: {str(e)}")
            st.info("Make sure weasyprint is installed: brew install weasyprint (Mac)")

    # Interview tips
    if st.session_state.get("interview_tips"):
        st.markdown("---")
        st.markdown("### Interview Tips")
        for tip in st.session_state.interview_tips:
            st.markdown(f"""<div class="tip-card">{tip}</div>""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### How It Works")
    st.markdown("""
    1. **Search** - Agent browses WeWorkRemotely for AWS DevOps jobs
    2. **Select** - Pick a job you want to apply for
    3. **Tailor** - Agent reads your base resume from S3 and rewrites it for the job
    4. **Download** - Get a professional PDF resume
    5. **Prepare** - Get interview tips based on company research
    """)

    st.markdown("---")
    st.markdown("### Architecture")
    st.markdown("""
    - **Gateway**: Single HTTPS endpoint
    - **Auth**: Cognito M2M (client_credentials)
    - **IAM**: S3 resume storage
    - **API Key**: Serper for company research
    - **Browser**: WeWorkRemotely scraping
    """)
