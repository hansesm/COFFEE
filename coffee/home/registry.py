from django.db import models

from coffee.home.ai_provider.azure_ai_api import AzureAIClient
from coffee.home.ai_provider.configs import OllamaConfig, AzureAIConfig
from coffee.home.ai_provider.ollama_api import OllamaClient
from coffee.home.ai_provider.azure_openai_api import AzureOpenAIClient
from coffee.home.ai_provider.configs import AzureOpenAIConfig


class ProviderType(models.TextChoices):
    AZURE_AI = "azure_ai", "Azure AI"
    AZURE_OPENAI = "azure_openai", "Azure OpenAI"
    OLLAMA = "ollama", "Ollama"

SCHEMA_REGISTRY = {
    ProviderType.OLLAMA: (OllamaConfig, OllamaClient),
    ProviderType.AZURE_AI:  (AzureAIConfig, AzureAIClient),
    ProviderType.AZURE_OPENAI: (AzureOpenAIConfig, AzureOpenAIClient)
}