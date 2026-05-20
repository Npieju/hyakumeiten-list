# hyakumeiten-list

食べログ 百名店データを整理して、地図で探しやすくするためのリポジトリです。

公開アプリ: https://hyakummeiten-map.onrender.com

このリポジトリには 2 つの用途があります。

- 百名店データを CSV に整形して再利用しやすくすること
- そのデータを SQLite にまとめ、地図 Web アプリから検索できるようにすること

現在の公開アプリでは、Leaflet ベースの地図上で店舗を見ながら、年・ジャンル・店名で絞り込みできます。さらに `営業確認` で営業状況を、`予約可能店舗検索` で食べログの予約可否を日付単位で確認できます。

## リポジトリに含まれるもの

- `data/`: スクレイプ済み CSV、全年度集計、アプリ用 SQLite などの生成物
- `scripts/`: CSV 生成、集計、SQLite 構築、確認用 CLI
- `src/api/`: FastAPI アプリ
- `src/web/`: 地図 UI
- `src/providers/`: 予約サイト連携 adapter
- `docs/`: 仕様書と開発用ドキュメント

## すぐ試す

依存関係を入れて検索マスタを作り、アプリを起動します。

```bash
pip install -r requirements.txt
python3 scripts/build_shop_master.py
python3 -m src.api.app
```

起動後は次を開きます。

- `http://127.0.0.1:8000/`

ヘルスチェック:

```bash
curl 'http://127.0.0.1:8000/health'
```

## データとアプリの概要

- 年別・ジャンル別 CSV を生成できます
- 全年度を横断した集計 CSV を生成できます
- `data/app/hyakummeiten.sqlite3` に検索用マスタを構築できます
- 地図 UI と API は同じ SQLite を参照します
- 予約可否は provider adapter 経由で取得します。現在の実用例は `tabelog` です

CSV の列仕様は [docs/csv-data-spec.md](/home/yt/Projects/hyakummeiten-list/docs/csv-data-spec.md) を参照してください。

## 公開環境

公開アプリは Render Free Web Service 上で動かしています。

- Web アプリ本体は FastAPI で配信しています
- 検索用 SQLite は deploy 時に再生成します
- 無料枠のため、一定時間アクセスがないと sleep します
- ランタイムの一時ファイルは永続化されません

Render 設定は [render.yaml](/home/yt/Projects/hyakummeiten-list/render.yaml) にあります。

## 関連ドキュメント

- [docs/development.md](/home/yt/Projects/hyakummeiten-list/docs/development.md): セットアップ、再生成、確認コマンド
- [docs/csv-data-spec.md](/home/yt/Projects/hyakummeiten-list/docs/csv-data-spec.md): CSV 仕様
- [docs/reservation-search-requirements.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-requirements.md): 要求整理
- [docs/reservation-search-spec.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-spec.md): 設計
- [docs/reservation-search-implementation-plan.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-search-implementation-plan.md): 実装計画
- [docs/reservation-link-review-spec.md](/home/yt/Projects/hyakummeiten-list/docs/reservation-link-review-spec.md): link review CSV 仕様
- [docs/acceptance-checklist.md](/home/yt/Projects/hyakummeiten-list/docs/acceptance-checklist.md): 運用確認項目
