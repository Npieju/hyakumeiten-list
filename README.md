# hyakumeiten-list

公開 URL: https://hyakummeiten-map.onrender.com

食べログ 百名店を年別・ジャンル別の CSV に整形して、Google My Maps に取り込みやすくするためのスクレイパーです。

同じ repo の中で、予約検索向けの検索マスタ実装も進めます。別 repo に切らず、既存の `data/` と `scripts/` を土台に段階的に追加する方針です。

現在は CSV / SQLite 生成に加えて、同じ検索マスタを使う地図 Web アプリも同 repo に載せる前提です。

CSV データの仕様は [docs/csv-data-spec.md](/home/yt/Projects/hyakummeiten-list/docs/csv-data-spec.md) にあります。
予約サイト連携を含む次フェーズの要求仕様は [docs/reservation-search-requirements.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-requirements.md) にあります。
設計書は [docs/reservation-search-spec.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-spec.md) にあります。
実装計画は [docs/reservation-search-implementation-plan.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-implementation-plan.md) にあります。

現状は `2025` 年を対象にしています。

## 無料公開

現状の構成では、公開先の第一候補は `Render Free Web Service` です。

理由:

- FastAPI をそのまま載せられる
- GitHub 連携だけで deploy できる
- クレジットカード前提の設定を避けやすい
- SQLite 検索 DB は deploy 時に `scripts/build_shop_master.py` で再生成できる

この repo には Render 用の [render.yaml](/home/yt/Projects/hyakummeiten-list/render.yaml) を同梱しています。Render で repo を import すると、次の設定でそのまま起動できます。

- build: `pip install -r requirements.txt && python scripts/build_shop_master.py`
- start: `python -m src.api.app`
- health check: `/health`

制約:

- Free Web Service は 15 分 idle で sleep する
- Free Web Service の filesystem は永続化されない
- そのため availability cache のような runtime 書き込みは restart ごとに消える

ただし、この app の検索マスタ SQLite は deploy 時に約 1.3 秒で再生成でき、サイズも約 13 MB なので、無料公開の用途では十分現実的です。

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

既知の欠損・移転ページには抽出時 override を当てます。たとえば `百名店 2019` の `ete` は、旧 URL / 旧住所のままだと `東京都渋谷区` と `0,0` が返るため、抽出時に移転後の URL `https://tabelog.com/tokyo/A1318/A131811/13249143/` と住所 `東京都渋谷区西原3-23-1` に置換します。

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

基準出力として `data/all_years/by_genre/*.csv` も作ります。ここでは地域違いの slug だけをまとめ、異なる料理ジャンルは混ぜません。

Google My Maps 用には、`data/all_years/by_genre/*.csv` をそのまま 4 つの map directory に振り分けた `data/all_years/for_mymap/` も出力します。genre 自体の圧縮はせず、1 map あたり 10 layer 以下に収めます。

出力先:

- `data/all_years/all.csv`
- `data/all_years/by_genre/*.csv`
- `data/all_years/by_region/tohoku_hokkaido.csv`
- `data/all_years/by_region/kanto.csv`
- `data/all_years/by_region/chubu.csv`
- `data/all_years/by_region/kansai.csv`
- `data/all_years/by_region/chugoku_shikoku_kyushu.csv`
- `data/all_years/by_region/unknown.csv`
- `data/all_years/for_mymap/casual_lunch/*.csv`
- `data/all_years/for_mymap/washoku_izakaya/*.csv`
- `data/all_years/for_mymap/dinner_restaurants/*.csv`
- `data/all_years/for_mymap/cafe_sweets/*.csv`

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
- 年、店名、正規化済みジャンルの filter
- `検索`、`営業確認`、`予約可能店舗検索` の 3 段階操作
- `営業 / 休業日 / 情報なし` と `予約可能 / 空席なし / 受付外` の段階別表示
- 複数年掲載店を marker 上の小さな装飾で表示

API 単体で確認する場合:

```bash
curl 'http://127.0.0.1:8000/health'
curl 'http://127.0.0.1:8000/v1/shops/search?year=2025&genre_slug=sushi_tokyo&limit=3'
```

## 予約サイト候補を自動紐付けする

provider adapter 向けの matching pipeline 確認手順です。`--provider` には [src/providers/registry.py](/home/yt/Projects/hyakummeiten-list/src/providers/registry.py) に登録されている provider 名を指定します。

```bash
python3 scripts/match_reservation_links.py --provider <provider> --limit 50
python3 scripts/export_link_review_csv.py --provider <provider>
```

出力先:

- `data/linkage/<provider>/review_candidates.csv`

この段階では次が更新されます。

- `reservation_links`
- `link_review_queue`

## review CSV を扱う

候補 export:

```bash
python3 scripts/export_link_review_csv.py --provider <provider> --allow-empty
```

決定 import の schema 検証:

```bash
python3 scripts/import_link_review_csv.py --provider <provider> --input docs/examples/review_decisions.sample.csv --dry-run
```

CSV の列契約は [docs/reservation-link-review-spec.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-link-review-spec.md) を参照してください。

## 予約状態を CLI で確認する

予約状態付き検索は CLI でも確認できます。

```bash
python3 scripts/check_availability.py --provider tabelog --date 2026-05-25 --party-size 2 --time-window dinner --year 2025 --genre-slug sushi_tokyo --limit 10
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
			"provider": ["tabelog"]
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
python3 scripts/check_availability.py --provider tabelog --date 2026-05-25 --party-size 2 --time-window dinner --year 2025 --genre-slug sushi_tokyo --limit 10
python3 -m src.api.app
```

運用確認項目は [docs/acceptance-checklist.md](/home/yt/Projects/hyakummeiten-list/docs/acceptance-checklist.md) にまとめています。
