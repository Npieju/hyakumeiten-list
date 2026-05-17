# hyakummeiten-list

食べログ 百名店を年別・ジャンル別の CSV に整形して、Google My Maps に取り込みやすくするためのスクレイパーです。

現状は `2025` 年を対象にしています。

## セットアップ

```bash
pip install -r requirements.txt
```

環境によっては `python3 -m venv` や `ensurepip` が使えない場合があります。その場合は、利用可能な Python 環境で `requests` と `beautifulsoup4` を導入してください。

## 2025年のジャンル一覧だけ作る

```bash
python3 scripts/scrape_hyakumeiten.py --year 2025 --genres-only
```

出力先:

- `data/2025/genres.csv`

## 2025年の全ジャンルCSVを作る

```bash
python3 scripts/scrape_hyakumeiten.py --year 2025 --throttle-seconds 0 --workers 4
```

出力先:

- `data/2025/genres.csv`
- `data/2025/all.csv`
- `data/2025/by_genre/*.csv`

Google My Maps 向けに、各店舗 CSV には以下を含めます。

- `Name`
- `Address`
- `Description`
- `Website`
- `Google Maps URL`
- `Year`
- `Genre`
- `Genre Slug`
- `Release Date`

## 主なオプション

- `--genre <slug>`: 特定ジャンルだけ出力
- `--genres-only`: ジャンル一覧だけ出力
- `--throttle-seconds <float>`: リクエスト間の待機秒数
- `--workers <int>`: 店舗詳細の並列取得数
