# これはなに？

論文向けPDF翻訳サービス「[Index_PDF_Translation](https://github.com/Mega-Gorilla/Index_PDF_Translation)」をフォークし、ローカル環境の大規模言語モデルを利用して翻訳するように変更したものです。
英日翻訳にのみ対応。

## システム要件

* VRAM / RAM: 20GB
  * 利用中のモデル「[Gemma2:24b Q4_0](https://ollama.com/library/gemma2)」で推論可能なメモリが必要

## 利用方法

1. [Ollama](https://ollama.com)をインストール
2. 言語モデル入手
   1. `ollama pull gemma2:27b`
3. 依存関係をインストール
   1. [uv](https://github.com/astral-sh/uv)、または[Python](https://www.python.org/downloads/) 3.12系をインストール
   2. リポジトリルートに移動し、
      1. uvの場合: `uv sync`
      2. pipの場合: `pip install .`
4. 仮想環境シェルからアプリ実行
   1. `. ./.venv/bin/activate`
   2. `python manual_translate.py`
