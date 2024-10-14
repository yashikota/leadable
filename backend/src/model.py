import os

from ollama import Client

client = Client(host=os.environ.get("OLLAMA_HOST_URL", "http://ollama:11434"))


async def show_models():
    try:
        return client.list()
    except Exception as e:
        return {"error": str(e)}


async def download_model(model_name: str) -> dict:
    try:
        return client.pull(model_name)
    except Exception as e:
        return {"error": str(e)}
