# Use a multi-stage build to include uv
FROM ghcr.io/astral-sh/uv:latest AS uv

# Use Python 3.14.2 slim image
FROM python:3.14.2-slim

# Copy the uv binary from the uv image
COPY --from=uv /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Copy configuration files
COPY pyproject.toml .

# Sync dependencies using uv
RUN uv sync --no-cache

# Copy the rest of the application
COPY . .

# Set the environment path
ENV PATH="/app/.venv/bin:$PATH"

# Default command
CMD ["python", "main.py"]
