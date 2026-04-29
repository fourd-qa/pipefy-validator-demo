FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p results tmp

# Render passa $PORT, fallback 8080 pra dev local
ENV PORT=8080
EXPOSE 8080

# gunicorn em prod (1 worker, threads pra Robot subprocess), fallback flask dev se preferir
CMD gunicorn server:app --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 180 --access-logfile -
