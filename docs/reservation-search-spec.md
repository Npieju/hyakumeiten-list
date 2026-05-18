# Reservation Search Design

この文書は予約検索機能の設計書である。
要求仕様は [docs/reservation-search-requirements.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-requirements.md) を参照する。
CSV の入力契約は [docs/csv-data-spec.md](/home/yt/Projects/hyakummeiten-list/docs/csv-data-spec.md) を参照する。
実装順は [docs/reservation-search-implementation-plan.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-implementation-plan.md) を参照する。

## Design Goal

百名店データを起点に、要求仕様を満たす軽量な検索・予約判定システムを、地図 GUI を持つ Web アプリとして構築する。

設計上の中心方針は、frontend の地図体験、静的な店舗検索、動的な予約状態判定を分離することにある。

## Design Scope

初期スコープは次の通り。

1. 百名店 CSV から 1 店舗 1 行の検索用マスタを構築する
2. 地図 GUI を持つ Web フロントエンドを提供する
3. frontend から呼ぶ検索 API を提供する
4. 店舗を予約サイトと紐付ける
5. 日付クエリで予約状態を取得し、結果を分類して返す
6. 細かいジャンル条件と予約状態条件を同時に扱えるようにする

次は初期スコープ外とする。

1. 予約サイトへの自動ログイン
2. 実予約の代行
3. 全サイト一括対応
4. 常時全件の空席監視

## Selected Architecture

ここでは「低コストにしたい」という要求を、実装可能な設計選択として固定する。

採用する構成:

1. 永続ストアは SQLite 1 ファイル
2. frontend は自前の Web アプリとして同 repo 内に持つ
3. API は FastAPI + Uvicorn の単一プロセス
4. 静的検索は SQLite のみで完結
5. 予約状態取得はオンデマンド実行
6. 空席キャッシュも SQLite に保存
7. 手動確認フローは管理画面ではなく CSV 出力で回す

採用しない構成:

1. Postgres 常駐
2. Redis 常駐
3. 外部全文検索エンジン
4. 全件巡回の常時バッチ
5. provider ごとの常駐ワーカー
6. 先に重い SPA build 基盤を前提にする構成
7. 初期段階から WebGL / vector tile 中心に寄せる構成

この設計の狙いは次の通り。

1. サーバ費を SQLite と単一 API プロセスだけに抑える
2. frontend は静的配信可能な構成に保つ
3. 外部アクセスは予約状態が必要なときだけ発生させる
4. 百名店の静的検索と予約状態取得を分離して、通常検索のコストを一定に保つ

## Technology Selection

Web アプリ化にあたり、初期方針の「低コスト」「同 repo」「単一プロセス」「段階的拡張」を満たす技術を比較した上で、次を採用する。

採用:

1. API: FastAPI + Uvicorn
2. frontend: 素の HTML / CSS / JavaScript（ES modules）
3. map library: Leaflet
4. frontend 配信: API プロセスと同一 origin で静的配信

比較対象と判断:

1. FastAPI vs Flask
FastAPI を採用する。理由は、型付き request / response モデルを早い段階で固定しやすく、検索 API と予約 API の schema をそのまま契約として扱いやすいからである。Flask でも実装は可能だが、今回の計画では API 契約の固定を前倒ししているため、薄いが型を持てる FastAPI の方が方針に合う。

2. Leaflet vs MapLibre GL JS
Leaflet を採用する。今回の MVP で必要なのは marker 表示、popup、bounding box 連動、一覧同期であり、3D 表現や vector style の自由度は優先度が低い。MapLibre GL JS は表現力が高い一方で、初期構成・style 管理・描画負荷の設計論点が増える。低コスト・早期成立の方針では Leaflet の方が適切である。

3. 素の JavaScript vs React / Vue / Svelte
素の JavaScript を採用する。今回の初期 UI は 1 画面の map + filter + list であり、状態管理の複雑さはまだ限定的である。React などを入れると build、lint、依存更新、バンドラ選定が早期に必要になり、同 repo の軽量運用方針と衝突しやすい。複雑化した段階で移行余地を残す方が合理的である。

4. frontend と API の別配信 vs 同一 origin 配信
同一 origin 配信を採用する。MVP の段階では CORS、別デプロイ、環境差分の管理を避け、単一プロセスでローカル開発と本番運用の差を小さく保つ方がよい。

## Runtime Components

実装対象のコンポーネントは 5 つ。

1. オフライン取り込み: 百名店 CSV から検索用 DB を生成する
2. Web フロントエンド: 地図表示と interactive 検索 UI を提供する
3. クエリ API: 検索と予約状態付与を提供する
4. 紐付け更新: 店舗と予約サイト候補を対応付ける
5. provider adapter: 予約サイトごとの差分を吸収する

### Offline Import

入力:

1. `data/<year>/by_genre/*.csv`
2. 必要に応じて [data/all_years/all.csv](/home/yt/Projects/hyakummeiten-list/data/all_years/all.csv) を監査用途で参照する

出力:

1. `data/app/hyakummeiten.sqlite3`

## Repository Strategy

初期実装は別 repo に切り出さず、同じ repo で進める。

理由:

1. 元データ CSV と検索マスタ生成処理の変更を同じ履歴で追える
2. 予約検索の初期段階では scraper と検索側の仕様変更がまだ連動する
3. SQLite 生成までの実装規模では repo 分離の利益より運用コストの方が大きい

整理方針:

1. 元データは従来通り `data/<year>/...` と `data/all_years/...` に置く
2. アプリ向け生成物は `data/app/` に分ける
3. 生成スクリプトは当面 `scripts/` 直下に置く
4. Web frontend と API 実装は `src/` 配下に置く

### Web Frontend

frontend は自前の Web アプリとして実装する。

役割:

1. 地図ライブラリを使って店舗 marker を描画する
2. 地図 viewport と filter state を同期する
3. API から返る店舗一覧を地図とリストの両方に反映する
4. marker 選択時に店舗詳細と外部リンクを表示する
5. 後続 phase で予約状態を色や badge に反映する

初期方針:

1. frontend は静的アセットとして配信可能にする
2. frontend は HTML / CSS / JavaScript の最小構成で始める
3. 地図ライブラリは Leaflet を採用する
4. MVP では bounding box を API に渡して再検索する
5. viewport 更新は debounce し、無駄な再検索を抑える

### Query API

API は stateless に近い単一プロセスを想定する。

実装基盤は FastAPI + Uvicorn を採用する。

役割:

1. 静的条件で候補店舗を絞る
2. 予約状態 filter がある場合だけ availability を評価する
3. キャッシュヒット時は外部アクセスせず返す
4. キャッシュミス時だけ provider adapter を呼ぶ

### Frontend-API Contract

frontend は API を直接呼び、CSV を直接読まない。

理由:

1. 検索条件、viewport、予約条件の組み合わせを frontend だけで安全に処理しきれない
2. SQLite を API 背後に閉じ込める方が将来の provider 追加や schema 変更に強い
3. marker 表示とリスト表示で同一レスポンスを再利用できる

## Requirement Mapping

この設計書では次を実装対象とする。

1. 静的検索
2. 細かいジャンル検索
3. 予約状態付き検索
4. 予約状態の分類
5. 予約対象外と予約終了の区別
6. 予約サイト照会なしの静的検索
7. 手動確認フロー

## Design Constraints

### Search

検索では次の条件を扱う。

1. `year`: 単一年または複数年
2. `genre_slug`: 単一または複数
3. `region`: `tohoku_hokkaido`, `kanto`, `chubu`, `kansai`, `chugoku_shikoku_kyushu`
4. `prefecture`: 都道府県単位
5. `name_query`: 店名部分一致
6. `address_query`: 住所部分一致
7. `has_multiple_years`: 複数年掲載の有無
8. `bounding_box`: `min_lat`, `max_lat`, `min_lng`, `max_lng`

検索キーは表示名の `Genre` ではなく、安定した `Genre Slug` を使う。
地理検索では店舗に保持した `Latitude` / `Longitude` を使い、MVP では半径検索ではなく bounding box を採用する。

### Reservation Filter

予約関連では次の条件を扱う。

1. `date`: 予約対象日
2. `party_size`: 人数
3. `time_window`: 時間帯
4. `provider`: 予約サイト
5. `reservation_status`: 予約状態

### Reservation Status

予約状態は少なくとも次の区分を持つ。

1. `bookable`: 予約可能
2. `not_supported`: 予約対象外
3. `sold_out`: 空席なし、受付終了
4. `booking_closed`: 予約受付時間外、締切済み
5. `temporarily_closed`: 臨時休業など
6. `provider_unlinked`: 店舗は存在するが予約サイト未紐付け
7. `provider_error`: 取得失敗
8. `unknown`: 判定不能

画面や API の利用者向けには、次の 3 区分に丸めて見せられるようにする。

1. 予約可能店舗: `bookable`
2. 予約対象外店舗: `not_supported`, `provider_unlinked`
3. 予約終了店舗: `sold_out`, `booking_closed`, `temporarily_closed`

`provider_error` と `unknown` は「要確認」として別表示できるようにする。

## Storage Design

実装は CSV を直接検索しない。検索用の正規化 SQLite を作る。

DB path:

1. `data/app/hyakummeiten.sqlite3`

### Table: shops

1 店舗 1 行の基本情報。

```sql
CREATE TABLE shops (
	shop_id TEXT PRIMARY KEY,
	tabelog_url TEXT NOT NULL UNIQUE,
	name TEXT NOT NULL,
	normalized_name TEXT NOT NULL,
	address TEXT NOT NULL,
	normalized_address TEXT NOT NULL,
	google_maps_url TEXT NOT NULL,
	latitude REAL NOT NULL,
	longitude REAL NOT NULL,
	prefecture TEXT NOT NULL,
	region TEXT NOT NULL,
	created_at TEXT NOT NULL,
	updated_at TEXT NOT NULL
);

CREATE INDEX idx_shops_region ON shops(region);
CREATE INDEX idx_shops_prefecture ON shops(prefecture);
CREATE INDEX idx_shops_normalized_name ON shops(normalized_name);
CREATE INDEX idx_shops_lat_lng ON shops(latitude, longitude);
```

`latitude` と `longitude` は WGS84 の 10 進度数で保持する。

### Table: shop_years

店舗と掲載年の対応。

```sql
CREATE TABLE shop_years (
	shop_id TEXT NOT NULL,
	year INTEGER NOT NULL,
	release_date TEXT NOT NULL,
	PRIMARY KEY (shop_id, year),
	FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
);

CREATE INDEX idx_shop_years_year ON shop_years(year);
```

### Table: shop_genres

店舗とジャンルの対応。年ごとのジャンル変化も保持する。

```sql
CREATE TABLE shop_genres (
	shop_id TEXT NOT NULL,
	year INTEGER NOT NULL,
	genre_slug TEXT NOT NULL,
	genre_name TEXT NOT NULL,
	PRIMARY KEY (shop_id, year, genre_slug),
	FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
);

CREATE INDEX idx_shop_genres_slug_year ON shop_genres(genre_slug, year);
CREATE INDEX idx_shop_genres_year ON shop_genres(year);
```

### Table: reservation_links

店舗と予約 provider の対応。

```sql
CREATE TABLE reservation_links (
	link_id INTEGER PRIMARY KEY AUTOINCREMENT,
	shop_id TEXT NOT NULL,
	provider TEXT NOT NULL,
	provider_shop_id TEXT,
	provider_url TEXT,
	capability_status TEXT NOT NULL,
	match_status TEXT NOT NULL,
	match_confidence REAL,
	matched_by TEXT NOT NULL,
	last_verified_at TEXT,
	notes TEXT NOT NULL DEFAULT '',
	FOREIGN KEY (shop_id) REFERENCES shops(shop_id),
	UNIQUE (shop_id, provider),
	UNIQUE (provider, provider_shop_id)
);

CREATE INDEX idx_reservation_links_provider ON reservation_links(provider);
CREATE INDEX idx_reservation_links_match_status ON reservation_links(match_status);
```

`capability_status` は次のいずれか。

1. `supported`
2. `not_supported`
3. `unknown`

`match_status` は次のいずれか。

1. `auto_linked`
2. `review_required`
3. `manually_confirmed`
4. `rejected`

### Table: availability_cache

日付クエリに依存する動的結果。

```sql
CREATE TABLE availability_cache (
	shop_id TEXT NOT NULL,
	provider TEXT NOT NULL,
	query_date TEXT NOT NULL,
	party_size INTEGER NOT NULL,
	time_window TEXT NOT NULL,
	status TEXT NOT NULL,
	status_reason TEXT NOT NULL,
	reservation_url TEXT,
	available_slots_json TEXT NOT NULL DEFAULT '[]',
	checked_at TEXT NOT NULL,
	expires_at TEXT NOT NULL,
	raw_payload_hash TEXT,
	PRIMARY KEY (shop_id, provider, query_date, party_size, time_window),
	FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
);

CREATE INDEX idx_availability_cache_lookup
ON availability_cache(query_date, party_size, time_window, provider, status, expires_at);
```

### Table: link_review_queue

手動確認が必要な候補を保持する。初期 UI は作らず、CSV エクスポートで使う。

```sql
CREATE TABLE link_review_queue (
	review_id INTEGER PRIMARY KEY AUTOINCREMENT,
	shop_id TEXT NOT NULL,
	provider TEXT NOT NULL,
	candidate_name TEXT NOT NULL,
	candidate_url TEXT NOT NULL,
	candidate_address TEXT NOT NULL,
	score REAL NOT NULL,
	review_status TEXT NOT NULL DEFAULT 'pending',
	created_at TEXT NOT NULL,
	reviewed_at TEXT,
	FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
);
```

## Processing Model

### 1. Build Search Master

1. `data/<year>/by_genre/*.csv` を年ごとに走査する
2. `Website` を `shop_id` の基準にして `shops` を作る
3. `Latitude` / `Longitude` を `shops` に積む
4. `Year` を分解して `shop_years` を作る
5. 各年の `Genre Slug` と `Genre` をそのまま `shop_genres` に積む
6. `prefecture` と `region` を住所から決定する

出力スクリプト名は `scripts/build_shop_master.py` とする。

### 2. Match Reservation Providers

1. 予約サイトごとに候補検索を行う
2. `name` と `normalized_address` を主な照合キーにする
3. 高信頼候補のみ `auto_linked` にする
4. 低信頼候補は `review_required` に落とす

出力:

1. `reservation_links`
2. `link_review_queue`
3. review 用 CSV

### 3. Resolve Availability

1. ユーザーの `date`, `party_size`, `time_window` を受け取る
2. 検索条件に合う `shop_master` を抽出する
3. 紐付け済み `reservation_links` を provider ごとに評価する
4. 必要なものだけ provider adapter で空席確認する
5. 結果を `availability_cache` に保存する

ここでは「全件先読み」をしない。問い合わせ時に必要な店舗だけ確認する。
これにより、provider API 呼び出し数と常時実行コストを抑える。

さらに次の上限を設ける。

1. 1 リクエストあたり live fetch 対象は最大 50 店舗
2. 候補件数が 50 を超える場合は、まずキャッシュ済み結果だけ返す
3. 50 を超える live fetch を必要とする条件では、追加絞り込みを促す

### 4. Return Result Set

返却単位は店舗とし、provider ごとの詳細をぶら下げる。

Return shape:

1. 店舗基本情報
2. 百名店掲載情報
3. 予約状態サマリ
4. provider ごとの予約 URL
5. 空席時間帯

初期段階では API 本体の前に、同等の検索条件を受ける CLI として `scripts/query_shops.py` を用意する。

## Provider Adapter Contract

予約サイトごとに adapter を分ける。各 adapter は最低限次の 3 メソッドを持つ。

1. `search_candidates(shop)`
2. `resolve_shop(candidate)`
3. `fetch_availability(link, date, party_size, time_window)`

各 adapter の返却値は provider ごとの差を吸収した共通 shape に寄せる。

adapter は遅延ロード可能な構成にする。未使用 provider のモジュールや設定が起動時コストにならないようにする。

共通返却 shape:

```json
{
	"provider": "example_provider",
	"status": "bookable",
	"status_reason": "slot_found",
	"reservation_url": "https://example.com/reserve/123",
	"available_slots": ["18:00", "19:30"],
	"checked_at": "2026-05-19T12:00:00Z",
	"expires_at": "2026-05-19T12:15:00Z",
	"raw_payload_hash": "sha256:..."
}
```

## API Specification

初期実装では 2 エンドポイントで足りる。

### `GET /v1/shops/search`

用途:

1. 静的検索のみ
2. frontend の地図表示と一覧表示の共通データ取得
3. provider を呼ばない

Query params:

1. `year`
2. `genre_slug`
3. `region`
4. `prefecture`
5. `name_query`
6. `address_query`
7. `min_lat`
8. `max_lat`
9. `min_lng`
10. `max_lng`
11. `limit`
12. `offset`

返却:

1. `total`
2. `returned`
3. `truncated`
4. `warning`
5. `items[]`

`limit` は map と list の共通結果集合に対して適用する。
MVP では map と list で別クエリには分けず、同じ `items[]` を描画に使う。
`total > returned` の場合は `truncated = true` とし、frontend は「現在条件では一部のみ表示中」であることを明示する。

`items[]` の shape:

```json
{
	"total": 128,
	"returned": 100,
	"truncated": true,
	"warning": "too_many_results_in_viewport",
	"items": [
		{
	"shop_id": "...",
	"name": "...",
	"address": "...",
	"latitude": 35.6764,
	"longitude": 139.6993,
	"region": "kanto",
	"prefecture": "東京都",
	"tabelog_url": "...",
	"google_maps_url": "...",
	"years": [2023, 2024, 2025],
	"genres": [
		{"year": 2025, "genre_slug": "sushi_tokyo", "genre_name": "寿司 TOKYO"}
	]
		}
	]
}
```

### `POST /v1/shops/availability-search`

用途:

1. 静的検索 + 予約状態 filter
2. 必要時のみ provider を呼ぶ

Request body:

```json
{
	"filters": {
		"year": [2025],
		"genre_slug": ["sushi_tokyo"],
		"region": ["kanto"],
		"prefecture": [],
		"bounding_box": {
			"min_lat": 35.60,
			"max_lat": 35.75,
			"min_lng": 139.60,
			"max_lng": 139.85
		},
		"name_query": null,
		"address_query": null
	},
	"reservation": {
		"date": "2026-05-25",
		"party_size": 2,
		"time_window": "dinner",
		"status": ["bookable"],
		"provider": []
	},
	"limit": 20,
	"offset": 0
}
```

返却:

```json
{
	"total": 12,
	"cache_hit_ratio": 0.75,
	"live_checks": 8,
	"items": [
		{
			"shop_id": "...",
			"name": "...",
			"address": "...",
			"reservation_summary": {
				"status": "bookable",
				"status_reason": "slot_found"
			},
			"providers": [
				{
					"provider": "example_provider",
					"status": "bookable",
					"reservation_url": "...",
					"available_slots": ["18:00", "19:30"]
				}
			]
		}
	]
}
```

### Query Execution Rules

1. `GET /v1/shops/search` は provider を呼ばない
2. `POST /v1/shops/availability-search` は静的検索を先に実行する
3. 候補件数が 50 を超える場合は live fetch を打ち切る
4. 打ち切り時はキャッシュヒット分のみ返し、レスポンスに warning を含める

## Frontend Interaction Design

### Primary Screens

初期 UI は 1 画面で完結させる。

1. 上部または左側に検索 filter
2. 主領域に地図
3. 補助領域に結果一覧
4. marker 選択時の詳細 panel

### Map Interaction Rules

1. 初回表示では直近年を既定選択とし、代表 viewport は東京圏を初期表示に使う
2. pan / zoom 完了後に現在 viewport を bounding box に変換して再検索する
3. filter 変更時は viewport を維持したまま再検索する
4. 検索結果が多い場合、marker clustering または件数上限制御を行う
5. marker 選択時は対応する一覧項目も強調する

初回表示で全国全件を即時描画しない。
最初の検索は既定 viewport に限定し、利用者操作後に viewport を更新する。

### Result Rendering Rules

1. 地図 marker と一覧 item は同じ店舗集合を表す
2. 一覧は地図外の全件ではなく、現在検索条件に一致した結果を表示する
3. reservation status がある場合、marker と一覧の両方に同じ status 表現を適用する
4. API 未応答時、frontend は loading / error 状態を明示する

## Recommended Lightweight Architecture

初期推奨構成は次の通り。

1. データ生成: 既存の CSV 生成スクリプト
2. 検索用変換: `shop_master` と `reservation_links` を SQLite 化
3. API 層: FastAPI + Uvicorn の単一プロセス軽量 API
4. キャッシュ層: SQLite 内の `availability_cache`
5. フロント: Leaflet を使う静的 Web アプリ

避けるもの:

1. Postgres の常駐必須化
2. Elasticsearch や Meilisearch の導入
3. Redis 必須のキャッシュ設計
4. 定期全件巡回バッチ

### Recommended Request Flow

1. リクエストを受ける
2. frontend が filter と viewport を API に送る
3. SQLite の `shop_master` を `genre_slug`, `year`, `region`, `prefecture` で絞る
4. 地図 UI の表示範囲がある場合は `latitude`, `longitude` で bounding box を先に絞る
5. `reservation_links` で候補 provider を取る
6. `availability_cache` を見る
7. 有効なキャッシュがあればそのまま返す
8. キャッシュ切れ分だけ provider adapter を呼ぶ
9. 取得結果を SQLite に保存して返す
10. frontend が marker と一覧を再描画する

この流れなら、静的検索はほぼローカル参照だけで終わり、外部アクセスは本当に必要な店舗に限定される。

## Cache Policy

低コスト化のため、空席状態は問い合わせごとに取得しつつ、短時間キャッシュする。

初期方針:

1. 同一 `shop_id + provider + date + party_size + time_window` の結果を再利用する
2. 当日検索は短めの TTL にする
3. 未来日の検索は少し長めの TTL にする
4. `not_supported` と `provider_unlinked` は長めにキャッシュする

初期 TTL 案:

1. `bookable`: 15 分
2. `sold_out`: 15 分
3. `booking_closed`: 60 分
4. `not_supported`: 7 日
5. `provider_unlinked`: 7 日
6. `provider_error`: 5 分
7. `unknown`: 10 分

キャッシュ更新条件:

1. `expires_at <= now` の場合のみ live fetch 候補にする
2. `not_supported` と `provider_unlinked` は live fetch しない
3. `provider_error` は短時間で再試行可能にする

## Search Serving Strategy

軽量化のため、検索と予約確認の責務を分ける。

1. 静的検索結果は SQLite だけで返せるようにする
2. 予約確認は result set に対して後段で適用する
3. `reservation_status` filter が無い場合、provider には一切アクセスしない
4. `reservation_status = bookable` のような条件がある場合だけ availability を評価する

この設計により、単なるジャンル検索や地域検索では外部通信が発生しない。

さらに、最初の検索ページで全候補を live 評価しない。
ページング単位で必要分だけ評価する。

## Deployment Recommendation

最初の候補は次のどちらかに寄せる。

1. 単一の小さい VM 上で、SQLite + 単一 API プロセス
2. serverless 実行環境上で、SQLite 相当の単一ファイル DB または軽量永続化層

初期の推奨は 1 である。理由は次の通り。

1. 実装が単純
2. provider ごとの通信制御を入れやすい
3. ローカル開発との差が小さい
4. 最小構成で十分安い

初期デプロイ単位:

1. API プロセス 1
2. SQLite ファイル 1
3. 日次または手動実行のオフライン更新ジョブ

## Cost-Oriented MVP Decision

MVP では次を固定する。

1. provider は 1 つだけ
2. 対象ジャンルは予約文化があるものに限定
3. 検索対象マスタは SQLite 1 ファイル
4. 空席確認はオンデマンドのみ
5. review 用の紐付け確認は CSV 出力で回し、管理画面は作らない

これにより、実装コストと運用コストの両方を下げる。

## Query Examples

### Example 1

条件:

1. `genre_slug = sushi_tokyo`
2. `year = 2025`
3. `region = kanto`
4. `date = 2026-05-25`
5. `party_size = 2`
6. `reservation_status = bookable`

結果:

1. 寿司 TOKYO 2025 の関東店舗のうち、指定条件で予約可能な店舗のみ返す

### Example 2

条件:

1. `genre_slug in [french_tokyo, italian_tokyo]`
2. `year in [2023, 2024, 2025]`
3. `reservation_status in [not_supported, provider_unlinked]`

結果:

1. 対象ジャンルに属するが、そもそも予約対象外または未紐付けの店舗一覧を返す

## Classification Rules

内部判定は `reservation_capability` と `reservation_availability` に分けて考える。

### reservation_capability

1. `supported`
2. `unsupported`
3. `unknown`

### reservation_availability

1. `bookable`
2. `sold_out`
3. `booking_closed`
4. `temporarily_closed`
5. `unknown`

最終的な見せ方は次で決める。

1. `supported + bookable` -> 予約可能店舗
2. `supported + sold_out` -> 予約終了店舗
3. `supported + booking_closed` -> 予約終了店舗
4. `supported + temporarily_closed` -> 予約終了店舗
5. `unsupported` -> 予約対象外店舗
6. `unknown` を含むもの -> 要確認

## MVP Proposal

最初の MVP は対象を絞る。

1. 予約文化が比較的強いジャンルだけ対象にする
2. provider は 1 サイトだけ対応する
3. 入力は `date`, `party_size`, `genre_slug`, `region`
4. 出力は少なくとも `bookable`, `sold_out`, `not_supported`, `booking_closed`, `unknown` を返す

優先ジャンル候補:

1. `sushi_*`
2. `yakiniku_*`
3. `french_*`
4. `italian_*`
5. `japanese_*`

ラーメン、カレー、パン、和菓子は初期対象から外す余地が大きい。

## Proposed Repository Layout

1. `scripts/build_shop_master.py`
2. `scripts/match_reservation_links.py`
3. `scripts/export_link_review_csv.py`
4. `scripts/check_availability.py`
5. `scripts/query_shops.py`
6. `src/providers/`
7. `data/app/`
8. `data/linkage/`

## First Implementation Tasks

実装開始時の順序を固定する。

1. `build_shop_master.py` で SQLite を生成する
2. `query_shops.py` で `GET /v1/shops/search` 相当の静的検索を実装する
3. provider 1 つ分の adapter interface を作る
4. `match_reservation_links.py` で `reservation_links` と review CSV を作る
5. `check_availability.py` で `availability_cache` を更新する
6. `POST /v1/shops/availability-search` を実装する

## Open Questions

1. 最初に対応する provider はどこか
2. provider ごとの利用規約とアクセス制約をどう扱うか