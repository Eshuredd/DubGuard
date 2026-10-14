FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY src ./src
RUN python -m pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 dubguard
USER dubguard
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "dubguard.api:app", "--host", "0.0.0.0", "--port", "8000"]
