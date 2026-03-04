FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/pricing-agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY services/shared ./shared
COPY services/pricing-agent/app ./app
COPY services/pricing-agent/start.sh ./start.sh

RUN chmod +x /app/start.sh

CMD ["/bin/sh", "/app/start.sh"]
