# Job Application Coach - Bedrock AgentCore

An AI agent that finds AWS DevOps jobs on WeWorkRemotely.com and generates a tailored professional resume PDF.

## Architecture

```
Streamlit UI
    │
    │  POST + Bearer JWT (M2M from Cognito)
    ▼
AgentCore Gateway  ◄── Inbound JWT validation
    │
    ▼
Agent Runtime (Docker container on AgentCore)
    │
    ├── Agent 1: Job Finder
    │       └── Browser Tool → scrapes weworkremotely.com
    │
    └── Agent 2: Resume Tailor
            ├── Browser Tool → scrapes selected job posting
            ├── Outbound IAM → reads base resume from S3
            └── Outbound API Key → Serper for company research
    │
    ▼
Returns tailored resume JSON → Streamlit generates PDF via WeasyPrint
```

## Features Used

| AgentCore Feature | Usage |
|---|---|
| Gateway | Single HTTPS endpoint for Streamlit |
| Inbound JWT Auth | Cognito M2M (client_credentials) validates the Streamlit app |
| Outbound IAM Auth | Agent reads base resume from S3 |
| Outbound API Key Auth | Serper API for company research |
| Browser Tool | Scrapes WeWorkRemotely job listings |
| Observability | OpenTelemetry traces/metrics via AWS Distro → CloudWatch |
| Memory | Bedrock memory stores excluded companies per user |

---

## Quick Summary (Deployment Steps)

1. Install WeasyPrint (local PDF deps)
2. Create S3 bucket + upload base resume
3. Create IAM role (S3 + ECR + Bedrock + AgentCore Memory access)
4. Create Cognito User Pool + M2M app client
5. Create Bedrock AgentCore Memory
6. Build Docker image + push to ECR
7. Deploy runtime + gateway on AgentCore (Serper key as env var)
8. Add WAF with IP allowlist
9. Set env vars + `streamlit run streamlit_app.py`

**Gateway Invocation URL:** `POST {GATEWAY_ENDPOINT}/job-application-coach/invocations`

---

## Prerequisites

- AWS Account with Bedrock AgentCore access
- AWS CLI configured
- Docker installed
- Python 3.10+
- WeasyPrint system dependencies (for local PDF generation)

---

## Setup Instructions

### Step 1: Install WeasyPrint Dependencies (for local dev)

```bash
# macOS
brew install weasyprint

# Ubuntu/Debian
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0
```

### Step 2: Create S3 Bucket for Resumes

```bash
aws s3 mb s3://my-resume-bucket --region us-east-1

# Upload a sample base resume
aws s3 cp resume.json s3://my-resume-bucket/resumes/default/resume.json
```

### Step 3: Create IAM Role for AgentCore

```bash
aws iam create-role \
    --role-name AgentCoreS3AccessRole \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }'

aws iam put-role-policy \
    --role-name AgentCoreS3AccessRole \
    --policy-name AgentCoreJobCoachPolicy \
    --policy-document '{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": "arn:aws:s3:::my-resume-bucket/resumes/*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer"
                ],
                "Resource": "*"
            }
        ]
    }'
```
Also add BedrockAgentCoreFullAccess permission

### Step 4: Create Cognito User Pool (M2M Auth)

Use the Console for this (simpler — see Console Step 3 below). When you create an M2M user pool, it automatically gives you:
- Token endpoint URL
- App client with Client ID + Secret

No manual resource server, domain, or app client creation needed.

### Step 5: Build and Push Docker Image

```bash
cd job_application_coach

# Build
docker build -t job-application-coach .

# Tag for ECR
aws ecr create-repository --repository-name job-application-coach --region us-east-1
docker tag job-application-coach:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/job-application-coach:latest

# Push
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/job-application-coach:latest
```

### Step 6: Deploy to AgentCore

Use the **Console** for this step (see Console Steps 6 & 7 below).

Deploy the agent runtime from Bedrock Console, then create a Gateway with JWT auth. The Gateway gives you a direct HTTPS endpoint (e.g., `https://job-coach-gateway-xxxx.gateway.bedrock-agentcore.us-east-1.amazonaws.com`) — no Lambda needed. Streamlit calls it directly.

### Step 7: Configure Environment and Run Streamlit

```bash
# Create .env file
cp .env.example .env

# Edit .env with your values:
# TOKEN_URL=https://us-east-1xxxxxxx.auth.us-east-1.amazoncognito.com/oauth2/token
# CLIENT_ID=your-client-id
# CLIENT_SECRET=your-client-secret
# GATEWAY_ENDPOINT=https://job-coach-gateway-xxxx.gateway.bedrock-agentcore.us-east-1.amazonaws.com

# Install dependencies
pip install -e .

# Run Streamlit
streamlit run streamlit_app.py
```

---

## AWS Console Setup Instructions

### Console Step 1: Create S3 Bucket

1. Go to **S3 Console** → **Create bucket**
2. Bucket name: `my-resume-bucket`
3. Region: `us-east-1`
4. Leave defaults → **Create bucket**
5. Open the bucket → **Create folder** → name it `resumes/default/`
6. Upload your `resume.json` file into `resumes/default/`

### Console Step 2: Create IAM Role

1. Go to **IAM Console** → **Roles** → **Create role**
2. Trusted entity: **Custom trust policy** → paste:
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [{
           "Effect": "Allow",
           "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
           "Action": "sts:AssumeRole"
       }]
   }
   ```
3. Click **Next** → **Create policy** (opens new tab) with these permissions:
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Action": ["s3:GetObject"],
               "Resource": "arn:aws:s3:::my-resume-bucket/resumes/*"
           },
           {
               "Effect": "Allow",
               "Action": [
                   "ecr:GetAuthorizationToken",
                   "ecr:BatchGetImage",
                   "ecr:GetDownloadUrlForLayer"
               ],
               "Resource": "*"
           }
       ]
   }
   ```
   - Policy name: `AgentCoreJobCoachPolicy` → **Create policy**
4. Back on role creation → refresh → attach `AgentCoreJobCoachPolicy`
5. Role name: `AgentCoreS3AccessRole` → **Create role**
6. Copy the **Role ARN** (e.g., `arn:aws:iam::123456789012:role/AgentCoreS3AccessRole`)

### Console Step 3: IAM Role Permissions for Runtime

The AgentCore runtime IAM role needs access to Bedrock models, AgentCore Memory, S3, and ECR. Add the following policies to the runtime role (`AgentCoreS3AccessRole`):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "S3ResumeAccess",
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": "arn:aws:s3:::my-resume-bucket/resumes/*"
        },
        {
            "Sid": "ECRAccess",
            "Effect": "Allow",
            "Action": [
                "ecr:GetAuthorizationToken",
                "ecr:BatchGetImage",
                "ecr:GetDownloadUrlForLayer"
            ],
            "Resource": "*"
        },
        {
            "Sid": "BedrockModelAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": "arn:aws:bedrock:us-east-1::foundation-model/us.amazon.nova-pro-v1:0"
        },
        {
            "Sid": "AgentCoreMemoryAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:ListEvents",
                "bedrock-agentcore:CreateEvent"
            ],
            "Resource": "arn:aws:bedrock-agentcore:us-east-1:*:memory/*"
        }
    ]
}
```

**Important:** Without the Memory permissions, the "Not Interested" feature (company exclusion) will silently fail. Without the Bedrock model permissions, the CrewAI agents cannot invoke Nova Pro.

### Console Step 4: Create Cognito User Pool (M2M Auth)

1. Go to **Cognito Console** → **Create user pool**
2. Select application type: **Machine-to-machine (M2M)**
3. Pool name: `agentcore-m2m-pool`
4. **Create**

The console automatically creates:
- An **App client** with Client ID and Client Secret

The pool details page shows these URLs:
- **OpenID Connect configuration URL**: `https://cognito-idp.us-east-1.amazonaws.com/<pool-id>/.well-known/openid-configuration`
- **Token signing key URL (JWKS)**: `https://cognito-idp.us-east-1.amazonaws.com/<pool-id>/.well-known/jwks.json`

5. Find the **Token URL** (for Streamlit to get a JWT):
   - Open the OpenID configuration URL in a browser
   - Look for `token_endpoint` in the JSON
   - Example: `https://us-east-1ytcry2kzy.auth.us-east-1.amazoncognito.com/oauth2/token`

6. Copy these values:

   **For Streamlit (`.env` file):**
   - `TOKEN_URL` = the token_endpoint from above
   - `CLIENT_ID` = shown in App clients section
   - `CLIENT_SECRET` = click "Show client secret" to reveal

   **For Gateway JWT config (Console Step 7):**
   - Issuer = `https://cognito-idp.us-east-1.amazonaws.com/<pool-id>`
   - JWKS URI = Token signing key URL from pool details
   - Audience = your Client ID

### Console Step 5: Create ECR Repository & Push Image

1. Go to **ECR Console** → **Create repository**
2. Repository name: `job-application-coach`
3. **Create**
4. Click the repository → **View push commands** → follow the 4 commands shown:
   ```bash
   # Authenticate Docker to ECR
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

   # Build locally
   cd job_application_coach
   docker build -t job-application-coach .

   # Tag
   docker tag job-application-coach:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/job-application-coach:latest

   # Push
   docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/job-application-coach:latest
   ```

### Console Step 6: Create Bedrock AgentCore Memory

1. Go to **Bedrock Console** → **AgentCore** → **Memory** → **Create**
2. Memory name: `job_coach_memory`
3. Set short term memory for 90 days and long term memory strategy as User preference. Once created, enable logging and tracing
4. Copy the **Memory ID** from the details page (e.g., `job_coach_memory-xYz123`)

This memory stores which companies each user has excluded. When a user clicks "Not Interested" on a company, it's saved here and filtered out in future searches.

### Console Step 7: Deploy Agent Runtime on Bedrock AgentCore

1. Go to **Bedrock Console** → **AgentCore** → **Agent Runtimes** → **Create**
2. Runtime name: `job_application_coach`
3. Container image URI: `123456789012.dkr.ecr.us-east-1.amazonaws.com/job-application-coach:latest`
4. Port: `8080`
5. IAM Role: select `AgentCoreS3AccessRole`
6. Environment variables:
   - `AWS_REGION` = `us-east-1`
   - `S3_RESUME_BUCKET` = `my-resume-bucket`
   - `SERPER_API_KEY` = `your-serper-api-key`
   - `AGENTCORE_MEMORY_ID` = `<Memory ID from Step 5>`
7. **Create**
8. Wait for status to become **Active**
9. Enable logging and tracing

### Console Step 8: Create AgentCore Gateway with JWT Auth

AgentCore Gateway gives you a direct HTTPS endpoint — no Lambda or API Gateway needed. Streamlit calls it directly.

1. Go to **Bedrock Console** → **AgentCore** → **Gateways** → **Create**
2. Gateway name: `job-coach-gateway`
3. **Schema definition**: Upload `gateway_schema.json` (included in this project) or paste the OpenAPI spec
   - This tells the Gateway what operations the agent supports (find_jobs, tailor_resume, exclude_company)
   - Defines the request/response format
4. Configure **Inbound Auth**:
   - Type: **JWT**
   - Issuer: `https://cognito-idp.us-east-1.amazonaws.com/<pool-id>` (e.g., `us-east-1_yTCrY2Kzy`)
   - JWKS URI: Token signing key URL from Cognito pool details (e.g., `https://cognito-idp.us-east-1.amazonaws.com/<pool-id>/.well-known/jwks.json`)
   - Audience: your Cognito **Client ID**
5. Link to your agent runtime: `job-application-coach`
6. **Create** and enable logging and tracing
7. Copy the **Gateway endpoint URL** (format: `https://<name>-<id>.gateway.bedrock-agentcore.us-east-1.amazonaws.com`)

This is the URL Streamlit calls directly with the M2M JWT token.

### Console Step 9: Enable Tracing & Log Delivery for Gateway

1. Go to **Bedrock Console** → **AgentCore** → **Gateways** → select `job-coach-gateway`
2. Click **Edit** or go to **Observability** tab
3. **Enable Tracing**:
   - Toggle tracing **ON**
   - This sends traces to CloudWatch X-Ray for every request through the Gateway
4. **Enable Log Delivery**:
   - Toggle log delivery **ON**
   - Log group: create or select a CloudWatch log group (e.g., `/aws/agentcore/job-coach-gateway`)
   - This logs all request/response payloads and errors

### Console Step 10: Enable Tracing & Log Delivery for Memory

1. Go to **Bedrock Console** → **AgentCore** → **Memory** → select `job_coach_memory`
2. Click **Edit** or go to **Observability** tab
3. **Enable Tracing**:
   - Toggle tracing **ON**
   - Traces memory read/write operations in CloudWatch X-Ray
4. **Enable Log Delivery**:
   - Toggle log delivery **ON**
   - Log group: create or select a CloudWatch log group (e.g., `/aws/agentcore/job-coach-memory`)
   - This logs all memory create_event/list_events calls

**Viewing logs:**
- Go to **CloudWatch Console** → **Log groups** → select your log group
- Filter for errors: search `"error"` or `"status":500`

**Viewing traces:**
- Go to **CloudWatch Console** → **X-Ray traces** → **Service map**
- You'll see the full chain: `Gateway → Agent Runtime → S3/Memory`
- Click any trace to see latency per step

### Console Step 11: Add WAF (IP Allowlist)

1. Go to **WAF & Shield Console** → **IP sets** → **Create IP set**
2. IP set name: `job-coach-allowed-ips`
3. Region: **CloudFront (Global)** or your region
4. IP version: **IPv4**
5. Add your allowed IPs (CIDR notation):
   ```
   203.0.113.10/32        ← your office IP
   198.51.100.0/24        ← your VPN range
   ```
6. **Create IP set**

**Create Web ACL:**
7. Go to **Web ACLs** → **Create web ACL**
8. Name: `job-coach-waf`
9. Resource type: **Regional resources** (same region as Gateway)
10. Associated resource: select your Gateway (or associate later)
11. **Add rules** → **Add my own rules** → **IP set**
    - Rule name: `allow-known-ips`
    - IP set: select `job-coach-allowed-ips`
    - Action: **Allow**
12. **Default action**: **Block** (blocks everything NOT in the IP set)
13. **Create web ACL**

**Result:**
```
Any request → WAF checks source IP
    ├── IP in allowlist → passes to Gateway → JWT check → Agent
    └── IP NOT in allowlist → ❌ 403 Forbidden (never reaches Gateway)
```

### Console Step 12: Run Streamlit Locally

```bash
cd job_application_coach

# Create .env from example
cp .env.example .env
```

Edit `.env` with your values:
```
AWS_REGION=us-east-1
S3_RESUME_BUCKET=my-resume-bucket
SERPER_API_KEY=your-serper-api-key
TOKEN_URL=<token_endpoint from Console Step 3>
CLIENT_ID=<from Console Step 3>
CLIENT_SECRET=<from Console Step 3>
GATEWAY_ENDPOINT=<from Console Step 7>
AGENTCORE_MEMORY_ID=<from Console Step 5>
```

```bash
# Install dependencies
pip install -e .

# Run
streamlit run streamlit_app.py
```

---

## Observability (OpenTelemetry)

The Dockerfile configures AWS OpenTelemetry auto-instrumentation. When deployed on AgentCore, traces and metrics are automatically sent to CloudWatch.

**What gets traced:**
- Every HTTP request to the agent runtime
- CrewAI agent execution (task start/end, tool calls)
- S3 calls (via boto3 instrumentation)
- Serper API calls (via requests instrumentation)

**Environment variables (set in Dockerfile):**

| Variable | Value | Purpose |
|---|---|---|
| `OTEL_SERVICE_NAME` | `job_application_coach_agent` | Identifies this agent in CloudWatch |
| `OTEL_TRACES_EXPORTER` | `otlp` | Export traces via OTLP |
| `OTEL_METRICS_EXPORTER` | `otlp` | Export metrics via OTLP |
| `OTEL_PYTHON_DISTRO` | `aws_distro` | Use AWS OpenTelemetry distribution |
| `AGENT_OBSERVABILITY_ENABLED` | `true` | Enable AgentCore observability |
| `OTEL_TRACES_SAMPLER` | `always_on` | Trace every request |

**Viewing in Console:**
1. Go to **CloudWatch Console** → **X-Ray traces** → **Service map**
2. You'll see: `Streamlit → Gateway → job_application_coach_agent → S3/Serper`
3. Click any trace to see latency breakdown per agent/tool call

---

## Local Development (without AgentCore)

To test locally without deploying to AgentCore:

```bash
# Install
pip install -e .

# Run the agent runtime locally (uses BedrockAgentCoreApp)
python src/job_application_coach/crew.py

# In another terminal, run Streamlit pointing to localhost
GATEWAY_ENDPOINT=http://localhost:8080 streamlit run streamlit_app.py
```

Note: For local dev, the Streamlit app will fail on M2M token retrieval since there's no Gateway.
You can temporarily bypass by modifying `call_gateway()` to skip auth and hit localhost directly.

---

## File Structure

```
job_application_coach/
├── pyproject.toml
├── Dockerfile
├── agentcore_config.json             # Reference only (not consumed by AgentCore)
├── streamlit_app.py
├── .env.example
├── .gitignore
├── templates/
│   └── resume_template.html          # WeasyPrint HTML/CSS template
└── src/job_application_coach/
    ├── __init__.py
    ├── main.py                        # CLI entry point
    ├── crew.py                        # CrewAI agents and tasks
    ├── runtime_handler.py             # HTTP server for AgentCore
    ├── pdf_generator.py               # WeasyPrint PDF generation
    ├── config/
    │   ├── agents.yaml                # Agent definitions
    │   └── tasks.yaml                 # Task definitions
    └── tools/
        ├── __init__.py
        └── s3_resume_tool.py          # Custom S3 resume reader (IAM auth)
```
