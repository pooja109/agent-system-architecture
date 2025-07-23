# Use official Python image as base
FROM python:3.11-slim-bullseye

# Upgrade system packages to fix vulnerabilities
RUN apt-get update && apt-get upgrade -y && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements if exists, else skip
COPY requirements.txt ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Copy the agent script and any other necessary files
COPY research_agent.py ./

# Set the default command to run the agent
CMD ["python", "research_agent.py"]