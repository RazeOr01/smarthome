FROM python:3.11-slim

WORKDIR /app

COPY . /app

ENV PYTHONUNBUFFERED=1


RUN apt update 


RUN pip install --no-cache-dir -r requirements.txt

CMD ["python","-u" ,"main.py"]
