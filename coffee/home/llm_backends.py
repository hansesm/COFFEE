import logging
from django.conf import settings
from .ollama_api import list_models as list_ollama_models, stream_chat_response as stream_ollama_response
from .azure_openai_api import list_azure_models, stream_azure_response
from .azure_ai_api import list_azure_ai_models, stream_azure_ai_response

def get_all_available_models():
    """
    Get all available models from all LLM backends.
    
    Returns:
        list: List of model dictionaries with 'name' and 'backend' keys
    """
    all_models = []
    
    # Get display names from settings
    display_names = getattr(settings, 'LLM_BACKEND_DISPLAY_NAMES', {
        'ollama': 'Ollama',
        'azure_openai': 'Azure OpenAI',
        'azure_ai': 'Azure AI'
    })
    
    # Get Ollama models
    try:
        ollama_models = list_ollama_models()
        ollama_display_name = display_names.get('ollama', 'Ollama')
        for model in ollama_models:
            all_models.append({
                'name': model,
                'backend': 'ollama',
                'display_name': f"{model} ({ollama_display_name})"
            })
    except Exception as e:
        logging.error(f"Failed to get Ollama models: {e}")
    
    # Get Azure OpenAI models
    try:
        azure_models = list_azure_models()
        azure_display_name = display_names.get('azure_openai', 'Azure OpenAI')
        for model in azure_models:
            all_models.append({
                'name': model['name'],
                'backend': 'azure_openai',
                'display_name': f"{model['name']} ({azure_display_name})"
            })
    except Exception as e:
        logging.error(f"Failed to get Azure OpenAI models: {e}")
    
    # Get Azure AI models
    try:
        azure_ai_models = list_azure_ai_models()
        azure_ai_display_name = display_names.get('azure_ai', 'Azure AI')
        for model in azure_ai_models:
            all_models.append({
                'name': model['name'],
                'backend': 'azure_ai',
                'display_name': f"{model['name']} ({azure_ai_display_name})"
            })
    except Exception as e:
        logging.error(f"Failed to get Azure AI models: {e}")
    
    logging.info(f"Found {len(all_models)} total models across all backends")
    return all_models

def stream_llm_response(model_name, backend, user_input, system_prompt):
    """
    Stream response from the specified LLM backend.
    
    Args:
        model_name: Name of the model/deployment
        backend: Backend type ('ollama', 'azure_openai', or 'azure_ai')
        user_input: User's input text
        system_prompt: System prompt for the model
    
    Yields:
        str: Streamed response chunks
    """
    try:
        if backend == 'ollama':
            logging.info(f"Streaming from Ollama model: {model_name}")
            # Ollama expects (prompt, model) - system_prompt is the full prompt already
            yield from stream_ollama_response(system_prompt, model_name)
        elif backend == 'azure_openai':
            logging.info(f"Streaming from Azure OpenAI deployment: {model_name}")
            yield from stream_azure_response(model_name, user_input, system_prompt)
        elif backend == 'azure_ai':
            logging.info(f"Streaming from Azure AI model: {model_name}")
            yield from stream_azure_ai_response(model_name, user_input, system_prompt)
        else:
            error_msg = f"Unsupported backend: {backend}"
            logging.error(error_msg)
            yield error_msg
            
    except Exception as e:
        error_msg = f"LLM backend error: {str(e)}"
        logging.error(error_msg)
        yield error_msg

def parse_model_backend(llm_field):
    """
    Parse the LLM field to extract model name and backend.
    Expected formats:
    - "model_name::ollama" (explicit backend)
    - "model_name::azure_openai" (explicit backend)
    - "model_name::azure_ai" (explicit backend)
    - "model_name" (defaults to ollama for backward compatibility)
    
    Args:
        llm_field: String from criteria.llm field
    
    Returns:
        tuple: (model_name, backend)
    """
    if "::" in llm_field:
        model_name, backend = llm_field.split("::", 1)
        return model_name.strip(), backend.strip()
    else:
        # Default to ollama for backward compatibility
        return llm_field.strip(), 'ollama'