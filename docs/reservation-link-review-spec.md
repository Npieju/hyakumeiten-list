# Reservation Link Review CSV Spec

この文書は、手動 review 用 CSV の入出力契約を定義する。

対象 phase は [docs/reservation-search-implementation-plan.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-implementation-plan.md) の Phase 4 である。

## Purpose

低信頼な provider 紐付け候補を、管理画面なしで CSV review に回す。

この phase で固定するのは次の 2 つである。

1. review 候補を DB から CSV に書き出す形式
2. review 決定を CSV から DB に反映する形式

## File Layout

provider ごとの運用ファイルは次に置く。

1. `data/linkage/<provider>/review_candidates.csv`
2. `data/linkage/<provider>/review_decisions.csv`

## Export: review_candidates.csv

`scripts/export_link_review_csv.py` は `link_review_queue.review_status = 'pending'` の行だけを出力する。

列は次で固定する。

1. `review_id`
2. `shop_id`
3. `shop_name`
4. `shop_address`
5. `tabelog_url`
6. `google_maps_url`
7. `provider`
8. `candidate_name`
9. `candidate_url`
10. `candidate_address`
11. `score`
12. `review_status`
13. `created_at`

補足:

1. `review_id` は import 時の主キー参照に使う
2. `score` は自動判定の confidence を保持する
3. queue が空でも `--allow-empty` 指定時は header-only CSV を出力する

## Import: review_decisions.csv

`scripts/import_link_review_csv.py` は review 決定を読み、`reservation_links` と `link_review_queue` に反映する。

列は次で固定する。

1. `review_id`
2. `shop_id`
3. `provider`
4. `decision`
5. `provider_shop_id`
6. `provider_url`
7. `capability_status`
8. `notes`

### decision

`decision` は次のいずれか。

1. `approve`
2. `reject`

### capability_status

`capability_status` は [docs/reservation-search-spec.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-spec.md) の `reservation_links` 定義に合わせ、次のいずれかとする。

1. `supported`
2. `not_supported`
3. `unknown`

### Apply Rules

1. `approve` のときは `provider_shop_id` と `provider_url` を必須とする
2. `approve` は `reservation_links.match_status = 'manually_confirmed'` として保存する
3. `reject` は `reservation_links.match_status = 'rejected'` として保存する
4. import 済み row は `link_review_queue.review_status` を同じ結果に更新する
5. `matched_by` は `manual_review_csv` に固定する

## Commands

候補 export:

```bash
python3 scripts/export_link_review_csv.py --provider example_provider --allow-empty
```

決定 import の schema 検証:

```bash
python3 scripts/import_link_review_csv.py --provider example_provider --input docs/examples/review_decisions.sample.csv --dry-run
```