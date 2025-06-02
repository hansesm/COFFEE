FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt /app/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app

# Datenbankmigration
#RUN python manage.py makemigrations
#RUN python manage.py migrate --run-syncdb
#RUN python manage.py create_users_and_groups

# Staticfiles
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Sicherheit: User wechseln
RUN adduser --disabled-password --gecos '' django
USER django

CMD ["gunicorn", "--config", "gunicorn-cfg.py", "core.wsgi"]
