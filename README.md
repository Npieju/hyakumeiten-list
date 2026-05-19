# hyakumeiten-list

食べログ 百名店を年別・ジャンル別の CSV に整形して、Google My Maps に取り込みやすくするためのスクレイパーです。

同じ repo の中で、予約検索向けの検索マスタ実装も進めます。別 repo に切らず、既存の `data/` と `scripts/` を土台に段階的に追加する方針です。

現在は CSV / SQLite 生成に加えて、同じ検索マスタを使う地図 Web アプリも同 repo に載せる前提です。

CSV データの仕様は [docs/csv-data-spec.md](/home/yt/Projects/hyakummeiten-list/docs/csv-data-spec.md) にあります。
予約サイト連携を含む次フェーズの要求仕様は [docs/reservation-search-requirements.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-requirements.md) にあります。
設計書は [docs/reservation-search-spec.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-spec.md) にあります。
実装計画は [docs/reservation-search-implementation-plan.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-implementation-plan.md) にあります。

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

## 予約検索向けの検索マスタを作る

予約検索フェーズの初期実装として、年別 `by_genre` CSV から SQLite の検索マスタを作れます。

```bash
python3 scripts/build_shop_master.py
```

出力先:

- `data/app/hyakummeiten.sqlite3`

この DB には次が入ります。

- `shops`
- `shop_years`
- `shop_genres`
- `reservation_links`
- `availability_cache`
- `link_review_queue`

## 検索マスタを静的検索する

API 実装前の確認用として、SQLite マスタをそのまま検索する CLI を用意しています。

```bash
python3 scripts/query_shops.py --year 2025 --genre-slug sushi_tokyo --limit 5
```

JSON で `total` と `items` を返します。

## 地図 Web アプリを起動する

検索マスタを API と地図 UI から使うには、先に SQLite を生成します。

```bash
python3 scripts/build_shop_master.py
python3 -m src.api.app
```

別ポートで起動したい場合:

```bash
PORT=8001 python3 -m src.api.app
```

起動後にブラウザで次を開きます。

- `http://127.0.0.1:8000/`

この Web アプリは次を持ちます。

- Leaflet ベースの地図表示
- 現在 viewport に対する bounding box 検索
- 店舗一覧と marker の同期表示
- `Genre Slug`、年、地域、店名、複数年掲載の filter

API 単体で確認する場合:

```bash
curl 'http://127.0.0.1:8000/health'
curl 'http://127.0.0.1:8000/v1/shops/search?year=2025&genre_slug=sushi_tokyo&limit=3'
```

## 予約サイト候補を自動紐付けする

`example_provider` を使った matching pipeline の確認手順です。

```bash
python3 scripts/match_reservation_links.py --provider example_provider --limit 50
python3 scripts/export_link_review_csv.py --provider example_provider
```

出力先:

- `data/linkage/example_provider/review_candidates.csv`

この段階では次が更新されます。

- `reservation_links`
- `link_review_queue`

## review CSV を扱う

候補 export:

```bash
python3 scripts/export_link_review_csv.py --provider example_provider --allow-empty
```

決定 import の schema 検証:

```bash
python3 scripts/import_link_review_csv.py --provider example_provider --input docs/examples/review_decisions.sample.csv --dry-run
```

CSV の列契約は [docs/reservation-link-review-spec.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-link-review-spec.md) を参照してください。

## 予約状態を CLI で確認する

予約状態付き検索は CLI でも確認できます。

```bash
python3 scripts/check_availability.py --provider example_provider --date 2026-05-25 --party-size 2 --time-window dinner --year 2025 --genre-slug sushi_tokyo --limit 10
```

`--status bookable` のように status filter を付けられます。

候補件数が広すぎる場合は `warning = live_check_limit_exceeded` が返り、未評価結果が混ざることを示します。

## 予約状態を API で確認する

予約状態付き検索 API:

```bash
curl -X POST 'http://127.0.0.1:8000/v1/shops/availability-search' \
	-H 'content-type: application/json' \
	-d '{
		"filters": {"year": [2025], "genre_slug": ["sushi_tokyo"]},
		"reservation": {
			"date": "2026-05-25",
			"party_size": 2,
			"time_window": "dinner",
			"status": ["bookable"],
			"provider": ["example_provider"]
		},
		"limit": 10,
		"offset": 0
	}'
```

レスポンスには次が含まれます。

- `total`
- `cache_hit_ratio`
- `live_checks`
- `warning`
- `items`

## 現在の rebuild / verify 順序

検索マスタから予約検索までを通す最小手順:

```bash
python3 scripts/build_shop_master.py
python3 scripts/validate_shop_master.py
python3 scripts/match_reservation_links.py --provider example_provider --limit 50
python3 scripts/check_availability.py --provider example_provider --date 2026-05-25 --party-size 2 --time-window dinner --year 2025 --genre-slug sushi_tokyo --limit 10
python3 -m src.api.app
```

運用確認項目は [docs/acceptance-checklist.md](/home/yt/Projects/hyakummeiten-list/docs/acceptance-checklist.md) にまとめています。
