"""
AgentCore Runtime Handler.
Receives requests from the Gateway, runs the CrewAI agents, and returns results.
"""
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

from job_application_coach.crew import JobApplicationCoach
from job_application_coach.tools.s3_resume_tool import S3ResumeTool


class AgentHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        action = body.get("action", "")

        try:
            if action == "find_jobs":
                result = self._find_jobs(body)
            elif action == "tailor_resume":
                result = self._tailor_resume(body)
            else:
                result = {"error": f"Unknown action: {action}"}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def _find_jobs(self, body: dict) -> dict:
        coach = JobApplicationCoach()

        find_task = coach.find_jobs_task()
        find_agent = coach.job_finder()

        from crewai import Crew, Process
        crew = Crew(agents=[find_agent], tasks=[find_task], process=Process.sequential, verbose=True)
        result = crew.kickoff()

        try:
            jobs = json.loads(str(result))
        except json.JSONDecodeError:
            jobs = [{"title": "Parse error", "company": "N/A", "url": "#", "raw": str(result)}]

        return {"jobs": jobs}

    def _tailor_resume(self, body: dict) -> dict:
        job_url = body.get("job_url", "")

        s3_tool = S3ResumeTool()
        resume_content = s3_tool._run(user_id="default")

        coach = JobApplicationCoach()

        tailor_task = coach.tailor_resume_task()
        tailor_agent = coach.resume_tailor()

        from crewai import Crew, Process
        crew = Crew(agents=[tailor_agent], tasks=[tailor_task], process=Process.sequential, verbose=True)
        result = crew.kickoff(inputs={"job_url": job_url, "resume_content": resume_content})

        try:
            parsed = json.loads(str(result))
        except json.JSONDecodeError:
            parsed = {"resume": json.loads(resume_content), "interview_tips": ["Could not parse agent output"]}

        return parsed

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "healthy", "agent": "job_application_coach"}).encode())


def main():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), AgentHandler)
    print(f"Agent runtime listening on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
