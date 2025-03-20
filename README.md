# Leadable

論文向けPDF翻訳サービス「[Index_PDF_Translation](https://github.com/Mega-Gorilla/Index_PDF_Translation)」の[フォーク](https://github.com/chitsii/Index_PDF_Translation)をフォークし、ローカル環境の大規模言語モデルを利用して翻訳するように変更したものです。
英日翻訳にのみ対応。

## 使い方

1. 翻訳したいPDFをエリアにドロップ
   ![first look](images/firstlook.png)

2. 正しくPDFファイルが読み込まれた場合
   ![upload](images/upload.png)

3. PDFファイル以外をドロップした場合
   ![error](images/error.png)

4. 「Translate」を押して翻訳をし，翻訳が完了したら「Download translated file」のボタンが現れる
   ![translate](images/translate.png)

## 運用方法

立ち上げ  

```sh
make run
```

終了する場合は  

```sh
make down
```

## 開発

### セットアップ

開発環境のツール管理には[aqua](https://aquaproj.github.io)を使用しています。  

1. aquaのインストール
   [公式サイトのinstal](https://aquaproj.github.io/docs/install)を参考にインストールしてください。  
2. `aqua i -l` を実行
3. `docker`, `ollama`, `pnpm`, `uv`が使用可能になります。  

### オプション

OllamaのサーバーのURLとバックエンドのAPIのURLは環境変数を定義することで任意に変更可能です。  

```txt
OLLAMA_HOST_URL="http://localhost:8000"
VITE_LEADABLE_API_URL="http://localhost:5173"
```

### 技術スタック

#### バックエンド

* Python
* FastAPI

#### フロントエンド

* React
* Vite
* Tailwind
* Daisy UI
