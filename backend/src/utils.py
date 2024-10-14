import urllib.parse
import urllib.request


def decode_url(url: str) -> str:
    return urllib.parse.unquote(url)


async def health_check():
    return {"status": "ok"}


async def health_check_ollama():
    url = "http://ollama:11434"
    try:
        urllib.request.urlopen(url)
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}
