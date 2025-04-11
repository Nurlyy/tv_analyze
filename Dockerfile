FROM python:3.11-buster

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

# Install system dependencies required for building some packages
RUN apt update && apt install -y build-essential ffmpeg libsndfile1 python3-dev libatlas-base-dev

# Install wheel and pip
RUN pip install --upgrade pip && pip install wheel

COPY requirements.txt /code/
RUN pip install -r requirements.txt

COPY . /code/

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]