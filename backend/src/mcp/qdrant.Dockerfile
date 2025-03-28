ARG PYTHON_VERSION=3.12
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING="UTF-8" \
    PYTHONBREAKPOINT="IPython.terminal.debugger.set_trace" \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Expose the default port for SSE transport
EXPOSE 8000

# Set environment variables with defaults that can be overridden at runtime
ENV QDRANT_URL="http://qdrant:6333"
ENV COLLECTION_NAME="leadable"
ENV EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"

CMD ["uvx", "mcp-server-qdrant", "--transport", "sse"]
