# Hyakumeiten CSV Data Specification

この文書は、百名店 scraper が出力する CSV 群の仕様を定義する。

目的は 2 つある。

1. CSV 出力の列仕様と再生成ルールを固定する
2. 予約検索フェーズがどの CSV を入力 source of truth として使うかを明確にする

## Scope

対象は次の CSV 群である。

1. `data/<year>/genres.csv`
2. `data/<year>/by_genre/*.csv`
3. `data/<year>/all.csv`
4. `data/<year>/unavailable.csv`
5. `data/<year>/selected.csv`
6. `data/<year>/selected_unavailable.csv`
7. `data/<year>/by_region/*.csv`
8. `data/all_years/all.csv`
9. `data/all_years/by_region/*.csv`

## Directory Layout

### Yearly raw and derived outputs

1. `data/<year>/genres.csv`: その年に存在する genre 一覧
2. `data/<year>/by_genre/<genre_slug>.csv`: その年・その genre の店舗一覧
3. `data/<year>/all.csv`: その年の全 genre を単純結合した一覧
4. `data/<year>/unavailable.csv`: 取得不能ページを記録した一覧
5. `data/<year>/selected.csv`: `--genre` 指定時の一時的な結合結果
6. `data/<year>/selected_unavailable.csv`: `--genre` 指定時の unavailable 一覧
7. `data/<year>/by_region/*.csv`: 地域別に再分割した一覧

### Cross-year derived outputs

1. `data/all_years/all.csv`: 全年度を `Website` 単位で 1 行にまとめた一覧
2. `data/all_years/by_region/*.csv`: `data/all_years/all.csv` の地域別一覧

## Source Of Truth Rules

予約検索フェーズや検索マスタ生成では、次の優先順位で CSV を使う。

1. `data/<year>/by_genre/*.csv`: 年とジャンルの対応を保持する正規入力
2. `data/<year>/genres.csv`: 年ごとの genre 定義の正規入力
3. `data/<year>/all.csv`: 年単位の配布用派生物
4. `data/<year>/by_region/*.csv`: 地域配布用派生物
5. `data/all_years/all.csv`: 監査・配布用派生物

次は source of truth として使わない。

1. `data/<year>/selected.csv`
2. `data/<year>/selected_unavailable.csv`
3. `data/all_years/all.csv` を `shop_genres` 構築の唯一入力にすること

理由:

1. `selected.csv` 系は部分実行の結果であり、年全体を代表しない
2. `data/all_years/all.csv` は複数年・複数 genre を ` | ` で連結しており、年ごとの genre 対応を失う

## File Specifications

### `data/<year>/genres.csv`

1 行は 1 年・1 genre を表す。

Columns:

1. `Year`: 掲載年
2. `Genre`: 表示用 genre 名
3. `Genre Slug`: 安定した識別子
4. `Release Date`: 百名店公開日文字列
5. `URL`: 百名店 genre ページ URL

Invariants:

1. `Genre Slug` は同一年内で一意
2. `Genre Slug` は検索キーとして使う

### `data/<year>/by_genre/<genre_slug>.csv`

1 行は 1 店舗・1 年・1 genre を表す。

Columns:

1. `Name`
2. `Address`
3. `Description`
4. `Website`
5. `Google Maps URL`
6. `Year`
7. `Genre`
8. `Genre Slug`
9. `Release Date`

Invariants:

1. `Genre Slug` はファイル名の slug と一致する
2. `Year` は親ディレクトリの年と一致する
3. `Website` は店舗の canonical key として扱う
4. 同一店舗が複数年に掲載される場合でも、年ごとに別行になる
5. 同一店舗が同一年に複数 genre に載る場合は、genre ごとに別行になる

Notes:

1. 404 など取得不能な店舗でも、一覧に存在する限り行自体は保持する
2. その場合の `Address` は override または空文字になりうる

### `data/<year>/all.csv`

`data/<year>/by_genre/*.csv` の単純結合結果。

Columns:

1. `data/<year>/by_genre/*.csv` と同一

Usage:

1. 年単位の配布用
2. region 再分割の入力

Not for:

1. 年ごとの genre 対応を失わない前提での再正規化

### `data/<year>/unavailable.csv`

一覧には出ているが店舗詳細取得に失敗した店舗の監査ログ。

Columns:

1. `Website`
2. `Year`
3. `Genre`
4. `Genre Slug`
5. `Release Date`
6. `Reason`
7. `Status Code`
8. `Listed Name`
9. `Listed Area`

Invariants:

1. ここに載った店舗は、対応する `by_genre` / `all.csv` に fallback row が存在しうる
2. `Reason` は取得失敗理由であり、店舗の営業状態ではない

### `data/<year>/selected.csv`

`--genre` 指定時だけ作られる部分集合の結合結果。

Rules:

1. 永続的な配布物ではなく、作業用出力とみなす
2. `data/<year>/all.csv` を置き換えるものではない

### `data/<year>/by_region/*.csv`

`data/<year>/all.csv` を住所先頭の都道府県から地域分類した派生物。

Region slugs:

1. `tohoku_hokkaido`
2. `kanto`
3. `chubu`
4. `kansai`
5. `chugoku_shikoku_kyushu`
6. `unknown`

Rules:

1. 地域分類は `Address` の都道府県接頭辞から決める
2. 判定不能な行は `unknown.csv` に入る

### `data/all_years/all.csv`

`Website` 単位で全年度を 1 行にまとめた配布用 CSV。

Columns:

1. `Name`
2. `Address`
3. `Description`
4. `Website`
5. `Google Maps URL`
6. `Year`
7. `Genre`
8. `Genre Slug`
9. `Release Date`

Aggregation rules:

1. 重複判定キーは `Website`
2. `Year`, `Genre`, `Genre Slug`, `Release Date` は ` | ` 区切りで連結する
3. `Name`, `Address`, `Google Maps URL` は長い方を優先して代表値にする

Warning:

1. `Year` と `Genre` の位置対応は保証しない
2. このファイル単独から年ごとの `shop_genres` を復元してはならない

## Regeneration Rules

### Rebuild a year

```bash
python3 scripts/scrape_hyakumeiten.py --year 2025 --throttle-seconds 0 --workers 4
python3 scripts/build_region_csv.py --year 2025
```

### Rebuild all years aggregate

```bash
python3 scripts/build_all_years_csv.py
```

### Rebuild search master for reservation search

```bash
python3 scripts/build_shop_master.py
```

This command must read `data/<year>/by_genre/*.csv` as input.

## Contract For Reservation Search Phase

予約検索フェーズでは次を前提契約とする。

1. `Website` は shop identity の基準キーである
2. `Genre Slug` は検索用の安定キーである
3. `data/<year>/by_genre/*.csv` は `shop_years` と `shop_genres` の正規入力である
4. `data/all_years/all.csv` は監査・配布向けであり、正規入力ではない

この契約を変える場合は、scraper、集計スクリプト、検索マスタ生成、要求仕様、設計書を同時に更新する。