FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for psycopg2 and rdflib
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY department_splitter.py .

CMD ["python", "department_splitter.py"]