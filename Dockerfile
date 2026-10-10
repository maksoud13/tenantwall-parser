FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY app ./app

# Cloud Run uses PORT env
ENV PORT=8000
EXPOSE 8000

# Run
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1