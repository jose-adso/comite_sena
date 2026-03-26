
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update \
	&& apt-get install -y --no-install-recommends build-essential libpq-dev \
	&& rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p instance

EXPOSE 8080

ENV FLASK_ENV=production

CMD ["python", "app.py", "--port", "8080"]
