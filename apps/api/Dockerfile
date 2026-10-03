FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY app ./app
RUN pip install --no-cache-dir .
COPY alembic.ini .
COPY migrations ./migrations
RUN useradd --create-home --uid 10001 fitness && mkdir /app/private-media && chown -R fitness:fitness /app
USER fitness
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
