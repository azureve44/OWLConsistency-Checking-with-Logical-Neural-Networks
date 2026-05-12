FROM python:3.9

WORKDIR /app

COPY . /app

RUN pip install pika
RUN pip install psycopg2
RUN pip install PyYAML
ENV PYTHONUNBUFFERED=1
CMD ["python3", "/app/remove_prefixes.py"]