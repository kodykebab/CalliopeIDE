# ---- Calliope Execution Sandbox ----
# Lightweight container for secure code execution

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Stellar CLI (required for agent tasks)
# Using a specific version for stability
RUN curl -L https://github.com/stellar/stellar-cli/releases/download/v22.1.0/stellar-cli-x86_64-unknown-linux-musl.tar.gz | tar -xz && \
    mv stellar /usr/local/bin/

# Create a non-root user for execution
RUN adduser --disabled-password --gecos "" sandboxuser
WORKDIR /workspace
RUN chown sandboxuser:sandboxuser /workspace

# Python security configurations
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace

# Set default user
USER sandboxuser

# Keep container alive or run specific command
CMD ["python3"]
