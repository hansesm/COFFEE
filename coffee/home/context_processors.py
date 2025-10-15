# In yourapp/context_processors.py
from django.conf import settings

def add_is_manager(request):
    if request.user.is_authenticated:
        return {"is_manager": request.user.groups.filter(name="manager").exists()}
    return {}

def app_version(request):
    """Make app version available in all templates"""
    return {
        'app_version': getattr(settings, 'APP_VERSION', '1.0.0') # TODO get version from pyproject.toml
    }
