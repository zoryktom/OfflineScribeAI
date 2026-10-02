FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data
COPY experiments/configs ./experiments/configs
COPY tests ./tests

RUN pip install --no-cache-dir -e .

CMD ["offlinescribe", "eval", "run", "--config", "experiments/configs/sample.yaml"]
