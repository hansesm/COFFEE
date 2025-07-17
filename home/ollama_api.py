import logging
import os
from dotenv import load_dotenv
from ollama import Client

load_dotenv()

PRIMARY_HOST = os.getenv("PRIMARY_HOST", "")
PRIMARY_DEFAULT_HEADER = {
    "Authorization": f"Bearer {os.getenv('PRIMARY_API_TOKEN', '')}",
    "Content-Type": "application/json",
}

FALLBACK_HOST = os.getenv("FALLBACK_HOST", "")
FALLBACK_DEFAULT_HEADER = {
    "Authorization": f"Bearer {os.getenv('FALLBACK_API_TOKEN', '')}",
    "Content-Type": "application/json",
}

VERIFY_SSL = os.getenv("VERIFY_SSL", "True").lower() == "true"

def get_client():
    """
    Creates and returns an Ollama Client.
    It tries the PRIMARY_HOST first and falls back to FALLBACK_HOST if necessary.
    """
    try:
        client = Client(
            host=PRIMARY_HOST,
            headers=PRIMARY_DEFAULT_HEADER,
            verify=VERIFY_SSL,
        )
        #lightweight operation here to verify connectivity.
        client.list()
        return client
    except Exception as primary_error:
        logging.error("Primary host failed: %s", primary_error)
        print("Primary host failed: " + str(primary_error))
        try:
            client = Client(
                host=FALLBACK_HOST,
                headers=FALLBACK_DEFAULT_HEADER,
                verify=False
            )
            return client
        except Exception as fallback_error:
            logging.error("Fallback host also failed: %s", fallback_error)
            print("Fallback host also failed: " + str(fallback_error))
            # Reraise the exception so the calling function knows something went wrong.
            raise fallback_error

def stream_chat_response(prompt, model="phi4:latest"):
    """
    Uses the Ollama Client to call the chat API with streaming enabled.
    The client is configured with a primary host and falls back to an alternative host if needed.
    """
    try:
        client = get_client()
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
        return model_names
    except Exception as e:
        logging.error("Error during listing models: %s", e)
        return []