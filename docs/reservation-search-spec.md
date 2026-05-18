# Reservation Search Design

この文書は予約検索機能の設計書である。
要求仕様は [docs/reservation-search-requirements.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-requirements.md) を参照する。
CSV の入力契約は [docs/csv-data-spec.md](/home/yt/Projects/hyakummeiten-list/docs/csv-data-spec.md) を参照する。

## Design Goal

百名店データを起点に、要求仕様を満たす軽量な検索・予約判定システムを構築する。

設計上の中心方針は、静的な店舗検索と、動的な予約状態判定を分離することにある。

## Design Scope

初期スコープは次の通り。

1. 百名店 CSV から 1 店舗 1 行の検索用マスタを構築する
2. 店舗を予約サイトと紐付ける
3. 日付クエリで予約状態を取得し、結果を分類して返す
4. 細かいジャンル条件と予約状態条件を同時に扱えるようにする

次は初期スコープ外とする。

1. 予約サイトへの自動ログイン
2. 実予約の代行
3. 全サイト一括対応
4. 常時全件の空席監視

## Selected Architecture

ここでは「低コストにしたい」という要求を、実装可能な設計選択として固定する。

採用する構成:

1. 永続ストアは SQLite 1 ファイル
2. 検索 API は単一プロセス
3. 静的検索は SQLite のみで完結
4. 予約状態取得はオンデマンド実行
5. 空席キャッシュも SQLite に保存
6. 手動確認フローは管理画面ではなく CSV 出力で回す

採用しない構成:

1. Postgres 常駐
2. Redis 常駐
3. 外部全文検索エンジン
4. 全件巡回の常時バッチ
5. provider ごとの常駐ワーカー

この設計の狙いは次の通り。

1. サーバ費を SQLite と単一 API プロセスだけに抑える
2. 外部アクセスは予約状態が必要なときだけ発生させる
3. 百名店の静的検索と予約状態取得を分離して、通常検索のコストを一定に保つ

## Runtime Components

実装対象のコンポーネントは 4 つ。

1. オフライン取り込み: 百名店 CSV から検索用 DB を生成する
2. 紐付け更新: 店舗と予約サイト候補を対応付ける
3. クエリ API: 検索と予約状態付与を提供する
4. provider adapter: 予約サイトごとの差分を吸収する

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
4. provider adapter や API 実装が増えた段階で `app/` または `src/` を切る

### Query API

API は stateless に近い単一プロセスを想定する。

役割:

1. 静的条件で候補店舗を絞る
2. 予約状態 filter がある場合だけ availability を評価する
3. キャッシュヒット時は外部アクセスせず返す
4. キャッシュミス時だけ provider adapter を呼ぶ

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

検索キーは表示名の `Genre` ではなく、安定した `Genre Slug` を使う。

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
	prefecture TEXT NOT NULL,
	region TEXT NOT NULL,
	created_at TEXT NOT NULL,
	updated_at TEXT NOT NULL
);

CREATE INDEX idx_shops_region ON shops(region);
CREATE INDEX idx_shops_prefecture ON shops(prefecture);
CREATE INDEX idx_shops_normalized_name ON shops(normalized_name);
```

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
3. `Year` を分解して `shop_years` を作る
4. 各年の `Genre Slug` と `Genre` をそのまま `shop_genres` に積む
5. `prefecture` と `region` を住所から決定する

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
2. provider を呼ばない

Query params:

1. `year`
2. `genre_slug`
3. `region`
4. `prefecture`
5. `name_query`
6. `address_query`
7. `limit`
8. `offset`

返却:

1. `total`
2. `items[]`

`items[]` の shape:

```json
{
	"shop_id": "...",
	"name": "...",
	"address": "...",
	"region": "kanto",
	"prefecture": "東京都",
	"tabelog_url": "...",
	"google_maps_url": "...",
	"years": [2023, 2024, 2025],
	"genres": [
		{"year": 2025, "genre_slug": "sushi_tokyo", "genre_name": "寿司 TOKYO"}
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

## Recommended Lightweight Architecture

初期推奨構成は次の通り。

1. データ生成: 既存の CSV 生成スクリプト
2. 検索用変換: `shop_master` と `reservation_links` を SQLite 化
3. API 層: 単一プロセスの軽量 API
4. キャッシュ層: SQLite 内の `availability_cache`
5. フロント: 静的配信または最小限のテンプレート

避けるもの:

1. Postgres の常駐必須化
2. Elasticsearch や Meilisearch の導入
3. Redis 必須のキャッシュ設計
4. 定期全件巡回バッチ

### Recommended Request Flow

1. リクエストを受ける
2. SQLite の `shop_master` を `genre_slug`, `year`, `region`, `prefecture` で絞る
3. `reservation_links` で候補 provider を取る
4. `availability_cache` を見る
5. 有効なキャッシュがあればそのまま返す
6. キャッシュ切れ分だけ provider adapter を呼ぶ
7. 取得結果を SQLite に保存して返す

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
3. `closed`
4. `unknown`

最終的な見せ方は次で決める。

1. `supported + bookable` -> 予約可能店舗
2. `supported + sold_out or closed` -> 予約終了店舗
3. `unsupported` -> 予約対象外店舗
4. `unknown` を含むもの -> 要確認

## MVP Proposal

最初の MVP は対象を絞る。

1. 予約文化が比較的強いジャンルだけ対象にする
2. provider は 1 サイトだけ対応する
3. 入力は `date`, `party_size`, `genre_slug`, `region`
4. 出力は `bookable`, `not_supported`, `booking_closed`, `unknown` を返す

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
2. SQLite を単一ファイルで持つ場合の配置場所をどこにするか
3. `review_required` の確定オペレーションを CSV インポートにするか
4. `time_window` を固定値にするか、任意時刻にするか
5. provider ごとの利用規約とアクセス制約をどう扱うか