FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-audio.txt pyproject.toml ./
RUN python -m pip install --no-cache-dir -r requirements-audio.txt
COPY src ./src
RUN python -m pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 dubguard \
    && mkdir -p /home/dubguard/data \
    && chown -R dubguard:dubguard /home/dubguard/data
ENV DUBGUARD_DATA_DIR=/home/dubguard/data
USER dubguard
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "dubguard.api:app", "--host", "0.0.0.0", "--port", "8000"]
