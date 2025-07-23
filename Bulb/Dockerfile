FROM python:3.11-slim

WORKDIR /app

COPY . /app
COPY cert.pem key.pem ./

ENV PYTHONUNBUFFERED=1


RUN apt update && apt install -y iputils-arping


RUN pip install --no-cache-dir -r requirements.txt

CMD ["python","-u" ,"main.py"]
