import logging
from ollama import Client
from django.conf import settings

def get_primary_headers():
    """Get headers for primary Ollama host"""
    headers = {"Content-Type": "application/json"}
    if settings.OLLAMA_PRIMARY_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {settings.OLLAMA_PRIMARY_AUTH_TOKEN}"
    return headers

def get_fallback_headers():
    """Get headers for fallback Ollama host"""
    headers = {"Content-Type": "application/json"}
    if settings.OLLAMA_FALLBACK_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {settings.OLLAMA_FALLBACK_AUTH_TOKEN}"
    return headers 

def get_client(timeout=None):
    """
    Creates and returns an Ollama Client.
    It tries the primary host first and falls back to fallback host if necessary.
    
    Args:
        timeout: Custom timeout in seconds. If None, uses OLLAMA_REQUEST_TIMEOUT setting.
    """
    if timeout is None:
        timeout = settings.OLLAMA_REQUEST_TIMEOUT
        
    try:
        # First try with a short timeout just for connection testing
        test_client = Client(
            host=settings.OLLAMA_PRIMARY_HOST,
            headers=get_primary_headers(),
            verify=settings.OLLAMA_PRIMARY_VERIFY_SSL,
            timeout=5,  # Short timeout for connection test
        )
        # Lightweight operation here to verify connectivity
        test_client.list()
        logging.info("Connected to primary Ollama host: %s", settings.OLLAMA_PRIMARY_HOST)
        
        # Now create the actual client with proper timeout for operations
        client = Client(
            host=settings.OLLAMA_PRIMARY_HOST,
            headers=get_primary_headers(),
            verify=settings.OLLAMA_PRIMARY_VERIFY_SSL,
            timeout=timeout,
        )
        return client
    except Exception as primary_error:
        logging.error("Primary host failed: %s", primary_error)
        print("Primary host failed: " + str(primary_error))
        
        if not settings.OLLAMA_ENABLE_FALLBACK:
            logging.error("Fallback is disabled, raising primary error")
            raise primary_error
            
        try:
            # Test fallback connection
            test_client = Client(
                host=settings.OLLAMA_FALLBACK_HOST,
                headers=get_fallback_headers(),
                verify=settings.OLLAMA_FALLBACK_VERIFY_SSL,
                timeout=5,  # Short timeout for connection test
            )
            test_client.list()
            logging.info("Connected to fallback Ollama host: %s", settings.OLLAMA_FALLBACK_HOST)
            
            # Create actual client with proper timeout
            client = Client(
                host=settings.OLLAMA_FALLBACK_HOST,
                headers=get_fallback_headers(),
                verify=settings.OLLAMA_FALLBACK_VERIFY_SSL,
                timeout=timeout,
            )
            return client
        except Exception as fallback_error:
            logging.error("Fallback host also failed: %s", fallback_error)
            print("Fallback host also failed: " + str(fallback_error))
            # Reraise the exception so the calling function knows something went wrong.
            raise fallback_error

def stream_chat_response(prompt, model=None):
    """
    Uses the Ollama Client to call the chat API with streaming enabled.
    The client is configured with a primary host and falls back to an alternative host if needed.
    """
    if model is None:
        model = settings.OLLAMA_DEFAULT_MODEL
        
    try:
        client = get_client()
        logging.info("Starting chat stream with model: %s", model)
        stream = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )
        for chunk in stream:
            try:
                yield chunk["message"]["content"]
            except KeyError:
                logging.error("Unexpected response structure: %s", chunk)
                yield "Unexpected response structure"
    except Exception as e:
        logging.error("Error during streaming chat: %s", e)
        yield f"An error occurred: {e}"

def list_models():
    """
    Returns the list of available Ollama models from configuration.
    Uses hardcoded model names from settings for consistent and fast loading.
    """
    try:
        from django.conf import settings
        
        model_names = getattr(settings, 'OLLAMA_MODEL_NAMES', 'phi4:latest')
        
        # Handle both string and list configurations
        if isinstance(model_names, str):
            model_names = [name.strip() for name in model_names.split(',')]
        
        # Filter out empty strings
        model_list = [model.strip() for model in model_names if model.strip()]
        
        logging.info("Available Ollama models from configuration: %s", model_list)
        return model_list
        
    except Exception as e:
        logging.error("Error during listing models: %s", e)
        # Return default model as fallback
        return ['phi4:latest']

def get_ollama_config():
    """
    Returns the current Ollama configuration for debugging/info purposes.
    """
    return {
        "primary_host": settings.OLLAMA_PRIMARY_HOST,
        "primary_verify_ssl": settings.OLLAMA_PRIMARY_VERIFY_SSL,
        "fallback_host": settings.OLLAMA_FALLBACK_HOST,
        "fallback_verify_ssl": settings.OLLAMA_FALLBACK_VERIFY_SSL,
        "default_model": settings.OLLAMA_DEFAULT_MODEL,
        "request_timeout": settings.OLLAMA_REQUEST_TIMEOUT,
        "enable_fallback": settings.OLLAMA_ENABLE_FALLBACK,
        "has_primary_auth": bool(settings.OLLAMA_PRIMARY_AUTH_TOKEN),
        "has_fallback_auth": bool(settings.OLLAMA_FALLBACK_AUTH_TOKEN),
    }

