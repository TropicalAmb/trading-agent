FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml README.md ./
COPY config ./config
COPY src ./src
COPY scripts ./scripts

RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
ENV CONFIG_PATH=config/settings.yaml
ENV JOURNAL_DB_PATH=data/journal.db
ENV USE_MOCK_BROKER=true
ENV ALLOW_LIVE_TRADING=false

RUN mkdir -p /app/data

# Paper autonomous loop (Yahoo delayed + paper execution adapter)
CMD ["python", "-m", "agent.live_main", "--mock"]
