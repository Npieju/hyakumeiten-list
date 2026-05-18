# Reservation Search Implementation Plan

この文書は、予約検索機能を実装するための実装計画書である。

要求仕様は [docs/reservation-search-requirements.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-requirements.md)、設計は [docs/reservation-search-spec.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-spec.md)、CSV 入力契約は [docs/csv-data-spec.md](/home/yt/Projects/hyakummeiten-list/docs/csv-data-spec.md) を前提にする。

目的は、実装順・入出力・確認項目を固定し、計画に沿って順番に実装するだけの状態にすることにある。

## Locked Decisions

今回の計画では、次を固定前提として扱う。

1. repo は分割せず、同じ repo のまま進める
2. 検索用 DB は `data/app/hyakummeiten.sqlite3` に置く
3. 検索マスタの正規入力は `data/<year>/by_genre/*.csv` と `data/<year>/genres.csv` に限る
4. `data/all_years/all.csv` は監査・配布用であり、検索マスタの正規入力にしない
5. review フローは管理画面ではなく CSV export/import で回す
6. `time_window` は MVP では `lunch` と `dinner` の固定値にする
7. API 実装は CLI の動作確認が終わってから着手する
8. `booking_closed` を正式な status 名とし、`closed` は使わない

## Current Baseline

ここまでは実装済みとみなす。

1. [scripts/build_shop_master.py](/home/yt/Projects/hyakummeiten-list/scripts/build_shop_master.py): 年別 `by_genre` から SQLite を生成する
2. [scripts/query_shops.py](/home/yt/Projects/hyakummeiten-list/scripts/query_shops.py): 静的検索 CLI を提供する
3. [docs/csv-data-spec.md](/home/yt/Projects/hyakummeiten-list/docs/csv-data-spec.md): CSV 入力契約を固定済み

既知の確認コマンド:

```bash
python3 scripts/build_shop_master.py
python3 scripts/query_shops.py --year 2025 --genre-slug sushi_tokyo --limit 3
```

## Phase Plan

実装は次の順で進める。前の phase の完了条件を満たすまで、次の phase を始めない。

### Phase 0. Baseline Hardening

目的:

1. 既存の SQLite 生成と静的検索を、以後の実装の土台として固定する

Implementation tasks:

1. `build_shop_master.py` に schema version 管理用の metadata table を追加する
2. `query_shops.py` に `--region`, `--prefecture`, `--name-query`, `--address-query`, `--has-multiple-years` の動作確認ケースを追加する
3. `scripts/validate_shop_master.py` を追加し、主要 table 件数と必須 table 存在を検証できるようにする

Files:

1. [scripts/build_shop_master.py](/home/yt/Projects/hyakummeiten-list/scripts/build_shop_master.py)
2. [scripts/query_shops.py](/home/yt/Projects/hyakummeiten-list/scripts/query_shops.py)
3. `scripts/validate_shop_master.py`

Outputs:

1. `data/app/hyakummeiten.sqlite3`
2. 検証用の標準出力ログ

Verification:

```bash
python3 scripts/build_shop_master.py
python3 scripts/validate_shop_master.py
python3 scripts/query_shops.py --year 2025 --genre-slug sushi_tokyo --limit 3
python3 scripts/query_shops.py --region kanto --name-query 鮨 --limit 5
```

Done when:

1. SQLite 生成が再実行可能である
2. 静的検索の主要 filter がすべて成功する
3. DB 検証コマンドが 0 exit code で終わる

### Phase 1. Link Review Data Model

目的:

1. 予約サイトとの紐付け候補を保存し、手動 review に回せる状態を作る

この phase の確認対象は review CSV の入出力契約であり、候補が実データで埋まる経路そのものは Phase 3 で初めて end-to-end に確認する。

Implementation tasks:

1. `data/linkage/` 配下の運用ファイル構成を固定する
2. review input/output CSV の列仕様を文書化する
3. `scripts/export_link_review_csv.py` を追加し、`link_review_queue` を CSV に書き出せるようにする
4. `scripts/import_link_review_csv.py` を追加し、review 結果を `reservation_links` に反映できるようにする
5. `docs/examples/review_decisions.sample.csv` を追加し、import schema の検証 fixture にする

Files:

1. `scripts/export_link_review_csv.py`
2. `scripts/import_link_review_csv.py`
3. `docs/reservation-link-review-spec.md`
4. `docs/examples/review_decisions.sample.csv`

Outputs:

1. `data/linkage/<provider>/review_candidates.csv`
2. `data/linkage/<provider>/review_decisions.csv`

Verification:

```bash
python3 scripts/export_link_review_csv.py --provider example_provider --allow-empty
python3 scripts/import_link_review_csv.py --provider example_provider --input docs/examples/review_decisions.sample.csv --dry-run
```

Done when:

1. review queue が空でも CSV を export できる
2. sample decisions CSV を schema validation 付きで import 検証できる
3. 手動 review に管理画面を前提としなくてよい

### Phase 2. Provider Adapter Interface

目的:

1. 予約 provider 実装の共通 interface を先に固定し、後続の provider 追加を単純化する

Implementation tasks:

1. `src/providers/base.py` を追加する
2. adapter 共通返却 shape を dataclass または TypedDict で固定する
3. provider registry を追加し、文字列名から adapter を引けるようにする
4. `example_provider` の no-op adapter を追加して interface を通す

Files:

1. `src/providers/base.py`
2. `src/providers/registry.py`
3. `src/providers/example_provider.py`

Outputs:

1. import 可能な provider interface
2. テスト用の no-op adapter

Verification:

```bash
python3 -c "from src.providers.registry import get_provider; print(get_provider('example_provider').name)"
```

Done when:

1. provider interface がコード上で固定される
2. provider 名から adapter を取得できる
3. no-op adapter を使って上位ロジックが実行できる

### Phase 3. Candidate Matching Pipeline

目的:

1. 店舗と provider 候補の自動照合処理を作る

Implementation tasks:

1. `scripts/match_reservation_links.py` を追加する
2. `name` と `normalized_address` を主照合キーとして候補検索を組む
3. confidence score の閾値を固定する
4. 高信頼候補を `auto_linked`、低信頼候補を `review_required` に振り分ける
5. `link_review_queue` と `reservation_links` を同時更新する

Files:

1. `scripts/match_reservation_links.py`
2. `src/providers/*`
3. `docs/reservation-link-review-spec.md`

Outputs:

1. `reservation_links` rows
2. `link_review_queue` rows
3. review CSV

Verification:

```bash
python3 scripts/match_reservation_links.py --provider example_provider --limit 50
python3 scripts/export_link_review_csv.py --provider example_provider
```

Done when:

1. 自動紐付け結果が DB に入る
2. review 必須候補が CSV に落ちる
3. 同一 `shop_id, provider` の重複が起きない

### Phase 4. First Real Provider

目的:

1. 1 つの実 provider を接続し、候補検索と空席取得を実動させる

Implementation tasks:

1. 最初の provider を 1 つ選定する
2. その provider 用 adapter を `src/providers/` に実装する
3. `search_candidates(shop)` を実装する
4. `resolve_shop(candidate)` を実装する
5. `fetch_availability(link, date, party_size, time_window)` を実装する
6. `scripts/check_availability.py` を追加し、real provider で live fetch を実行できるようにする
7. provider 固有の利用制約を `docs/provider-notes/<provider>.md` に記録する

Files:

1. `src/providers/<provider>.py`
2. `scripts/check_availability.py`
3. `docs/provider-notes/<provider>.md`

Outputs:

1. 候補検索結果
2. provider 固有の予約 URL
3. availability normalized result
4. live fetch 実行コマンド

Verification:

```bash
python3 scripts/match_reservation_links.py --provider <provider> --limit 20
python3 scripts/check_availability.py --provider <provider> --date 2026-05-25 --party-size 2 --time-window dinner --limit 10
```

Done when:

1. 実 provider で候補検索が通る
2. 実 provider で availability が normalized shape に落ちる
3. provider 固有注意点が文書化される

### Phase 5. Availability Cache Updater

目的:

1. provider 結果を `availability_cache` に保存し、再利用可能にする

Implementation tasks:

1. `scripts/check_availability.py` に cache hit / miss 判定を実装する
2. `expires_at` の TTL を status ごとに決める
3. 1 リクエスト最大 50 店舗の制約を適用する
4. `provider_error` と `unknown` を区別して記録する
5. live fetch 結果を `availability_cache` に保存して再利用する

Files:

1. `scripts/check_availability.py`
2. `src/providers/*`

Outputs:

1. `availability_cache` rows
2. fetch summary log

Verification:

```bash
python3 scripts/check_availability.py --provider <provider> --date 2026-05-25 --party-size 2 --time-window dinner --limit 10
python3 scripts/check_availability.py --provider <provider> --date 2026-05-25 --party-size 2 --time-window dinner --limit 10
```

Done when:

1. 1 回目は live fetch が走る
2. 2 回目は cache hit が確認できる
3. 取得結果が `availability_cache` に保存される

### Phase 6. Reservation Search API

目的:

1. 既存 CLI を薄い API として公開し、予約状態付き検索を返せるようにする

Implementation tasks:

1. `src/api/` を追加する
2. `GET /v1/shops/search` を `query_shops.py` 相当で実装する
3. `POST /v1/shops/availability-search` を `check_availability.py` と連携して実装する
4. `warning` と `cache_hit_ratio` をレスポンスに含める
5. live fetch 50 件上限超過時のレスポンスを固定する

Files:

1. `src/api/app.py`
2. `src/api/search.py`
3. `src/api/availability.py`

Outputs:

1. 静的検索 API
2. 予約状態付き検索 API

Verification:

```bash
python3 -m src.api.app
curl 'http://localhost:8000/v1/shops/search?year=2025&genre_slug=sushi_tokyo&limit=3'
curl -X POST 'http://localhost:8000/v1/shops/availability-search' -H 'content-type: application/json' -d '{"filters":{"year":[2025],"genre_slug":["sushi_tokyo"]},"reservation":{"date":"2026-05-25","party_size":2,"time_window":"dinner","status":["bookable"],"provider":[]},"limit":10,"offset":0}'
```

Done when:

1. 静的検索 API が CLI と同等の結果を返す
2. availability-search API が cache を使って結果を返す
3. 候補過多時に warning が返る

### Phase 7. Acceptance And Operations

目的:

1. 要求仕様に対して動作確認し、運用に必要な最小手順を固める

Implementation tasks:

1. `docs/acceptance-checklist.md` を追加する
2. 主要 use case ごとの実行コマンドを固定する
3. rebuild 手順、review 手順、provider 注意点を README か docs に集約する

Files:

1. `docs/acceptance-checklist.md`
2. `README.md`

Verification:

1. `UC1` から `UC5` までを手動確認する
2. DB 再生成から API 応答までを通しで確認する

Done when:

1. 要求仕様の acceptance criteria をすべて手で再確認できる
2. 運用者が review CSV を使ってリンク保守できる

## Execution Rules

実装時のルールを固定する。

1. 1 phase につき 1 commit 以上を切る
2. phase 完了後に必ず実行コマンドで検証する
3. provider 固有実装を始める前に、共通 interface を先に確定する
4. API 実装前に CLI で同等動作を通す
5. `data/app/` の生成物は git 管理しない

## Immediate Next Actions

次に着手する作業は Phase 0 で固定する。

1. `scripts/validate_shop_master.py` を追加する
2. `build_shop_master.py` に metadata table を追加する
3. `query_shops.py` の主要 filter を検証する

この 3 点が終わったら、次の実装は Phase 1 に進む。