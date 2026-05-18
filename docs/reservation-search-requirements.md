# Reservation Search Requirements

## Purpose

百名店データをもとに、自前の地図 GUI を持つ Web アプリ上で店舗を検索・可視化し、その結果に予約状態を重ねて扱えるようにする。

この文書は「何を実現するか」を定義する。実装方法は [docs/reservation-search-spec.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-spec.md) に分離する。

## Goal

利用者が次を実行できること。

1. Web アプリ上の地図で百名店を可視化できる
2. 年、ジャンル、地域、都道府県、店名などで百名店を抽出検索できる
3. 地図の表示範囲に応じて検索結果を interactive に更新できる
4. 抽出した店舗を予約状態ごとに区分けできる
5. 指定日、人数、時間帯で予約可能店舗だけを抽出できる
6. 予約対象外店舗と予約終了店舗を区別して扱える

## Target Users

1. 百名店を条件付きで探したい利用者
2. 予約可能な百名店だけを見たい利用者
3. 店舗と予約サイトの紐付けデータを保守する運用者

## In Scope

1. 百名店データの検索 API
2. 自前の地図 GUI を持つ Web アプリ
3. 地図表示範囲と検索条件の同期
4. 予約サイトとの店舗紐付け
5. 指定日クエリによる予約状態判定
6. 予約状態に基づく絞り込み
7. 手動確認が必要な紐付け候補の抽出

## Out Of Scope

1. 実際の予約操作の代行
2. 予約サイトへの自動ログイン
3. 全予約サイトの一括同時対応
4. 常時全件の空席監視
5. 運用者向けの本格管理画面
6. ネイティブモバイルアプリ

## Functional Requirements

### R1. Static Search

利用者は Web アプリ上で次の条件により店舗を絞り込めること。

1. 年
2. ジャンル
3. 地域
4. 都道府県
5. 店名
6. 住所
7. 複数年掲載の有無
8. 地図範囲

地図範囲は少なくとも店舗座標に対する矩形範囲指定で扱えること。

### R1a. Interactive Map UI

利用者は Web アプリ上の地図 GUI で次を行えること。

1. 店舗を地図上の marker として閲覧する
2. 地図の pan / zoom に応じて表示対象を更新する
3. marker 選択時に店舗詳細を確認する
4. リスト表示と地図表示で同じ検索条件を共有する
5. 検索条件変更時に地図とリストが同時更新される

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

静的検索と地図表示の応答は、重い常駐ミドルウェアなしで成立すること。

### N2a. Responsive Map Interaction

地図の pan / zoom に伴う再検索は、利用者が interactive と感じられる速度で行えること。

MVP では次を満たすこと。

1. viewport 変更時の再検索は debounce される
2. 既存 marker の再描画が過剰に重くならない
3. 初回表示は全国全件描画を避け、適切な viewport または条件で始める

### N3. Failure Isolation

予約サイト照会に失敗しても、静的検索機能は継続利用できること。

### N4. Incremental Provider Support

最初は provider を 1 つから始められ、あとから段階的に増やせること。

## Core Use Cases

### UC0. Map Browsing

利用者は Web アプリを開き、地図を移動しながら表示範囲内の百名店を確認する。

### UC1. Genre Search

利用者は `genre_slug = sushi_tokyo` と `year = 2025` を指定して、地図と一覧の両方で店舗を取得する。

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

1. Web アプリ上で地図と店舗一覧が表示される
2. `Genre Slug` と年で静的検索できる
3. 地図範囲で静的検索できる
4. 地図の pan / zoom に応じて検索結果が更新される
5. `reservation_status` なし検索では外部照会なしで結果を返せる
6. `reservation_status = bookable` 検索で予約可能店舗を返せる
7. `not_supported` と `sold_out` を別区分で返せる
8. 手動確認対象を CSV で出力できる

## Deliverables

1. 検索用データストア
2. 地図 GUI を持つ Web アプリ
3. 検索 API
4. 予約状態検索 API
5. 予約サイト紐付けデータ
6. review 用 CSV エクスポート

## Open Product Questions

1. 初期対象 provider はどこか
2. 初期対象ジャンルをどこまで絞るか

MVP では `time_window` を `lunch` / `dinner` の固定値で扱う。任意時刻入力に広げるかは MVP 後の拡張検討とする。