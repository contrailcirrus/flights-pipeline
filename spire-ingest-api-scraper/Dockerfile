FROM python:3.12

ENV PYTHONUNBUFFERED 1
ENV TZ UTC

WORKDIR /app

# Install python dependencies.
RUN pip install pipenv==2023.12.1
COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy

COPY . .
CMD [ "python", "-m", "src.main"]
