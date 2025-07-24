# COFFEE - Corrective Formative Feedback

AI-powered feedback system for educational institutions using Django and Large Language Models.

## Features

- **AI Feedback**: Automated feedback using Ollama and Azure OpenAI
- **Course & Task Management**: Create courses, assignments, and evaluation criteria
- **Multi-language**: German and English support
- **PDF Export**: Download feedback reports
- **Group Permissions**: Role-based access control

## Quick Start

1. **Clone and setup**
   ```bash
   git clone <repository-url>
   cd COFFEE
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Setup database**
   ```bash
   python manage.py migrate
   python manage.py create_users_and_groups
   ```

4. **Run**
   ```bash
   python manage.py runserver
   ```

## Configuration

All configuration is environment-based. Copy `.env.example` to `.env` and customize:

### Required Settings
```env
# Django (REQUIRED)
SECRET_KEY=your-secret-key-here  
DEBUG=True
DATABASE_URL=postgres://user:pass@localhost:5432/coffee_db

# Ollama Backend (REQUIRED - at least one LLM backend needed)
OLLAMA_PRIMARY_HOST=https://your-ollama-host.com
OLLAMA_PRIMARY_AUTH_TOKEN=your-token
```

### Optional Settings
```env
# Azure OpenAI Backend (alternative to Ollama)
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.com

# Customize backend display names in UI
LLM_OLLAMA_DISPLAY_NAME=Local AI
LLM_AZURE_OPENAI_DISPLAY_NAME=FernUni

# Advanced settings (SSL, timeouts, fallback hosts)
# See .env.example for all available options
```

## Docker Deployment

```bash
docker build -t coffee .
docker run -p 8000:8000 coffee
```

## LLM Backends

Supports multiple AI backends:
- **Ollama**: Local or remote Ollama instances with fallback support
- **Azure OpenAI**: GPT-4, GPT-3.5-turbo deployments

## Usage

1. **Admin**: Create courses, tasks, and criteria at `/admin/`
2. **Students**: Submit work and receive AI feedback
3. **Analysis**: View feedback analytics and export data

## Credits

This project was developed with assistance from [Claude Code](https://claude.ai/code), Anthropic's AI coding assistant.

## License

See LICENSE.md for details.