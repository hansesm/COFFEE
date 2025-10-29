# COFFEE - Corrective Formative Feedback

AI-powered feedback system for educational institutions using Django and Large Language Models.

## Quick Demo with Docker Compose

Spin up a complete demo environment—including database, Ollama, migrations, and sample data:

```bash
git clone <repository-url>
cd COFFEE
docker compose -f docker-compose.demo.yml up #uses ghcr.io/hansesm/coffee:latest
```

This command spins up PostgreSQL, Ollama and the app itself. On startup all migrations run automatically, default users are created, and demo data is imported. 
The download of the default LLM phi4 can take a while. Ollama may run slowly or time out when running in Docker.
You can adjust the `request_timout` setting in the [Admin Panel](http://localhost:8000/admin/home/llmprovider/1/change/) to prevent this.

In the meantime you can reach the app at [http://localhost:8000](http://localhost:8000). 

To tear everything down run:

```bash
docker compose -f docker-compose.demo.yml down -v
```

Restarting the demo reruns the migrations and will likely fail, so this compose file is meant strictly for a one-off demo environment.

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

### Optional: Local Ollama Setup for Development

1. **Install Ollama**
   - Follow the official instructions at [ollama.com/download](https://ollama.com/download) for your platform.

2. **Start the Ollama service**
   - After installation the daemon normally starts automatically. You can verify with:
     ```bash
     ollama serve
     ```
     (Press `Ctrl+C` to stop if it is already running in the background.)

3. **Download a model**
   ```bash
   ollama pull phi4
   ```

4. **Test the model locally**
   ```bash
   ollama run phi4
   ```
   The default API endpoint is available at `http://localhost:11434`.

5. **Register Ollama in Django Admin**
   - Sign in at `<BASE_URL>/admin`.
   - Go to **LLM Providers** → **Add**, pick **Ollama**, set the host (e.g. `http://localhost:11434`), and save.
   - Go to **LLM Models** → **Add**, select the newly created Ollama provider, enter the model name (e.g. `phi4`), choose a display name, and save.
   - The provider and model can now be assigned to tasks and criteria inside the app.

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
DB_PASSWORD=<YOUR_DB_PASSWORD>
DB_USERNAME=<user>
DB_HOST=<host>
DB_PORT=<port>
DB_NAME=<db>
DB_PROTOCOL=<postgres|sqlite>
```
### Custom LLM Providers

You can add your own **LLM Providers** and **LLM Models** in the Django Admin Panel (`<BASE_URL>/admin`).

Currently supported LLM Providers:
- **Ollama** – see [`ollama_api.py`](coffee/home/ai_provider/ollama_api.py)
- **Azure** – see [`azure_ai_api.py`](coffee/home/ai_provider/azure_ai_api.py)
- **Azure OpenAI** – see [`azure_openai_api.py`](coffee/home/ai_provider/azure_openai_api.py)

Contributions for additional providers such as **LLM Lite**, **AWS Bedrock**, **Hugging Face**, and others are very welcome! 🚀

## LLM Backends

Add providers and models in the Django admin under **LLM Providers** / **LLM Models**. Each backend needs different connection details:
- **Ollama** – Set `Endpoint` to your Ollama host (e.g. `http://ollama.local:11434` or `http://localhost:11434`). Leave the API key empty unless you enabled token auth; optional TLS settings live in the JSON `config`.
- **Azure AI** – Use the Inference endpoint that already includes the deployment segment, for example `https://<azure-resource>/openai/deployments/<deployment>`. Add the matching API key.
- **Azure OpenAI** – Point `Endpoint` to the service base URL like `https://<azure-resource>.cognitiveservices.azure.com/`. Add the matching API key.

## Default Login Credentials

After running `python manage.py create_users_and_groups`, use these credentials:

- **Admin**: username `admin`, password `reverence-referee-lunchbox`
- **Manager**: username `manager`, password `expediter-saline-untapped`

## Usage

1. **Admin**: Create courses, tasks, and criteria at `/admin/`
2. **Students**: Submit work and receive AI feedback
3. **Analysis**: View feedback analytics and export data

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

## Credits

This project was developed with assistance from [Claude Code](https://claude.ai/code), Anthropic's AI coding assistant.

## License

See LICENSE.md for details.
