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

def get_client():
    """
    Creates and returns an Ollama Client.
    It tries the primary host first and falls back to fallback host if necessary.
    """
    try:
        client = Client(
            host=settings.OLLAMA_PRIMARY_HOST,
            headers=get_primary_headers(),
            verify=settings.OLLAMA_VERIFY_SSL,
            timeout=settings.OLLAMA_REQUEST_TIMEOUT,
        )
        # Lightweight operation here to verify connectivity
        client.list()
        logging.info("Connected to primary Ollama host: %s", settings.OLLAMA_PRIMARY_HOST)
        return client
    except Exception as primary_error:
        logging.error("Primary host failed: %s", primary_error)
        print("Primary host failed: " + str(primary_error))
        
        if not settings.OLLAMA_ENABLE_FALLBACK:
            logging.error("Fallback is disabled, raising primary error")
            raise primary_error
            
        try:
            client = Client(
                host=settings.OLLAMA_FALLBACK_HOST,
                headers=get_fallback_headers(),
                verify=False,  # Fallback typically uses less secure connection
                timeout=settings.OLLAMA_REQUEST_TIMEOUT,
            )
            logging.info("Connected to fallback Ollama host: %s", settings.OLLAMA_FALLBACK_HOST)
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
    Uses the Ollama Client to retrieve the list of available models.
    The client is configured with a primary host and falls back to an alternative host if needed.
    Returns a list of model names as strings (or an empty list in case of an error).
    """
    try:
        client = get_client()
        response = client.list()
        logging.info("Retrieved models response: %s", response)
        # Extract the list of models from the response.
        # (Assuming the response contains an attribute 'models' with the list.)
        models = response.models
        # Build a list of model names.
        model_names = [m.model for m in models]
        logging.info("Available models: %s", model_names)
        return model_names
    except Exception as e:
        logging.error("Error during listing models: %s", e)
        return []

def get_ollama_config():
    """
    Returns the current Ollama configuration for debugging/info purposes.
    """
    return {
        "primary_host": settings.OLLAMA_PRIMARY_HOST,
        "fallback_host": settings.OLLAMA_FALLBACK_HOST,
        "verify_ssl": settings.OLLAMA_VERIFY_SSL,
        "default_model": settings.OLLAMA_DEFAULT_MODEL,
        "request_timeout": settings.OLLAMA_REQUEST_TIMEOUT,
        "enable_fallback": settings.OLLAMA_ENABLE_FALLBACK,
        "has_primary_auth": bool(settings.OLLAMA_PRIMARY_AUTH_TOKEN),
        "has_fallback_auth": bool(settings.OLLAMA_FALLBACK_AUTH_TOKEN),
    }

