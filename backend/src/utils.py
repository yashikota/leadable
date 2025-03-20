import urllib.parse
import urllib.request

from model import url


def decode_url(url: str) -> str:
    return urllib.parse.unquote(url)


async def health_check():
    return {"status": "ok"}


async def health_check_ollama():
    try:
        with urllib.request.urlopen(url) as res:
            return {"message": res.read().decode("utf-8")}
    except Exception as e:
        return {"error": str(e)}
