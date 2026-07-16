ARG PYTHON_IMAGE=python:3.13-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY zhihu_fiction ./zhihu_fiction

RUN python -m pip install --upgrade pip \
    && python -m pip install -r zhihu_fiction/requirements.txt \
    && python -m pip install redis minio

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "zhihu_fiction.server:app", "--host", "0.0.0.0", "--port", "8000"]
