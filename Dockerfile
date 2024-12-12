# Start with a base Python image
FROM python:3.9-slim

# Install dependencies for Chrome and Selenium
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    ca-certificates \
    fontconfig \
    libx11-dev \
    libx11-xcb1 \
    libxcomposite1 \
    libxrandr2 \
    libxdamage1 \
    libxi6 \
    libgdk-pixbuf2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libasound2 \
    libxtst6 \
    libappindicator3-1 \
    libxss1 \
    libgbm-dev \
    libnspr4 \
    libudev-dev \
    libpango1.0-0 \
    libatk1.0-0 \
    libgtk-3-0 \
    google-chrome-stable

# Install the chromedriver to match the installed version of Chrome
RUN wget https://chromedriver.storage.googleapis.com/111.0.5563.64/chromedriver_linux64.zip -P /tmp \
    && unzip /tmp/chromedriver_linux64.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver_linux64.zip

# Set up the environment
ENV PATH="/usr/local/bin/chromedriver:$PATH"

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy your app code into the container
COPY . /app

# Set the working directory to your app directory
WORKDIR /app

# Set the command to run your application
CMD ["python", "App.py"]
