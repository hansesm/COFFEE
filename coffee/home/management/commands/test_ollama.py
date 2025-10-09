from django.core.management.base import BaseCommand
from django.conf import settings
from coffee.home.ollama_api import get_ollama_config, get_client, list_models


class Command(BaseCommand):
    help = 'Test Ollama API configuration and connectivity'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing Ollama Configuration'))
        self.stdout.write('=' * 50)
        
        # Display current configuration
        config = get_ollama_config()
        self.stdout.write(self.style.HTTP_INFO('Current Configuration:'))
        for key, value in config.items():
            if 'auth' in key.lower():
                # Don't show full auth tokens for security
                display_value = '[SET]' if value else '[NOT SET]'
            else:
                display_value = value
            self.stdout.write(f'  {key}: {display_value}')
        
        self.stdout.write()
        
        # Test connectivity
        self.stdout.write(self.style.HTTP_INFO('Testing Connectivity:'))
        try:
            client = get_client()
            self.stdout.write(self.style.SUCCESS('✓ Successfully connected to Ollama'))
            
            # List available models
            models = list_models()
            if models:
                self.stdout.write(self.style.SUCCESS(f'✓ Found {len(models)} available models:'))
                for model in models:
                    marker = ' (default)' if model == settings.OLLAMA_DEFAULT_MODEL else ''
                    self.stdout.write(f'  - {model}{marker}')
            else:
                self.stdout.write(self.style.WARNING('⚠ No models found or unable to list models'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Connection failed: {str(e)}'))
            
        self.stdout.write()
        self.stdout.write(self.style.SUCCESS('Ollama configuration test complete'))