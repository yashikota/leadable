# Leadable

論文向けPDF翻訳サービス「[Index_PDF_Translation](https://github.com/Mega-Gorilla/Index_PDF_Translation)」の[フォーク](https://github.com/chitsii/Index_PDF_Translation)をフォークし、ローカル環境の大規模言語モデルを利用して翻訳するように変更したものです。
英日翻訳にのみ対応。

## 使い方

1. 翻訳したいPDFをエリアにドロップ or クリックでファイルダイアログから選択
   ![1](docs/images/1.png)

2. `PDFを翻訳` ボタンを押して翻訳を実行する
   ![2](docs/images/2.png)

3. 翻訳が完了したら `ダウンロード` のボタンが現れる。また履歴に追加される。  
   ![3](docs/images/3.png)

## 運用方法

### 開始  

```sh
make up
```

`http://localhost:8877` にウェブアプリが立ち上がる。  

### 終了  

```sh
make down
```

## 開発

1. [aquaをインストール](https://aquaproj.github.io/docs/install)
2. `aqua i -l`
