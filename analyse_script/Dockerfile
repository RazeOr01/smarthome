
FROM python:3.11-slim

RUN pip3 install --no-cache-dir pandas matplotlib scikit-learn

WORKDIR /app

COPY . .


ENV MPLBACKEND=Agg

CMD ["python3", "test_pandas.py"]
