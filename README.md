# COFFEE - Corrective Formative Feedback

AI-powered feedback system for educational institutions using Django and Large Language Models.

## Getting Started

1. **Prerequisites**
- Install [uv](https://github.com/astral-sh/uv?tab=readme-ov-file#installation)

2. **Clone and setup**
   ```bash
   git clone <repository-url>
   cd COFFEE
   uv venv --python 3.13
   uv sync
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Setup database**
   Without the env variable `DATABASE_URL` django creates a sqlite database:
   ```bash 
   uv run task migrate
   uv run task create-groups
   ```
   
   If you want to use a PostgreSQL database, you can spin it up with Docker Compose:
   ```bash
   docker compose up -d 
   uv run task migrate
   uv run task create-groups
   ```

6. **Run**
   ```bash
   uv run task server
   ```

### Optional: Populate Database with Demo Data

```bash
uv run task import-demo-data
```

## Configuration

All configuration is environment-based. Copy `.env.example` to `.env` and customize:

### Required Settings
```env
# Django (REQUIRED)
SECRET_KEY=your-secret-key-here  
DEBUG=True
DATABASE_URL=postgres://user:pass@localhost:5432/coffee_db
```
### Custom LLM Providers

You can add your own **LLM Providers** and **LLM Models** in the Django Admin Panel (`<BASE_URL>/admin`).

Currently supported LLM Providers:
- **Ollama** – see [`ollama_api.py`](coffee/home/ai_provider/ollama_api.py)
- **Azure** – see [`azure_ai_api.py`](coffee/home/ai_provider/azure_ai_api.py)
- **Azure OpenAI** – see [`azure_openai_api.py`](coffee/home/ai_provider/azure_openai_api.py)

Contributions for additional providers such as **LLM Lite**, **AWS Bedrock**, **Hugging Face**, and others are very welcome! 🚀

## Docker Deployment

```bash
docker build -t coffee .
docker run -p 8000:8000 --env-file .env coffee #On Windows add '--network host'  
```

## Podman Deployment (RedHat/RHEL)

For RedHat Enterprise Linux systems using Podman:

```bash
# Install podman-compose if not already installed
sudo dnf install podman-compose

# Copy and configure environment
cp .env.example .env
# Edit .env with your actual configuration values

# Deploy with podman-compose
podman-compose -f podman-compose.yaml up -d

# Create initial users and database schema
podman exec -it coffee_app python manage.py migrate
podman exec -it coffee_app python manage.py create_users_and_groups

# Access the application
curl http://localhost:8000
```

**Useful Podman commands:**
```bash
# View logs
podman-compose logs -f coffee_app

# Stop services
podman-compose down

# Rebuild and restart
podman-compose up -d --build
```

## LLM Backends

Supports multiple AI backends:
- **Ollama**: Local or remote Ollama instances with fallback support
- **Azure OpenAI**: GPT-4, GPT-3.5-turbo deployments

## Default Login Credentials

After running `python manage.py create_users_and_groups`, use these credentials:

- **Admin**: username `admin`, password `reverence-referee-lunchbox`
- **Manager**: username `manager`, password `expediter-saline-untapped`

## Usage

1. **Admin**: Create courses, tasks, and criteria at `/admin/`
2. **Students**: Submit work and receive AI feedback
3. **Analysis**: View feedback analytics and export data

## Credits

This project was developed with assistance from [Claude Code](https://claude.ai/code), Anthropic's AI coding assistant.

## License

See LICENSE.md for details.