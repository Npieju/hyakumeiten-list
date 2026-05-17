from __future__ import annotations

import argparse
import csv
from pathlib import Path


POPULAR_GENRE_SLUGS = {
    "izakaya_east",
    "izakaya_west",
    "japanese_east",
    "japanese_tokyo",
    "japanese_west",
    "ramen_aichi",
    "ramen_east",
    "ramen_hokkaido",
    "ramen_kanagawa",
    "ramen_osaka",
    "ramen_tokyo",
    "ramen_west",
    "sushi_east",
    "sushi_tokyo",
    "sushi_west",
    "yakiniku_east",
    "yakiniku_tokyo",
    "yakiniku_west",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--input-dir", default="data")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    year_dir = Path(args.input_dir) / str(args.year)
    by_genre_dir = year_dir / "by_genre"
    source_path = year_dir / "all.csv"
    target_path = year_dir / "popular.csv"

    source_paths = sorted(by_genre_dir.glob("*.csv"))
    if not source_paths:
        raise SystemExit(f"No genre CSV files found in {by_genre_dir}")

    all_rows: list[dict[str, str]] = []
    fieldnames: list[str] | None = None
    for genre_path in source_paths:
        with genre_path.open("r", encoding="utf-8", newline="") as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise SystemExit(f"No CSV header found in {genre_path}")
            if fieldnames is None:
                fieldnames = reader.fieldnames
            all_rows.extend(reader)

    if fieldnames is None:
        raise SystemExit(f"No CSV header found in {by_genre_dir}")

    popular_rows = [
        row for row in all_rows if row.get("Genre Slug", "") in POPULAR_GENRE_SLUGS
    ]

    with source_path.open("w", encoding="utf-8", newline="") as all_file:
        writer = csv.DictWriter(all_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    with target_path.open("w", encoding="utf-8", newline="") as target_file:
        writer = csv.DictWriter(target_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(popular_rows)

    print(f"Wrote {len(all_rows)} rows to {source_path}")
    print(f"Wrote {len(popular_rows)} rows to {target_path}")


if __name__ == "__main__":
    main()
