import os
import logging
from openai import AzureOpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

def get_azure_client():
    """
    Creates and returns an Azure OpenAI Client.
    """
    try:
        client = AzureOpenAI(
            api_version=getattr(settings, 'AZURE_OPENAI_API_VERSION', '2024-12-01-preview'),
            azure_endpoint=getattr(settings, 'AZURE_OPENAI_ENDPOINT', ''),
            api_key=getattr(settings, 'AZURE_OPENAI_API_KEY', ''),
        )
        
        # Test the connection by trying to list models (if available)
        try:
            # Simple test - this might not work with all Azure OpenAI deployments
            # but it's a basic connectivity check
            response = client.chat.completions.create(
                model=getattr(settings, 'AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4'),
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
                timeout=5
            )
            logger.info("Azure OpenAI client connection test successful")
            return client
        except Exception as test_error:
            logger.warning(f"Azure OpenAI client created but connection test failed: {test_error}")
            # Return client anyway, as the test might fail due to deployment configuration
            return client
            
    except Exception as e:
        logger.error(f"Failed to create Azure OpenAI client: {e}")
        return None

def list_azure_models():
    """
    Returns available Azure OpenAI models/deployments from configuration.
    Uses hardcoded deployment names with fallback handling for removed deployments.
    """
    try:
        deployment_name = getattr(settings, 'AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')
        deployment_names = getattr(settings, 'AZURE_OPENAI_DEPLOYMENT_NAMES', [deployment_name])
        
        # Ensure deployment_names is a list
        if isinstance(deployment_names, str):
            deployment_names = [name.strip() for name in deployment_names.split(',')]
        
        models = []
        for deployment in deployment_names:
            if deployment.strip():  # Skip empty strings
                models.append({
                    'name': deployment.strip(),
                    'backend': 'azure_openai'
                })
        
        logger.info(f"Found {len(models)} configured Azure OpenAI deployments")
        return models
        
    except Exception as e:
        logger.error(f"Failed to list Azure OpenAI models: {e}")
        return []


def stream_azure_response(deployment_name, user_input, system_prompt):
    """
    Stream response from Azure OpenAI.
    
    Args:
        deployment_name: The Azure OpenAI deployment name
        user_input: User's input text
        system_prompt: System prompt for the model
    
    Yields:
        str: Streamed response chunks
    """
    try:
        client = get_azure_client()
        if not client:
            yield "Error: Could not connect to Azure OpenAI"
            return
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        logger.info(f"Starting Azure OpenAI stream for deployment: {deployment_name}")
        logger.info(f"Using endpoint: {getattr(settings, 'AZURE_OPENAI_ENDPOINT', '')}")
        logger.info(f"Using API version: {getattr(settings, 'AZURE_OPENAI_API_VERSION', '2024-12-01-preview')}")
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            stream=True,
            max_tokens=getattr(settings, 'AZURE_OPENAI_MAX_TOKENS', 2000),
            temperature=getattr(settings, 'AZURE_OPENAI_TEMPERATURE', 0.7),
        )
        
        for chunk in response:
            logger.debug(f"Chunk: {chunk}")
            if chunk.choices and len(chunk.choices) > 0:
                if hasattr(chunk.choices[0], 'delta') and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            else:
                logger.warning(f"Empty choices in chunk: {chunk}")
                
    except Exception as e:
        error_str = str(e).lower()
        if 'deploymentnotfound' in error_str or ('deployment' in error_str and 'not exist' in error_str):
            error_msg = f"Azure OpenAI deployment '{deployment_name}' not found. Please check your deployment configuration or contact your administrator."
            logger.error(f"Deployment not found: {deployment_name}")
        else:
            error_msg = f"Azure OpenAI streaming error: {str(e)}"
            logger.error(error_msg)
        yield error_msg

def generate_azure_response(deployment_name, user_input, system_prompt):
    """
    Generate complete response from Azure OpenAI (non-streaming).
    
    Args:
        deployment_name: The Azure OpenAI deployment name
        user_input: User's input text
        system_prompt: System prompt for the model
    
    Returns:
        str: Complete response text
    """
    try:
        client = get_azure_client()
        if not client:
            return "Error: Could not connect to Azure OpenAI"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        logger.info(f"Generating Azure OpenAI response for deployment: {deployment_name}")
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            max_tokens=getattr(settings, 'AZURE_OPENAI_MAX_TOKENS', 2000),
            temperature=getattr(settings, 'AZURE_OPENAI_TEMPERATURE', 0.7),
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        error_str = str(e).lower()
        if 'deploymentnotfound' in error_str or ('deployment' in error_str and 'not exist' in error_str):
            error_msg = f"Azure OpenAI deployment '{deployment_name}' not found. Please check your deployment configuration or contact your administrator."
            logger.error(f"Deployment not found: {deployment_name}")
        else:
            error_msg = f"Azure OpenAI generation error: {str(e)}"
            logger.error(error_msg)
        return error_msg