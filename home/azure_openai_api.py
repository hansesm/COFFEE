import os
import logging
from openai import AzureOpenAI
from django.conf import settings

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
            logging.info("Azure OpenAI client connection test successful")
            return client
        except Exception as test_error:
            logging.warning(f"Azure OpenAI client created but connection test failed: {test_error}")
            # Return client anyway, as the test might fail due to deployment configuration
            return client
            
    except Exception as e:
        logging.error(f"Failed to create Azure OpenAI client: {e}")
        return None

def list_azure_models():
    """
    Returns available Azure OpenAI models/deployments.
    Since Azure OpenAI uses deployments, we'll return configured deployment names.
    """
    try:
        deployment_name = getattr(settings, 'AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')
        deployment_names = getattr(settings, 'AZURE_OPENAI_DEPLOYMENT_NAMES', [deployment_name])
        
        # Return deployment names as model list
        models = []
        for deployment in deployment_names:
            models.append({
                'name': deployment,
                'backend': 'azure_openai'
            })
        
        logging.info(f"Found {len(models)} Azure OpenAI deployments")
        return models
        
    except Exception as e:
        logging.error(f"Failed to list Azure OpenAI deployments: {e}")
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
        
        logging.info(f"Starting Azure OpenAI stream for deployment: {deployment_name}")
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            stream=True,
            max_tokens=getattr(settings, 'AZURE_OPENAI_MAX_TOKENS', 2000),
            temperature=getattr(settings, 'AZURE_OPENAI_TEMPERATURE', 0.7),
        )
        
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
                
    except Exception as e:
        error_msg = f"Azure OpenAI streaming error: {str(e)}"
        logging.error(error_msg)
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
        
        logging.info(f"Generating Azure OpenAI response for deployment: {deployment_name}")
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            max_tokens=getattr(settings, 'AZURE_OPENAI_MAX_TOKENS', 2000),
            temperature=getattr(settings, 'AZURE_OPENAI_TEMPERATURE', 0.7),
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        error_msg = f"Azure OpenAI generation error: {str(e)}"
        logging.error(error_msg)
        return error_msg