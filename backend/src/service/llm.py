import os

from ollama import Client

OLLAMA_HOST_URL = os.environ.get("OLLAMA_HOST_URL", "http://ollama:11434")


def get_ollama_client() -> Client:
    """
    Initialize and return an Ollama client.
    """
    return Client(host=OLLAMA_HOST_URL)


async def show_models() -> dict:
    """
    List all available models from Ollama.

    Returns:
        Dictionary containing the list of models or error information
    """
    try:
        client = get_ollama_client()
        return client.list()
    except Exception as e:
        return {"error": str(e), "message": "Failed to retrieve models list"}


async def download_model(model_name: str) -> dict:
    """
    Download a model from Ollama.

    Args:
        model_name: Name of the model to download

    Returns:
        Dictionary containing the download status or error information
    """
    try:
        client = get_ollama_client()
        return client.pull(model_name)
    except Exception as e:
        return {"error": str(e), "message": f"Failed to download model: {model_name}"}
