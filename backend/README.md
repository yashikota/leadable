# backend

To change the Ollama URL, use `OLLAMA_HOST=http://localhost:11434`

## Local Development

1. Install [Ollama](https://ollama.com)
2. `ollama pull lucas2024/gemma-2-2b-jpn-it:q8_0`
3. `uv sync`
4. `uv run fastapi dev src/main.py`
