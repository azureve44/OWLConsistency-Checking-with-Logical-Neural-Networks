FROM python:3.9

WORKDIR /app

COPY . /app

RUN pip install pika
RUN pip install psycopg2
RUN pip install PyYAML
RUN pip install -r requirements.txt

ENV PYTHONUNBUFFERED=1
CMD ["python3", "/app/worker_single_run.py"]
