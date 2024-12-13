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

# Run the app with 4 workers, 2 threads per worker, and a 120-second timeout
CMD ["gunicorn", "--timeout", "120", "-w", "4", "--threads", "2", "-b", "0.0.0.0:5000", "App:app"]
