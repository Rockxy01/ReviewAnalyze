# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y wget unzip xvfb libxi6 libgconf-2-4 libxkbcommon-x11-0 \
    libatk-bridge2.0-0 libx11-xcb1 libgtk-3-0 libxshmfence-dev && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /App

# Copy the current directory contents into the container at /app
COPY . /App

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PORT=8000

# Expose port
EXPOSE 8000

# Run the application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "AppOriginal:app"]
