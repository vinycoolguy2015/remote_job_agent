import json
import boto3
import os
from crewai.tools import BaseTool


class S3ResumeTool(BaseTool):
    name: str = "Read Resume from S3"
    description: str = "Reads the user's base resume JSON from an S3 bucket using IAM authentication."

    def _run(self, user_id: str = "default") -> str:
        bucket = os.environ.get("S3_RESUME_BUCKET", "my-resume-bucket")
        key = f"resumes/{user_id}/resume.json"

        s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))

        try:
            response = s3.get_object(Bucket=bucket, Key=key)
            resume_data = json.loads(response["Body"].read().decode("utf-8"))
            return json.dumps(resume_data, indent=2)
        except s3.exceptions.NoSuchKey:
            return json.dumps({
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+1-555-0100",
                "summary": "Senior DevOps Engineer with 8+ years of experience in AWS, Kubernetes, Terraform, and CI/CD pipelines.",
                "skills": ["AWS", "Terraform", "Kubernetes", "Docker", "Jenkins", "GitHub Actions", "Python", "Bash", "CloudFormation", "Ansible"],
                "experience": [
                    {
                        "company": "TechCorp Inc",
                        "role": "Senior DevOps Engineer",
                        "duration": "2021 - Present",
                        "bullets": [
                            "Managed AWS infrastructure serving 10M+ requests/day using Terraform and CloudFormation",
                            "Built CI/CD pipelines with GitHub Actions reducing deployment time by 60%",
                            "Implemented Kubernetes cluster management for 50+ microservices",
                            "Led migration from on-premise to AWS, saving $200K/year in infrastructure costs"
                        ]
                    },
                    {
                        "company": "CloudStart LLC",
                        "role": "DevOps Engineer",
                        "duration": "2018 - 2021",
                        "bullets": [
                            "Designed and maintained Docker-based development environments",
                            "Automated infrastructure provisioning using Ansible and Terraform",
                            "Set up monitoring and alerting with CloudWatch and PagerDuty",
                            "Reduced mean time to recovery (MTTR) from 4 hours to 30 minutes"
                        ]
                    }
                ],
                "education": {
                    "degree": "B.S. Computer Science",
                    "school": "University of California, Berkeley",
                    "year": "2018"
                }
            }, indent=2)
        except Exception as e:
            return f"Error reading resume: {str(e)}"
