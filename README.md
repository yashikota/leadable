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
make run
```

※バックグラウンドで動作させる場合は

```sh
make run-d
```

終了する場合は

```sh
make down
```

## オプション

OllamaのサーバーのURLとバックエンドのAPIのURLは環境変数を定義することで任意に変更可能です。  

```txt
OLLAMA_HOST_URL="http://localhost:8000"
VITE_LEADABLE_API_URL="http://localhost:5173"
```

## 技術スタック

### バックエンド

* Python
* FastAPI

### フロントエンド

* React
* Vite
* Tailwind
