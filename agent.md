# Agent Notes

## Current task

- Initialize this directory as a local Git repository.
- Build a scraper for Tabelog Hyakumeiten.
- Generate a 2025 genre list.
- Generate Google My Maps importable CSV files by year and by genre.

## Working rules

- Keep outputs organized under `data/<year>/`.
- Keep `genres.csv` as the full list for that year, even when scraping only selected genres.
- For heavier scrapers, always include visible progress output so long-running work does not look stalled.
- Prefer progress at the unit the user can reason about, such as genre count and shop count.
- Commit and push CSV progress in small checkpoints when new genre files have been generated.
- Keep CSV columns stable for My Maps imports unless there is a clear migration reason.

## Current commands

```bash
python3 scripts/scrape_hyakumeiten.py --year 2025 --genres-only
python3 scripts/scrape_hyakumeiten.py --year 2025 --genre cafe_east --throttle-seconds 0
```
