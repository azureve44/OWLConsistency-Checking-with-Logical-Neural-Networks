# Use an official Gradle image as a base
FROM gradle:jdk17 AS builder

# Set the working directory in the container
WORKDIR /app

# Copy build.gradle and settings.gradle to the container
COPY build.gradle settings.gradle /app/

# Copy gradlew and the wrapper directory to the container
COPY gradlew gradle/wrapper /app/

# Ensure gradlew has execute permissions
RUN chmod +x /app/gradlew

# Install findutils (includes xargs) to make sure required tools are present
RUN apt-get update && apt-get install -y findutils

# Copy the rest of the project files to the container
COPY . /app/

# Run Gradle build (should work with the wrapper now)
RUN ./gradlew clean build

# Use a smaller image for the final container
FROM openjdk:17-jdk-slim

# Set the working directory
WORKDIR /app

# Copy only the JARs (compiled application) to the final image
COPY --from=builder /app/build/libs /app/libs

# Run the application
CMD ["java", "-jar", "/app/libs/Preprocessing.jar"]