# Inventário de Limpeza — pequena app web Flask.
FROM python:3.11-slim-bookworm
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8002
CMD ["python", "-u", "app.py"]
