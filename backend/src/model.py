import os

from ollama import Client

client = Client(host=os.environ.get("OLLAMA_HOST", "http://ollama:11434"))


async def show_models():
    return client.list()


async def download_model(model_name: str) -> dict:
    return client.pull(model_name)
