# leadable

論文向けPDF翻訳サービス「[Index_PDF_Translation](https://github.com/Mega-Gorilla/Index_PDF_Translation)」の[フォーク](https://github.com/chitsii/Index_PDF_Translation)をフォークし、ローカル環境の大規模言語モデルを利用して翻訳するように変更したものです。
英日翻訳にのみ対応。

## システム要件

利用中のモデル「[gemma-2-2b-jpn-it:q8_0](https://ollama.com/lucas2024/gemma-2-2b-jpn-it:q8_0)」で推論可能なメモリが必要

## Docker

```sh
docker compose up --build
```

## 利用方法

1. [Ollama](https://ollama.com)をインストール
2. `ollama pull lucas2024/gemma-2-2b-jpn-it:q8_0`
3. [uv](https://github.com/astral-sh/uv)をインストール
4. `uv sync`
5. `uv run src/main.py`
