# Use an official Gradle image as a base
FROM amazoncorretto:17 AS builder

# Set the working directory in the container
WORKDIR /app

# Copy build.gradle and settings.gradle to the container
COPY build.gradle settings.gradle /app/

# Copy gradlew and the wrapper directory to the container
COPY gradlew gradle/wrapper /app/

# Ensure gradlew has execute permissions
RUN chmod +x /app/gradlew

# Install findutils (includes xargs) to make sure required tools are present
# RUN apt-get update && apt-get install -y findutils

RUN yum update -y
RUN yum install -y findutils
# Copy the rest of the project files to the container
COPY . /app/

RUN chmod +x ./gradlew
# Build the runtime artifact without running tests inside the image build.
# The smoke tests depend on host-specific ontology paths that are not available
# in the Docker build context.
RUN ./gradlew clean build -x test

# Use a smaller image for the final container
FROM amazoncorretto:17

# Set the working directory
WORKDIR /app

# Copy only the JARs (compiled application) to the final image
COPY --from=builder /app/build/libs /app/libs

# Run the application
CMD ["java", "-jar", "/app/libs/OAPT.jar"]
