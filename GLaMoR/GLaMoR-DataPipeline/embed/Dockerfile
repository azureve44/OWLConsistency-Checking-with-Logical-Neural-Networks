FROM python:3.9

WORKDIR /app

RUN pip install pika
RUN pip install numpy
RUN pip install rdflib
RUN pip install pyparsing
RUN pip install gensim
RUN pip install scikit-learn
RUN pip install nltk
RUN pip install OWLready2


COPY . /app

ENV PYTHONUNBUFFERED=1


CMD ["python3", "/app/worker.py"]
