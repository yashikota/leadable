# backend

To change the Ollama URL, use `OLLAMA_HOST=http://localhost:8434`

## Local Development

1. Install [Ollama](https://ollama.com)
2. `ollama pull hf.co/mmnga/sarashina2.2-3b-instruct-v0.1-gguf`
3. `uv sync`
4. `uv run fastapi dev src/main.py`
5. Deploy to `http://localhost:8866`

## Docs

<http://localhost:8866/docs>
