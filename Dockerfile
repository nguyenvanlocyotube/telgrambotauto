FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose admin panel port
EXPOSE 5000

CMD ["python", "-c", "print('Use docker-compose to run services')"]
