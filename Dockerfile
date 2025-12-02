# Dockerfile for sys-bio-kgs

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set working directory
RUN apt-get update && apt-get install -y \
    git \
    curl \
    gcc \
    pkg-config \
    libcairo2-dev \
    libglib2.0-dev \
    libffi-dev \
    libgirepository1.0-dev \
    gobject-introspection \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Make sure pip itself is up to date
RUN pip install --upgrade pip

# Force a PyGObject version that still works with libgirepository1.0
RUN pip install --no-cache-dir "PyGObject>=3.46,<3.51"

# Now install your package + momapy, which will reuse that PyGObject
RUN pip install --no-cache-dir -e .

# Copy remaining source code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "create_knowledge_graph.py"]
