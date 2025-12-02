# Dockerfile for sys-bio-kgs

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# Note: momapy is optional and requires additional system libraries (cairo, pango, gobject-introspection)
# If you want to use momapy, uncomment the following lines and install momapy with:
#   pip install -e ".[momapy]"
# RUN apt-get update && apt-get install -y \
#     libcairo2-dev \
#     libpango1.0-dev \
#     libgirepository1.0-dev \
#     gir1.2-pango-1.0 \
#     && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    clang \
    pkg-config \
    ninja-build \
    git \
    curl \
    libcairo2-dev \
    libglib2.0-dev \
    libgirepository1.0-dev \
    gobject-introspection \
    libpango1.0-dev \
    libffi-dev \
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
