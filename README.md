# Leadable

論文向けPDF翻訳サービス「[Index_PDF_Translation](https://github.com/Mega-Gorilla/Index_PDF_Translation)」の[フォーク](https://github.com/chitsii/Index_PDF_Translation)をフォークし、ローカル環境の大規模言語モデルを利用して翻訳するように変更したものです。
英日翻訳にのみ対応。

## System requirements

利用中のモデル「[gemma-2-2b-jpn-it:q8_0](https://ollama.com/lucas2024/gemma-2-2b-jpn-it:q8_0)」で推論可能なメモリが必要。  

## 使い方

### 翻訳したいPDFをエリアにドロップ

![first look](docs/images/firstlook.png)

### 正しくPDFファイルが読み込まれた場合

![upload](docs/images/upload.png)

### PDFファイル以外をドロップした場合

![error](docs/images/error.png)

### 「Translate」を押して翻訳をし，翻訳が完了したら「Download translated file」のボタンが現れる

![translate](docs/images/translate.png)

## 立ち上げ方

あらかじめBuildKitを有効化したDocker環境を用意してください。  

```sh
docker compose up --build
```

※バックグラウンドで動作させる場合は

```sh
docker compose up -d --build
```

## ファイル構造

* `/api` バックエンド
* `/frontend` フロントエンド
* `/docs` ドキュメント
* `.env.sample` .envのサンプル（実行時はこのファイルに従って，必ず `.env` を配置すること）
* `compose.yaml` Docker Compose起動用

## 技術スタック

### バックエンド

* Python
* FastAPI

### フロントエンド

* React
* Vite
* Tailwind
