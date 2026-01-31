FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py db.py models.py auth_models.py auth_utils.py query_models.py query_db.py trino_client.py cerbos_client.py ./
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]