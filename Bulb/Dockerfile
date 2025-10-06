FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libstdc++6 libgcc-s1 libssl3 libavahi-client3 libavahi-common3 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app
COPY cert.pem key.pem ./

ENV PYTHONUNBUFFERED=1


RUN apt update && apt install -y iputils-arping


RUN pip install --no-cache-dir -r requirements.txt

CMD ["python","-u" ,"main.py"]
