FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-audio.txt pyproject.toml ./
RUN python -m pip install --no-cache-dir -r requirements-audio.txt
COPY src ./src
RUN python -m pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 dubguard \
    && mkdir -p /home/dubguard/data /models \
    && chown -R dubguard:dubguard /home/dubguard/data
ENV DUBGUARD_DATA_DIR=/home/dubguard/data DUBGUARD_WHISPER_MODEL=/models/tiny.en HF_HUB_OFFLINE=1
USER dubguard
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
CMD ["python", "-m", "uvicorn", "dubguard.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "16", "--backlog", "32", "--timeout-graceful-shutdown", "90", "--no-access-log"]
