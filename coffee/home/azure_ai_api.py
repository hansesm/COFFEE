import os
import logging
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from django.conf import settings

logger = logging.getLogger(__name__)

def get_azure_ai_client():
    """
    Creates and returns an Azure AI Inference Client.
    """
    try:
        endpoint = getattr(settings, 'AZURE_AI_ENDPOINT', '')
        api_key = getattr(settings, 'AZURE_AI_API_KEY', '')
        api_version = getattr(settings, 'AZURE_AI_API_VERSION', '2024-05-01-preview')
        
        if not endpoint or not api_key:
            logger.error("Azure AI endpoint or API key not configured")
            return None
            
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
            api_version=api_version
        )
        
        logger.info("Azure AI client created successfully")
        return client
        
    except Exception as e:
        logger.error(f"Failed to create Azure AI client: {e}")
        return None

def list_azure_ai_models():
    """
    Returns available Azure AI models from configuration.
    Uses hardcoded model names from settings.
    """
    try:
        model_names = getattr(settings, 'AZURE_AI_MODEL_NAMES', 'Phi-4')
        
        # Handle both string and list configurations
        if isinstance(model_names, str):
            model_names = [name.strip() for name in model_names.split(',')]
        
        models = []
        for model_name in model_names:
            if model_name.strip():  # Skip empty strings
                models.append({
                    'name': model_name.strip(),
                    'backend': 'azure_ai'
                })
        
        logger.info(f"Found {len(models)} configured Azure AI models")
        return models
        
    except Exception as e:
        logger.error(f"Failed to list Azure AI models: {e}")
        return []

def stream_azure_ai_response(model_name, user_input, system_prompt):
    """
    Stream response from Azure AI Inference.
    
    Args:
        model_name: The Azure AI model name
        user_input: User's input text
        system_prompt: System prompt for the model
    
    Yields:
        str: Streamed response chunks
    """
    try:
        client = get_azure_ai_client()
        if not client:
            yield "Error: Could not connect to Azure AI"
            return
        
        messages = [
            SystemMessage(content=system_prompt),
            UserMessage(content=user_input)
        ]
        
        logger.info(f"Starting Azure AI stream for model: {model_name}")
        logger.info(f"Using endpoint: {getattr(settings, 'AZURE_AI_ENDPOINT', '')}")
        logger.info(f"Using API version: {getattr(settings, 'AZURE_AI_API_VERSION', '2024-05-01-preview')}")
        
        response = client.complete(
            messages=messages,
            model=model_name,
            max_tokens=getattr(settings, 'AZURE_AI_MAX_TOKENS', 2048),
            temperature=getattr(settings, 'AZURE_AI_TEMPERATURE', 0.8),
            top_p=getattr(settings, 'AZURE_AI_TOP_P', 0.1),
            presence_penalty=getattr(settings, 'AZURE_AI_PRESENCE_PENALTY', 0.0),
            frequency_penalty=getattr(settings, 'AZURE_AI_FREQUENCY_PENALTY', 0.0),
            stream=True
        )
        
        for chunk in response:
            logger.debug(f"Chunk: {chunk}")
            if hasattr(chunk, 'choices') and chunk.choices and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                if hasattr(choice, 'delta') and choice.delta and hasattr(choice.delta, 'content') and choice.delta.content:
                    yield choice.delta.content
            else:
                logger.warning(f"Empty choices in chunk: {chunk}")
                
    except Exception as e:
        error_msg = f"Azure AI streaming error: {str(e)}"
        logger.error(error_msg)
        yield error_msg

def generate_azure_ai_response(model_name, user_input, system_prompt):
    """
    Generate complete response from Azure AI (non-streaming).
    
    Args:
        model_name: The Azure AI model name
        user_input: User's input text
        system_prompt: System prompt for the model
    
    Returns:
        str: Complete response text
    """
    try:
        client = get_azure_ai_client()
        if not client:
            return "Error: Could not connect to Azure AI"
        
        messages = [
            SystemMessage(content=system_prompt),
            UserMessage(content=user_input)
        ]
        
        logger.info(f"Generating Azure AI response for model: {model_name}")
        
        response = client.complete(
            messages=messages,
            model=model_name,
            max_tokens=getattr(settings, 'AZURE_AI_MAX_TOKENS', 2048),
            temperature=getattr(settings, 'AZURE_AI_TEMPERATURE', 0.8),
            top_p=getattr(settings, 'AZURE_AI_TOP_P', 0.1),
            presence_penalty=getattr(settings, 'AZURE_AI_PRESENCE_PENALTY', 0.0),
            frequency_penalty=getattr(settings, 'AZURE_AI_FREQUENCY_PENALTY', 0.0)
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        error_msg = f"Azure AI generation error: {str(e)}"
        logger.error(error_msg)
        return error_msg