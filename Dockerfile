FROM python:3.9-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    chromium \
    chromium-driver && \
    rm -rf /var/lib/apt/lists/*

# Install pip dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Set environment variables
ENV PATH="/usr/bin:$PATH"

# Copy app files
COPY . /App
WORKDIR /App

# Run the app
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "App:app"]
