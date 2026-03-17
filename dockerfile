# FROM python:3.11-slim

# WORKDIR /app

# COPY requirements.txt .

# RUN pip install --no-cache-dir -r requirements.txt

# EXPOSE 8048

# CMD ["uvicorn", "generate_token:app", "--host", "0.0.0.0", "--port", "8048"]

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Create required runtime directories
RUN mkdir -p resumes transcripts evaluations recordings

EXPOSE 8048

CMD ["uvicorn", "generate_token:app", "--host", "0.0.0.0", "--port", "8048"]