ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION} AS venv

WORKDIR /app

COPY main.py ./

CMD ["python", "-u", "main.py"]

