# Use an official Python base image
FROM python:3.9

# Set the working directory inside the container
WORKDIR /app

# Install necessary dependencies
RUN pip install pika psycopg2
RUN pip install pandas
# Copy your Python script into the container
COPY initial_publish.py /app/

# Command to run the Python script when the container starts
CMD ["python3", "initial_publish.py"]
