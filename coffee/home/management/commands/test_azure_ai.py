from django.core.management.base import BaseCommand
from django.conf import settings
import logging
from coffee.home.azure_ai_api import get_azure_ai_client, list_azure_ai_models, generate_azure_ai_response

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test Azure AI Integration'

    def handle(self, *args, **options):
        self.stdout.write("Testing Azure AI Integration...")
        
        # Test configuration
        self.stdout.write("\n=== Configuration ===")
        self.stdout.write(f"Endpoint: {getattr(settings, 'AZURE_AI_ENDPOINT', 'Not configured')}")
        self.stdout.write(f"API Version: {getattr(settings, 'AZURE_AI_API_VERSION', 'Not configured')}")
        self.stdout.write(f"Has API Key: {'Yes' if getattr(settings, 'AZURE_AI_API_KEY', '') else 'No'}")
        self.stdout.write(f"Model Names: {getattr(settings, 'AZURE_AI_MODEL_NAMES', [])}")
        
        # Test client creation
        self.stdout.write("\n=== Client Test ===")
        try:
            client = get_azure_ai_client()
            if client:
                self.stdout.write(self.style.SUCCESS("✓ Azure AI client created successfully"))
            else:
                self.stdout.write(self.style.ERROR("✗ Failed to create Azure AI client"))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Client creation error: {e}"))
            return
        
        # Test model listing
        self.stdout.write("\n=== Model Listing Test ===")
        try:
            models = list_azure_ai_models()
            if models:
                self.stdout.write(self.style.SUCCESS(f"✓ Found {len(models)} models:"))
                for model in models:
                    self.stdout.write(f"  - {model['name']} ({model['backend']})")
            else:
                self.stdout.write(self.style.WARNING("⚠ No models found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Model listing error: {e}"))
        
        # Test response generation (if models available)
        if models:
            self.stdout.write("\n=== Response Generation Test ===")
            try:
                test_model = models[0]['name']
                self.stdout.write(f"Testing with model: {test_model}")
                
                response = generate_azure_ai_response(
                    test_model,
                    "Say hello in one sentence.",
                    "You are a helpful assistant."
                )
                
                if response and not response.startswith("Error:"):
                    self.stdout.write(self.style.SUCCESS("✓ Response generation successful"))
                    self.stdout.write(f"Response: {response[:100]}{'...' if len(response) > 100 else ''}")
                else:
                    self.stdout.write(self.style.ERROR(f"✗ Response generation failed: {response}"))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Response generation error: {e}"))
        
        self.stdout.write("\n=== Test Complete ===")