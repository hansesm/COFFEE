# COFFEE - Corrective Formative Feedback

COFFEE is a Django-based web application designed for educational institutions to provide AI-powered feedback on student submissions. The system enables instructors to create courses, tasks, and evaluation criteria, while students can submit their work and receive automated feedback powered by Large Language Models (LLMs).

## Features

### Core Functionality
- **Course Management**: Create and manage courses with faculty, study programmes, and terms
- **Task Creation**: Define assignments and tasks for courses
- **Criteria Management**: Set up evaluation criteria with custom prompts for AI feedback
- **Feedback System**: Automated feedback generation using configurable LLM models
- **User Groups**: Role-based access control with editing and viewing permissions
- **Session Tracking**: Track feedback sessions with NPS scoring
- **Multi-language Support**: German and English localization

### Technical Features
- **AI Integration**: Supports multiple LLM models via Ollama API
- **Streaming Responses**: Real-time feedback generation with streaming support
- **Data Export**: CSV export functionality for analytics
- **Responsive Design**: Modern web interface with Bootstrap
- **Group-based Permissions**: Granular access control for courses and content
- **Database Support**: PostgreSQL with UUID primary keys

## Technology Stack

- **Backend**: Django 5.2.4
- **Database**: PostgreSQL (with psycopg2-binary)
- **AI/ML**: Ollama integration for LLM models
- **Frontend**: Bootstrap, HTML5, CSS3, JavaScript
- **Deployment**: Docker, Kubernetes, Podman support
- **Web Server**: Gunicorn with WhiteNoise for static files

## Installation

### Prerequisites
- Python 3.8+
- PostgreSQL
- Ollama (for AI feedback functionality)
- Docker (optional, for containerized deployment)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd COFFEE
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Database setup**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Create users and groups**
   ```bash
   python manage.py create_users_and_groups
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

### Docker Deployment

#### Build and run with Docker
```bash
# Build the image
docker build -t fb_coffee .

# Run the container
docker run -p 8000:8000 fb_coffee
```

#### Multi-platform build and push
```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/hansesm/fb_coffee:latest \
  --tag ghcr.io/hansesm/fb_coffee:v2.7 \
  --push .
```

### Kubernetes Deployment

```bash
# Deploy the application
kubectl delete -f deployment-app.yaml
kubectl create -f deployment-app.yaml
```

### Podman Deployment

```bash
# Deploy with Podman
sudo podman play kube --replace podman-deployment.yaml

# Access the container
sudo podman exec -it feedback-app-pod-feedback-app /bin/bash
```

#### Podman Autostart Setup
```bash
sudo podman generate systemd --name feedback-app-pod --files
sudo mv pod-feedback-app-pod.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pod-feedback-app-pod
sudo systemctl start pod-feedback-app-pod
systemctl status pod-feedback-app-pod
```

## Configuration

### Environment Variables
Create a `.env` file in the project root:

```env
# Django Configuration
DEBUG=False
SECRET_KEY=your-secret-key-here

# Database Configuration
DB_ENGINE=django.db.backends.postgresql
DB_NAME=coffee_db
DB_USERNAME=your_db_user
DB_PASS=your_db_password
DB_HOST=localhost
DB_PORT=5432

# Ollama API Configuration
OLLAMA_PRIMARY_HOST=https://your-ollama-host.com/ollama
OLLAMA_PRIMARY_AUTH_TOKEN=your-primary-auth-token
OLLAMA_FALLBACK_HOST=http://localhost:11434
OLLAMA_FALLBACK_AUTH_TOKEN=your-fallback-auth-token
OLLAMA_VERIFY_SSL=True
OLLAMA_DEFAULT_MODEL=phi4:latest
OLLAMA_REQUEST_TIMEOUT=300
OLLAMA_ENABLE_FALLBACK=True
```

### Ollama API Configuration

The application supports configurable Ollama API settings with primary and fallback hosts:

#### Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `OLLAMA_PRIMARY_HOST` | `https://chat-impact.fernuni-hagen.de/ollama` | Primary Ollama API endpoint |
| `OLLAMA_PRIMARY_AUTH_TOKEN` | - | Authentication token for primary host |
| `OLLAMA_FALLBACK_HOST` | `http://catalpa-llm.fernuni-hagen.de:11434/` | Fallback Ollama API endpoint |
| `OLLAMA_FALLBACK_AUTH_TOKEN` | - | Authentication token for fallback host |
| `OLLAMA_VERIFY_SSL` | `True` | Whether to verify SSL certificates |
| `OLLAMA_DEFAULT_MODEL` | `phi4:latest` | Default model to use when none specified |
| `OLLAMA_REQUEST_TIMEOUT` | `300` | Request timeout in seconds |
| `OLLAMA_ENABLE_FALLBACK` | `True` | Whether to attempt fallback on primary failure |

#### Ollama Setup Examples

**Local Ollama Instance:**
```env
OLLAMA_PRIMARY_HOST=http://localhost:11434
OLLAMA_PRIMARY_AUTH_TOKEN=
OLLAMA_FALLBACK_HOST=http://localhost:11434
OLLAMA_FALLBACK_AUTH_TOKEN=
OLLAMA_VERIFY_SSL=False
OLLAMA_ENABLE_FALLBACK=False
```

**Remote Ollama with Authentication:**
```env
OLLAMA_PRIMARY_HOST=https://your-ollama-server.com/api
OLLAMA_PRIMARY_AUTH_TOKEN=your-api-token
OLLAMA_FALLBACK_HOST=http://localhost:11434
OLLAMA_FALLBACK_AUTH_TOKEN=
OLLAMA_VERIFY_SSL=True
OLLAMA_ENABLE_FALLBACK=True
```

**High Availability Setup:**
```env
OLLAMA_PRIMARY_HOST=https://ollama-primary.example.com
OLLAMA_PRIMARY_AUTH_TOKEN=primary-token
OLLAMA_FALLBACK_HOST=https://ollama-backup.example.com
OLLAMA_FALLBACK_AUTH_TOKEN=backup-token
OLLAMA_VERIFY_SSL=True
OLLAMA_ENABLE_FALLBACK=True
```

### Database Configuration
Update `core/settings.py` for your database configuration:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'coffee_db',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## Usage

### Initial Setup

1. **Access the admin interface** at `http://localhost:8000/admin/`
2. **Create user groups** for instructors and students
3. **Set up courses** with appropriate viewing and editing permissions
4. **Create tasks** for your courses
5. **Define evaluation criteria** with custom prompts

### Creating Feedback Systems

1. **Navigate to Course Management** to create a new course
2. **Add Tasks** that students will submit work for
3. **Create Criteria** with custom prompts for AI evaluation
4. **Set up Feedback** by linking tasks with evaluation criteria
5. **Configure LLM models** in the criteria settings

### Student Workflow

1. **Access the feedback system** via the provided URL
2. **Submit their work** in the designated text area
3. **Receive AI-powered feedback** based on configured criteria
4. **Rate the feedback** using the NPS scoring system

## Internationalization

The application supports multiple languages:

### Adding New Languages
```bash
# Generate message files for German
python manage.py makemessages -l de

# Generate message files for English  
python manage.py makemessages -l en

# Compile translations
python manage.py compilemessages
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test home

# Run with verbose output
python manage.py test home --verbosity=2
```

### Test Coverage
The test suite includes:
- Model validation tests
- View functionality tests
- Form validation tests
- Permission system tests
- Integration tests
- API endpoint tests

## API Endpoints

### Main Endpoints
- `/` - Main feedback list view
- `/feedback/<uuid>/` - Individual feedback submission
- `/course/` - Course management (authenticated)
- `/task/` - Task management (authenticated)
- `/criteria/` - Criteria management (authenticated)
- `/analysis/` - Feedback analytics (authenticated)
- `/accounts/login/` - User authentication

### API Features
- JSON responses for AJAX requests
- Streaming responses for real-time feedback
- CSV export functionality
- Group-based permission checks

## Development

### Project Structure
```
COFFEE/
├── core/                 # Django project settings
├── home/                 # Main application
│   ├── models.py        # Database models
│   ├── views.py         # View controllers
│   ├── forms.py         # Form definitions
│   ├── tests.py         # Test suite
│   └── templates/       # HTML templates
├── static/              # Static files (CSS, JS, images)
├── requirements.txt     # Python dependencies
├── manage.py           # Django management script
└── Dockerfile          # Container configuration
```

### Key Models
- **Course**: Represents academic courses with permission groups
- **Task**: Assignments within courses
- **Criteria**: Evaluation criteria with AI prompts
- **Feedback**: Links tasks with criteria sets
- **FeedbackSession**: Individual submission sessions

### Adding New Features

1. **Models**: Define in `home/models.py`
2. **Views**: Add to `home/views.py`
3. **URLs**: Update `home/urls.py`
4. **Templates**: Create in `home/templates/`
5. **Tests**: Add to `home/tests.py`

## Security

### Permission System
- Group-based access control
- Per-course editing and viewing permissions
- User authentication required for management functions
- CSRF protection enabled

### Best Practices
- UUID primary keys for all models
- Secure password handling
- Environment variable configuration
- SQL injection protection via Django ORM

## Troubleshooting

### Common Issues

1. **Database connection errors**
   - Check PostgreSQL service status
   - Verify database credentials
   - Ensure database exists

2. **Ollama API errors**
   - Verify Ollama service is running: `curl http://localhost:11434/api/tags`
   - Check model availability: Ensure the model specified in criteria exists
   - Confirm API endpoint configuration in environment variables
   - Check authentication tokens if using secured endpoints
   - Verify SSL certificate settings (`OLLAMA_VERIFY_SSL`)
   - Test fallback configuration if primary host fails
   - Check network connectivity to Ollama hosts
   - Review timeout settings (`OLLAMA_REQUEST_TIMEOUT`)

3. **Permission errors**
   - Ensure user groups are properly configured
   - Check course permission assignments
   - Verify user group memberships

### Logs
Check application logs:
```bash
# Django logs
python manage.py runserver --verbosity=2

# Container logs
docker logs <container-name>
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests to ensure functionality
5. Submit a pull request

## License

This project is licensed under the terms specified in the LICENSE.md file.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the test suite for examples
3. Submit issues via the project's issue tracker

---

**COFFEE** - Making feedback more efficient and accessible for educational institutions.