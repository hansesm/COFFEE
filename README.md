# COFFEE - Corrective Formative Feedback

AI-powered feedback system for educational institutions using Django and Large Language Models.

<img width="1231" height="760" alt="COFFEES Startpage" src="https://github.com/user-attachments/assets/50084d1d-99f6-414e-b1a2-ebbf1a0021e9" />


## Quick Demo with Docker Compose

Try COFFEE instantly with a single command! Download the [docker-compose.demo.yml](docker-compose.demo.yml) file and run:

```bash
docker compose -f docker-compose.demo.yml up
```

Or use this one-liner (macOS/Linux/Windows):

```bash
curl -O https://raw.githubusercontent.com/hansesm/coffee/main/docker-compose.demo.yml && docker compose -f docker-compose.demo.yml up
```

**Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri https://raw.githubusercontent.com/hansesm/coffee/main/docker-compose.demo.yml -OutFile docker-compose.demo.yml; docker compose -f docker-compose.demo.yml up
```

This spins up PostgreSQL, Ollama (with phi4 model), and the app itself using the pre-built image `ghcr.io/hansesm/coffee:latest`. On startup, migrations run automatically, default users are created, and demo data is imported.

**Note:** The phi4 model download can take a while. Ollama may run slowly or time out when running in Docker. You can adjust the `request_timeout` setting in the [Admin Panel](http://localhost:8000/admin/home/llmprovider/1/change/) to prevent timeouts.

Access the app at [http://localhost:8000](http://localhost:8000).

**To tear everything down:**

```bash
docker compose -f docker-compose.demo.yml down -v
```

The demo environment is restart-safe. If you stop and restart the containers, existing data will be preserved and the startup commands will detect existing users and demo data automatically.

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

**For RedHat Enterprise Linux systems using Podman:**


### Full version

```bash
# Install podman if not already installed
sudo dnf install podman
# To see if you already have podman
podman --version

# Install git if not already installed
sudo dnf install git
# To see if you already have git
git --version

# Install python3 if not already installed 
sudo dnf install python3
# To see if you already have python3
python3 --version

# Optional:Install nano if not already installed
sudo dnf install nano
# To see if you already have nano
nano --version

# Clone the COFFEE repository
git clone <REPOSITORY-URL>

# Enter the COFFEE directory
cd COFFEE

# Copy and configure the environment
cp .env.example .env

# Edit .env with your actual configuration values (e.g. with nano)
nano .env

# Make the startup script executable (only required once)
chmod +x run-podman.sh

# Start COFFEE
./run-podman.sh

# Verify that all containers are running
podman pod ps
podman ps -a

# Test if the application is reachable
curl -I http://localhost:8000

# Now open the browser:
# http://<Your IP or localhost>:8000
```

### Demo version
```bash
# Install podman if not already installed
sudo dnf install podman
# To see if you already have podman
podman --version

# Install python3 if not already installed 
sudo dnf install python3
# To see if you already have python3
python3 --version

# Install pip3 if not already installed 
sudo dnf install pip3
# To see if you already have pip3
pip3 --version

# Install podman-compose if not already installed (via pip)
python3 -m pip install --user podman-compose
# Verify if podman-compose is available
which podman-compose

# Clone the full repository (required for deployment)
git clone <REPOSITORY-URL>

# Enter the COFFEE directory
cd COFFEE

# Copy and configure the environment 
cp .env.example .env
# Edit .env with your configuration values
nano .env
```

### Important: If your system has limited available disk space

You must comment out the **Ollama** service in the `docker-compose.demo.yml` file **before** running the startup 
command.

The Ollama images are very large and can quickly consume your storage.
If they are not disabled, the command:

```bash
podman-compose -f docker-compose.demo.yml up -d
```

may fail and leave your environment in a broken state due to insufficient disk space.

Please be aware that if Ollama is removed or disabled, the **LLM Tool will no longer function**, as it depends on 
Ollama.

#### How to disable Ollama

Open the `docker-compose.demo.yml` file **before** running the startup command.
Ollama needs to be commented out in three places:

1. Under the ollama: section
2. Under app:, where ollama: is referenced with the condition: service_healthy
3. Under volumes: where the Ollama volume is defined
<img width="983" height="1109" alt="Screenshot 2026-02-05 134909" src="https://github.com/user-attachments/assets/4d1e6a79-7d1f-4ed5-b99b-0500187052f3" />
<img width="882" height="344" alt="Screenshot 2026-02-05 134852" src="https://github.com/user-attachments/assets/e88bca43-509e-4988-8ebb-bbad938925fe" />


Make sure you have commented out all relevant entries.



```bash
# Deploy with podman compose
podman-compose -f docker-compose.demo.yml up -d

# Test if the application is reachable 
curl -I http://localhost:8000

# Now open the browser:
# http://<Your IP or localhost>:8000
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
