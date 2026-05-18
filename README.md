# hyakumeiten-list

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

## 地域別の統合CSVを作る

My Maps に入れやすいように、地域別の統合 CSV を 5 分類で作れます。

```bash
python3 scripts/build_region_csv.py --year 2025
```

出力先:

- `data/2025/all.csv`
- `data/2025/by_region/tohoku_hokkaido.csv`
- `data/2025/by_region/kanto.csv`
- `data/2025/by_region/chubu.csv`
- `data/2025/by_region/kansai.csv`
- `data/2025/by_region/chugoku_shikoku_kyushu.csv`

このコマンドは `data/2025/by_genre/*.csv` から `all.csv` と地域別 CSV を再構築します。

住所が取れない店舗は `data/<year>/by_region/unknown.csv` に入ります。

地域の分け方は次の 5 区分です。

- `tohoku_hokkaido`: 東北北海道
- `kanto`: 関東
- `chubu`: 中部
- `kansai`: 関西
- `chugoku_shikoku_kyushu`: 中国四国九州

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

`--genre` を指定した実行では、結合結果は `data/<year>/selected.csv` に出力されます。`all.csv` を維持したい場合は `python3 scripts/build_region_csv.py --year <year>` で再構築してください。

## My Maps向けの使い分け

- 全件を入れたい場合は `data/2025/all.csv`
- 地域ごとに分けたい場合は `data/2025/by_region/*.csv`
- ジャンルごとに色分けしたい場合は `data/2025/by_genre/*.csv`

## 全年度の統合CSVを作る

年を跨いだ全件 CSV と地域別 CSV を作れます。

```bash
python3 scripts/build_all_years_csv.py
```

この集計では、同じ `Website` の店舗は 1 行にまとめます。
`Year`、`Genre`、`Genre Slug`、`Release Date` は ` | ` 区切りの複数値になります。

出力先:

- `data/all_years/all.csv`
- `data/all_years/by_region/tohoku_hokkaido.csv`
- `data/all_years/by_region/kanto.csv`
- `data/all_years/by_region/chubu.csv`
- `data/all_years/by_region/kansai.csv`
- `data/all_years/by_region/chugoku_shikoku_kyushu.csv`
- `data/all_years/by_region/unknown.csv`
