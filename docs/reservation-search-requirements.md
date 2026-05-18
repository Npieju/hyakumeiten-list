# Reservation Search Requirements

## Purpose

百名店データをもとに、店舗を細かい条件で絞り込み、その結果に予約状態を重ねて扱えるようにする。

この文書は「何を実現するか」を定義する。実装方法は [docs/reservation-search-spec.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-spec.md) に分離する。

## Goal

利用者が次を実行できること。

1. 年、ジャンル、地域、都道府県、店名などで百名店を抽出検索できる
2. 抽出した店舗を予約状態ごとに区分けできる
3. 指定日、人数、時間帯で予約可能店舗だけを抽出できる
4. 予約対象外店舗と予約終了店舗を区別して扱える

## Target Users

1. 百名店を条件付きで探したい利用者
2. 予約可能な百名店だけを見たい利用者
3. 店舗と予約サイトの紐付けデータを保守する運用者

## In Scope

1. 百名店データの検索
2. 予約サイトとの店舗紐付け
3. 指定日クエリによる予約状態判定
4. 予約状態に基づく絞り込み
5. 手動確認が必要な紐付け候補の抽出

## Out Of Scope

1. 実際の予約操作の代行
2. 予約サイトへの自動ログイン
3. 全予約サイトの一括同時対応
4. 常時全件の空席監視
5. 運用者向けの本格管理画面

## Functional Requirements

### R1. Static Search

利用者は次の条件で店舗を絞り込めること。

1. 年
2. ジャンル
3. 地域
4. 都道府県
5. 店名
6. 住所
7. 複数年掲載の有無

### R2. Fine-Grained Genre Search

検索は大分類ではなく、既存の `Genre Slug` 単位で扱えること。

例:

1. `sushi_tokyo`
2. `ramen_hokkaido`
3. `french_west`

### R3. Reservation-Aware Search

利用者は次の条件を追加して検索できること。

1. 日付
2. 人数
3. 時間帯
4. 予約サイト
5. 予約状態

### R4. Reservation Status Classification

店舗は少なくとも次の利用者向け区分で扱えること。

1. 予約可能店舗
2. 予約対象外店舗
3. 予約終了店舗
4. 要確認店舗

### R5. Distinguish Unsupported vs Closed

次は明確に分けること。

1. そもそも予約対象外の店舗
2. 予約サイトに載っているが、その日時は受付終了の店舗

### R6. Search Without Availability Lookup

予約状態を条件に含まない検索では、外部の予約サイト照会を必須にしないこと。

### R7. Link Review Workflow

自動判定で確信度が低い店舗紐付けは、手動確認できる形で出力できること。

## Non-Functional Requirements

### N1. Low Operating Cost

構成は低コスト運用を前提とすること。

### N2. Lightweight Server

静的検索の応答は、重い常駐ミドルウェアなしで成立すること。

### N3. Failure Isolation

予約サイト照会に失敗しても、静的検索機能は継続利用できること。

### N4. Incremental Provider Support

最初は provider を 1 つから始められ、あとから段階的に増やせること。

## Core Use Cases

### UC1. Genre Search

利用者は `genre_slug = sushi_tokyo` と `year = 2025` を指定して店舗一覧を取得する。

### UC2. Reservation Search

利用者は `genre_slug = french_tokyo`, `date = 2026-05-25`, `party_size = 2` を指定して予約可能店舗だけを取得する。

### UC3. Unsupported Listing

利用者は `reservation_status = not_supported` を指定して、予約対象外店舗を一覧する。

### UC4. Closed Listing

利用者は `reservation_status = sold_out or booking_closed` を指定して、予約終了店舗を一覧する。

### UC5. Operations Review

運用者は自動紐付けで `review_required` になった候補を確認し、採用または却下する。

## Acceptance Criteria

次を満たせば初期要件を満たしたとみなす。

1. `Genre Slug` と年で静的検索できる
2. `reservation_status` なし検索では外部照会なしで結果を返せる
3. `reservation_status = bookable` 検索で予約可能店舗を返せる
4. `not_supported` と `sold_out` を別区分で返せる
5. 手動確認対象を CSV で出力できる

## Deliverables

1. 検索用データストア
2. 予約サイト紐付けデータ
3. 予約状態検索 API
4. review 用 CSV エクスポート

## Open Product Questions

1. 初期対象 provider はどこか
2. 初期対象ジャンルをどこまで絞るか

MVP では `time_window` を `lunch` / `dinner` の固定値で扱う。任意時刻入力に広げるかは MVP 後の拡張検討とする。