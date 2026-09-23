FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --run-syncdb --noinput && python manage.py seed_pilot && gunicorn config:application --bind 0.0.0.0:8000 --workers 2"]
