#!/usr/bin/env python
import sys
import warnings
import json

from job_application_coach.crew import JobApplicationCoach

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def run():
    inputs = {
        'job_url': 'https://weworkremotely.com/remote-jobs/search?term=aws+devops',
        'resume_content': 'Will be loaded from S3 by the agent tool'
    }

    try:
        result = JobApplicationCoach().crew().kickoff(inputs=inputs)
        print(result)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


if __name__ == "__main__":
    run()
