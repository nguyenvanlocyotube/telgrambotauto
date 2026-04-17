FROM python:3.11-slim

RUN echo "force rebuild v3"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Expose port (Flask)
EXPOSE 3000

CMD ["python", "bot.py"]