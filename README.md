# COFFEE

This is a Django-based feedback application. The project is configured using environment variables loaded from a `.env` file. A sample configuration is provided in `.env.example`.

## Development

1. Create a copy of `.env.example` named `.env` and adjust the values for your environment.
2. Build and start the stack using Docker Compose:

```bash
docker-compose up --build
```

The application will be available at `http://localhost:8000`.

## Running Tests

Install the dependencies and run the Django test suite:

```bash
pip install -r requirements.txt
python manage.py test
```

## Deployment

A production image can be built using the provided `Dockerfile`:

```bash
docker build -t coffee-app:latest .
```

Environment variables should be supplied via the `.env` file or your orchestration platform.
