# Use a lightweight Python base image
FROM python:3.11-slim

# Install system dependencies including Tesseract OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1-mesa-glx # Sometimes needed for Pillow/OpenCV headless operations \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY bot.py .

# Command to run the bot
CMD ["python", "bot.py"]
