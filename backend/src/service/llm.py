import requests
from litellm import NotFoundError, completion
from ollama import Client

from service.log import logger

OLLAMA_HOST_URL = "http://ollama:11434"


def get_ollama_client() -> Client:
    return Client(host=OLLAMA_HOST_URL)


async def get_models():
    try:
        ollama_models = await get_ollama_models()
        openai_models = await get_openapi_models()
        anthropic_models = await get_anthropic_models()
        google_models = await get_google_models()
        deepseek_models = await get_deepseek_models()
        return {
            "ollama": ollama_models,
            "openai": openai_models,
            "anthropic": anthropic_models,
            "google": google_models,
            "deepseek": deepseek_models,
        }
    except Exception as e:
        return str(e)


async def get_ollama_models():
    try:
        client = get_ollama_client()
        return [model["name"] for model in client.list().get("models", [])]
    except Exception as e:
        return str(e)


async def get_openapi_models():
    try:
        url = "https://llm-models-api.yashikota.workers.dev/models?provider=openai"
        res = requests.get(url).json()
        return [model["id"].split("/")[1] for model in res.get("data", [])]
    except Exception as e:
        return str(e)


async def get_anthropic_models():
    try:
        url = "https://llm-models-api.yashikota.workers.dev/models?provider=anthropic"
        res = requests.get(url).json()
        return [model["id"].split("/")[1] for model in res.get("data", [])]
    except Exception as e:
        return str(e)


async def get_google_models():
    try:
        url = "https://llm-models-api.yashikota.workers.dev/models?provider=google&strip_suffix=true"
        res = requests.get(url).json()
        return [
            model["id"].split("/")[1]
            for model in res.get("data", [])
            if "gemini" in model["id"].split("/")[1]
        ]
    except Exception as e:
        return str(e)


async def get_deepseek_models():
    try:
        url = "https://llm-models-api.yashikota.workers.dev/models?provider=deepseek&ignore_free=true"
        res = requests.get(url).json()
        return [model["id"].split("/")[1] for model in res.get("data", [])]
    except Exception as e:
        return str(e)


async def check_valid_model(provider, model, api_key: str) -> bool:
    try:
        response = completion(
            model=f"{convert_model(provider, model)}",
            messages=[{"role": "user", "content": "あなたは誰？"}],
            api_key=api_key,
        )
        logger.info(f"Model check response: {response}")
        return True
    except NotFoundError:
        return False


def convert_model(provider, model):
    if provider == "google":
        model = f"gemini/{model}"
    elif provider == "deepseek":
        model = f"deepseek/{model}"
    elif provider == "ollama":
        model = f"ollama_chat/{model}"
    return model
