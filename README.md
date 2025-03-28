# Leadable

論文向けPDF翻訳サービス「[Index_PDF_Translation](https://github.com/Mega-Gorilla/Index_PDF_Translation)」の[フォーク](https://github.com/chitsii/Index_PDF_Translation)をフォークし、ローカル環境の大規模言語モデルを利用して翻訳するように変更したものです。
英日翻訳にのみ対応。

## 使い方

![1](docs/images/1.png)

1. 翻訳したいPDFを上部エリアにドロップ or クリックでファイルダイアログから選択し、アップロードする

2. アップロード完了後、一覧に追加される。ステータスは `待機中`, `処理中`, `完了`, `失敗` の4つ。リロードしなくても自動更新される。  

3. 下部のLLM設定から、翻訳に使用するプロバイダーとモデルを選択可能。プロバイダーは `Ollama (local)`, `OpenAI`, `Anthropic`, `Gemini`, `DeepSeek` の5つ。Ollama以外はAPI Keyが必須。  

## 立ち上げ

`.evn.example` を参考に `.env` を作成してください。  

```sh
make up
```

<http://localhost:8877> にアプリケーションが立ち上がります
