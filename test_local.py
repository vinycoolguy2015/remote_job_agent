"""Local test for the CrewAI job finder - no AgentCore runtime needed."""
from dotenv import load_dotenv
load_dotenv()

from crewai import Agent, Crew, Process, Task, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
import os
import json

llm = LLM(model="bedrock/us.amazon.nova-pro-v1:0")
serper_tool = SerperDevTool(api_key=os.environ.get("SERPER_API_KEY", ""))
browser_tool = ScrapeWebsiteTool()

print("=" * 60)
print("LOCAL TEST: Job Finder Crew")
print("=" * 60)

job_finder = Agent(
    role="Senior DevOps Job Researcher",
    goal="Find AWS DevOps remote job listings from WeWorkRemotely.com",
    backstory="You are an expert job market analyst specializing in DevOps and cloud engineering roles.",
    verbose=True,
    tools=[serper_tool, browser_tool],
    llm=llm
)

find_jobs_task = Task(
    description="""Find AWS DevOps remote job listings from WeWorkRemotely.com.
    Use the search tool to search for: "site:weworkremotely.com AWS DevOps remote jobs"
    Extract all relevant job listings from the search results.
    For each job, provide: job title, company name, and the job listing URL.
    If the search returns no results, try searching for: "weworkremotely.com devops engineer AWS"
    IMPORTANT: Return ONLY a valid JSON array with no markdown formatting or extra text.""",
    expected_output="""A JSON array (no markdown, no code blocks) of job listings:
    [{"title": "Senior DevOps Engineer", "company": "Acme Corp", "url": "https://weworkremotely.com/..."}]""",
    agent=job_finder
)

crew = Crew(
    agents=[job_finder],
    tasks=[find_jobs_task],
    process=Process.sequential,
    verbose=True,
)

print("\nKicking off crew...")
result = crew.kickoff()

print("\n" + "=" * 60)
print("RAW RESULT:")
print("=" * 60)
print(result.raw)

print("\n" + "=" * 60)
print("PARSED JSON:")
print("=" * 60)
try:
    raw = str(result.raw)
    # Strip markdown code block wrapper
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    jobs = json.loads(raw)
    print(json.dumps(jobs, indent=2))
    print(f"\nFound {len(jobs)} jobs")
except (json.JSONDecodeError, IndexError) as e:
    print(f"JSON parse error: {e}")
    print("Raw output was not valid JSON")
