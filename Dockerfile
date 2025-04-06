FROM python:3.10-slim

# Set environment variables
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.5.1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    # Add poetry to PATH for subsequent commands in this RUN layer
    export PATH="/root/.local/bin:$PATH" && \
    poetry config virtualenvs.create false

# Add poetry to PATH for subsequent RUN layers and the final CMD
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

COPY . .

RUN poetry install --only main --no-interaction

# Create a non-root user to run the agent
RUN useradd -m agent
USER agent

# Set the command to run the agent
CMD ["python", "-m", "agent", "--config", "config.json"]

# Add label for the Cloudflare Workers
LABEL com.cloudflare.w.name="eigenlayer-ai-agent"