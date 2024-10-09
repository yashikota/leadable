import ollama


async def show_models():
    return ollama.list()


async def download_model(model_name: str) -> dict:
    return ollama.pull(model_name)
