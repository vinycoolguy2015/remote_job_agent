import os
import json
import uuid
import traceback
import boto3
from datetime import datetime

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

print("=== Job Application Coach Starting ===")
print(f"AWS_REGION: {os.environ.get('AWS_REGION', 'NOT SET')}")
print(f"AGENTCORE_MEMORY_ID: {os.environ.get('AGENTCORE_MEMORY_ID', 'NOT SET')}")
print(f"SERPER_API_KEY: {'SET' if os.environ.get('SERPER_API_KEY') else 'NOT SET'}")
print(f"S3_RESUME_BUCKET: {os.environ.get('S3_RESUME_BUCKET', 'NOT SET')}")

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from job_application_coach.tools.s3_resume_tool import S3ResumeTool

serper_tool = SerperDevTool(api_key=os.environ.get("SERPER_API_KEY", ""))
browser_tool = ScrapeWebsiteTool()
s3_resume_tool = S3ResumeTool()
llm = LLM(model="bedrock/us.amazon.nova-pro-v1:0")

# Bedrock AgentCore Memory client
memory_client = boto3.client('bedrock-agentcore', region_name=os.environ.get("AWS_REGION", "us-east-1"))
MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "job_coach_memory")
print("=== Initialization complete ===")


@CrewBase
class JobApplicationCoach():
    """Job Application Coach crew"""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def job_finder(self) -> Agent:
        return Agent(
            config=self.agents_config['job_finder'],
            verbose=True,
            tools=[serper_tool, browser_tool],
            llm=llm
        )

    @agent
    def resume_tailor(self) -> Agent:
        return Agent(
            config=self.agents_config['resume_tailor'],
            verbose=True,
            tools=[serper_tool, browser_tool, s3_resume_tool],
            llm=llm
        )

    @task
    def find_jobs_task(self) -> Task:
        return Task(
            config=self.tasks_config['find_jobs_task'],
        )

    @task
    def tailor_resume_task(self) -> Task:
        return Task(
            config=self.tasks_config['tailor_resume_task'],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )


def get_excluded_companies(user_id: str) -> list:
    """Retrieve list of companies the user has excluded from Bedrock memory."""
    try:
        previous_events = memory_client.list_events(
            memoryId=MEMORY_ID,
            actorId=user_id,
            sessionId=f"{user_id}_exclusions",
            maxResults=50
        )
        excluded = []
        for event in previous_events.get('events', []):
            for item in event.get('payload', []):
                conv = item.get('conversational', {})
                content = conv.get('content', {}).get('text', '')
                if content.startswith("EXCLUDE:"):
                    excluded.append(content.replace("EXCLUDE:", "").strip().lower())
        return excluded
    except Exception as e:
        print(f"Error retrieving memory: {e}")
        return []


def save_excluded_company(user_id: str, company_name: str):
    """Save a company exclusion to Bedrock memory."""
    try:
        memory_client.create_event(
            memoryId=MEMORY_ID,
            actorId=user_id,
            sessionId=f"{user_id}_exclusions",
            eventTimestamp=datetime.utcnow(),
            payload=[
                {
                    "conversational": {
                        "content": {"text": f"EXCLUDE:{company_name}"},
                        "role": "USER"
                    }
                },
                {
                    "conversational": {
                        "content": {"text": f"Noted. Jobs from {company_name} will be hidden in future searches."},
                        "role": "ASSISTANT"
                    }
                }
            ],
            clientToken=str(uuid.uuid4())
        )
    except Exception as e:
        print(f"Error saving to memory: {e}")


def filter_excluded_jobs(jobs: list, excluded_companies: list) -> list:
    """Remove jobs from excluded companies."""
    if not excluded_companies:
        return jobs
    return [
        job for job in jobs
        if job.get("company", "").lower() not in excluded_companies
    ]


@app.entrypoint
def agent_invocation(payload, context):
    """Handler for agent invocation from AgentCore Gateway"""
    print(f'Payload: {payload}')
    print(f'Context: {context}')
    try:
        # Handle nested payload format from Gateway
        # Gateway may send: {"action": "find_jobs", "parameters": {"topic": "..."}}
        # Or flat: {"action": "find_jobs", "search_term": "aws devops"}
        if "parameters" in payload:
            params = payload.get("parameters", {})
            action = payload.get("action", params.get("action", "find_jobs"))
        else:
            params = payload
            action = payload.get("action", "find_jobs")

        user_id = params.get("user_id", payload.get("user_id", "default"))

        if action == "find_jobs":
            # Retrieve excluded companies from Bedrock memory
            excluded = get_excluded_companies(user_id)
            print(f"Excluded companies for {user_id}: {excluded}")

            coach = JobApplicationCoach()
            crew = Crew(
                agents=[coach.job_finder()],
                tasks=[coach.find_jobs_task()],
                process=Process.sequential,
                verbose=True,
            )
            result = crew.kickoff()
            try:
                raw = str(result.raw)
                # Strip markdown code block wrapper if present
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()
                jobs = json.loads(raw)
            except (json.JSONDecodeError, IndexError):
                jobs = [{"title": "Parse error", "company": "N/A", "url": "#", "raw": str(result.raw)}]

            # Filter out excluded companies
            filtered_jobs = filter_excluded_jobs(jobs, excluded)
            return {"result": {"jobs": filtered_jobs, "excluded_companies": excluded}}

        elif action == "tailor_resume":
            job_url = params.get("job_url", payload.get("job_url", ""))
            resume_content = s3_resume_tool._run(user_id=user_id)

            coach = JobApplicationCoach()
            crew = Crew(
                agents=[coach.resume_tailor()],
                tasks=[coach.tailor_resume_task()],
                process=Process.sequential,
                verbose=True,
            )
            result = crew.kickoff(inputs={"job_url": job_url, "resume_content": resume_content})
            try:
                raw = str(result.raw)
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"resume": json.loads(resume_content), "interview_tips": ["Could not parse agent output"]}
            return {"result": parsed}

        elif action == "exclude_company":
            company_name = params.get("company", payload.get("company", ""))
            if company_name:
                save_excluded_company(user_id, company_name)
                return {"result": {"message": f"'{company_name}' excluded from future searches."}}
            return {"error": "No company name provided"}

        elif action == "ping":
            return {"result": {"message": "pong", "received_payload": payload}}

        else:
            return {"error": f"Unknown action: {action}"}

    except Exception as e:
        print(f'Exception occurred: {e}')
        print(traceback.format_exc())
        return {"error": f"An error occurred: {str(e)}"}


if __name__ == "__main__":
    app.run(port=8080)
