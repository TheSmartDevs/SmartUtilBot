#Copyright @ISmartDevs
#Channel t.me/TheSmartDev
# Use an official Python image
FROM python:3.9-slim-buster

# Install system dependencies
RUN apt update && apt install -y git curl ffmpeg && apt clean

# Set working directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the bot files
COPY . .

# Make start.sh executable
RUN chmod +x start.sh

# Expose port for Flask
EXPOSE 8000

# Run the bot and Flask server
CMD ["bash", "start.sh"]
