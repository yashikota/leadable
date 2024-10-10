import urllib.parse


def decode_url(url: str) -> str:
    return urllib.parse.unquote(url)


async def health_check():
    return {"status": "ok"}
