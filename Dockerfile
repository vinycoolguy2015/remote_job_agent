FROM --platform=linux/arm64 python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir "aws-opentelemetry-distro>=0.11.0"

COPY pyproject.toml .
COPY src/ src/
COPY templates/ templates/

RUN pip install --no-cache-dir -e .

# OpenTelemetry Configuration for AgentCore observability
ENV OTEL_SERVICE_NAME=job_application_coach_agent
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_METRICS_EXPORTER=otlp

# AWS OpenTelemetry Distribution
ENV OTEL_PYTHON_DISTRO=aws_distro
ENV OTEL_PYTHON_CONFIGURATOR=aws_configurator

# Export Protocol
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# Enable Agent Observability
ENV AGENT_OBSERVABILITY_ENABLED=true

# Service Identification
ENV OTEL_TRACES_SAMPLER=always_on
ENV OTEL_RESOURCE_ATTRIBUTES=service.namespace=AgentCore,service.version=1.0

EXPOSE 8080

# Run with OpenTelemetry auto-instrumentation
CMD ["opentelemetry-instrument", "python", "-m", "job_application_coach.crew"]
