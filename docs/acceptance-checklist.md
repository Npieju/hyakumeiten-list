# Acceptance Checklist

この文書は、現時点の MVP 実装に対する手動確認手順をまとめる。

対象は [docs/reservation-search-requirements.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-requirements.md) の `UC0` から `UC5` と acceptance criteria である。

## Prerequisites

```bash
python3 scripts/build_shop_master.py
python3 scripts/validate_shop_master.py
python3 scripts/match_reservation_links.py --provider example_provider --limit 50
python3 -m src.api.app
```

## UC0. Map Browsing

目的:

1. 地図と一覧が同時に表示されること
2. pan / zoom 後に検索結果が更新されること

確認:

1. ブラウザで `http://127.0.0.1:8000/` を開く
2. 地図上に marker が出ることを確認する
3. 地図を移動して一覧件数が変わることを確認する

## UC1. Genre Search

確認コマンド:

```bash
python3 scripts/query_shops.py --year 2025 --genre-slug sushi_tokyo --limit 5
curl 'http://127.0.0.1:8000/v1/shops/search?year=2025&genre_slug=sushi_tokyo&limit=5'
```

確認ポイント:

1. CLI と API がどちらも `items` を返す
2. Web UI でも `Year=2025`, `Genre Slug=sushi_tokyo` で結果が更新される

## UC2. Reservation Search

確認コマンド:

```bash
python3 scripts/check_availability.py --provider example_provider --date 2026-05-25 --party-size 2 --time-window dinner --year 2025 --genre-slug french_tokyo --status bookable --limit 10
curl -X POST 'http://127.0.0.1:8000/v1/shops/availability-search' -H 'content-type: application/json' -d '{"filters":{"year":[2025],"genre_slug":["french_tokyo"]},"reservation":{"date":"2026-05-25","party_size":2,"time_window":"dinner","status":["bookable"],"provider":["example_provider"]},"limit":10,"offset":0}'
```

確認ポイント:

1. `cache_hit_ratio` と `live_checks` が返る
2. Web UI の予約状態トグルを有効化すると status chip が出る

## UC3. Unsupported Listing

確認コマンド:

```bash
python3 scripts/check_availability.py --provider example_provider --date 2026-05-25 --party-size 2 --time-window dinner --status not_supported --limit 10
```

確認ポイント:

1. `not_supported` が `sold_out` と区別される

## UC4. Closed Listing

確認コマンド:

```bash
python3 scripts/check_availability.py --provider example_provider --date 2026-05-25 --party-size 2 --time-window dinner --status sold_out --status booking_closed --limit 10
```

確認ポイント:

1. `sold_out` と `booking_closed` が返る
2. Web UI の chip / marker 色が `bookable` と区別される

## UC5. Operations Review

確認コマンド:

```bash
python3 scripts/export_link_review_csv.py --provider example_provider
python3 scripts/import_link_review_csv.py --provider example_provider --input docs/examples/review_decisions.sample.csv --dry-run
```

確認ポイント:

1. `review_candidates.csv` が出力できる
2. sample CSV の dry-run import が通る

## Broad Query Warning

確認コマンド:

```bash
python3 scripts/check_availability.py --provider example_provider --date 2026-05-25 --party-size 2 --time-window dinner --limit 10
```

確認ポイント:

1. 候補が広い場合は `warning = live_check_limit_exceeded` が返る
2. Web UI では未評価結果が `未評価` として表示される