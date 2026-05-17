# hyakummeiten-list

食べログ 百名店を年別・ジャンル別の CSV に整形して、Google My Maps に取り込みやすくするためのスクレイパーです。

現状は `2025` 年を対象にしています。

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2025年のジャンル一覧だけ作る

```bash
python3 scripts/scrape_hyakumeiten.py --year 2025 --genres-only
```

出力先:

- `data/2025/genres.csv`

## 2025年の全ジャンルCSVを作る

```bash
python3 scripts/scrape_hyakumeiten.py --year 2025
```

出力先:

- `data/2025/genres.csv`
- `data/2025/all.csv`
- `data/2025/by_genre/*.csv`

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

## GitHub リポジトリ化

このディレクトリはローカルで `git init` 済みです。GitHub 側のリモート作成は手元の認証が必要です。

```bash
git branch -M main
git add .
git commit -m "Initial scraper for Tabelog Hyakumeiten 2025"
git remote add origin <your-repo-url>
git push -u origin main
```
