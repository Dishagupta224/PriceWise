FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/inventory-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY services/shared ./shared
COPY services/inventory-service/app ./app
COPY services/inventory-service/start.sh ./start.sh

RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
