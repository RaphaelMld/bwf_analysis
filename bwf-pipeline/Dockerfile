FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools

COPY pyproject.toml .
RUN pip install --no-cache-dir httpx sqlalchemy alembic psycopg2-binary \
    pydantic pydantic-settings apscheduler tenacity python-dotenv

COPY . .

CMD ["python", "-m", "bwf.scheduler"]