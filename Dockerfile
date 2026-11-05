FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    COPILOT_CLI_EXTRACT_DIR=/opt/copilot-runtime \
    COPILOT_SKIP_CLI_DOWNLOAD=1

RUN useradd --create-home --home-dir /home/app --shell /usr/sbin/nologin app

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m copilot download-runtime \
    && chmod -R a+rX /opt/copilot-runtime

COPY app/ ./app/
COPY data/ ./data/
COPY scripts/ ./scripts/

USER app
ENV HOME=/home/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
