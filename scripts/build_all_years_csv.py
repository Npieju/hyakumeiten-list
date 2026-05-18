from __future__ import annotations

import argparse
import csv
from pathlib import Path

from build_region_csv import PREFECTURE_TO_REGION, REGION_LABELS, extract_prefecture


MULTI_VALUE_SEPARATOR = " | "


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data")
    parser.add_argument("--output-dir", default="data/all_years")
    return parser.parse_args()


def split_multi_value(value: str) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return []
    return [part.strip() for part in cleaned.split(MULTI_VALUE_SEPARATOR) if part.strip()]


def join_multi_value(values: list[str]) -> str:
    return MULTI_VALUE_SEPARATOR.join(values)


def prefer_value(current: str, candidate: str) -> str:
    if not current:
        return candidate
    if len(candidate) > len(current):
        return candidate
    return current


def update_unique_values(existing: str, candidate: str) -> str:
    merged_values = split_multi_value(existing)
    seen_values = set(merged_values)
    for value in split_multi_value(candidate):
        if value in seen_values:
            continue
        seen_values.add(value)
        merged_values.append(value)
    return join_multi_value(merged_values)


def aggregate_description(row: dict[str, str]) -> str:
    years = row.get("Year", "")
    genres = row.get("Genre", "")
    return f"食べログ 百名店: {years} / {genres}".strip()


def coordinates_match(current: str, candidate: str) -> bool:
    if not current or not candidate:
        return True
    return current == candidate


def main() -> None:
    args = parse_args()
    input_root = Path(args.input_dir)
    output_root = Path(args.output_dir)
    by_region_dir = output_root / "by_region"

    source_paths = sorted(
        path
        for path in input_root.glob("[0-9][0-9][0-9][0-9]/all.csv")
        if path.parent.name.isdigit()
    )
    if not source_paths:
        raise SystemExit(f"No yearly all.csv files found in {input_root}")

    aggregated_rows_by_website: dict[str, dict[str, str]] = {}
    region_rows: dict[str, list[dict[str, str]]] = {
        slug: [] for slug in REGION_LABELS
    }
    fieldnames: list[str] | None = None

    for source_path in source_paths:
        with source_path.open("r", encoding="utf-8", newline="") as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise SystemExit(f"No CSV header found in {source_path}")
            if fieldnames is None:
                fieldnames = reader.fieldnames
            elif reader.fieldnames != fieldnames:
                raise SystemExit(
                    f"CSV header mismatch in {source_path}: {reader.fieldnames} != {fieldnames}"
                )

            for row in reader:
                website = row.get("Website", "").strip()
                if not website:
                    raise SystemExit(f"Missing Website in {source_path}: {row}")

                aggregated_row = aggregated_rows_by_website.get(website)
                if aggregated_row is None:
                    aggregated_row = dict(row)
                    aggregated_rows_by_website[website] = aggregated_row
                else:
                    aggregated_row["Name"] = prefer_value(
                        aggregated_row.get("Name", ""),
                        row.get("Name", ""),
                    )
                    aggregated_row["Address"] = prefer_value(
                        aggregated_row.get("Address", ""),
                        row.get("Address", ""),
                    )
                    aggregated_row["Google Maps URL"] = prefer_value(
                        aggregated_row.get("Google Maps URL", ""),
                        row.get("Google Maps URL", ""),
                    )
                    for column in ("Latitude", "Longitude"):
                        current_value = aggregated_row.get(column, "")
                        candidate_value = row.get(column, "")
                        if not coordinates_match(current_value, candidate_value):
                            raise SystemExit(
                                f"Coordinate mismatch for {website} in {source_path}: "
                                f"{column} {current_value!r} != {candidate_value!r}"
                            )
                        aggregated_row[column] = prefer_value(current_value, candidate_value)
                    for column in ("Year", "Genre", "Genre Slug", "Release Date"):
                        aggregated_row[column] = update_unique_values(
                            aggregated_row.get(column, ""),
                            row.get(column, ""),
                        )

                aggregated_row["Description"] = aggregate_description(aggregated_row)

    if fieldnames is None:
        raise SystemExit(f"No CSV header found in {input_root}")

    all_rows = list(aggregated_rows_by_website.values())
    for row in all_rows:
        prefecture = extract_prefecture(row.get("Address", ""))
        region_slug = (
            PREFECTURE_TO_REGION[prefecture]
            if prefecture is not None
            else "unknown"
        )
        region_rows[region_slug].append(row)

    output_root.mkdir(parents=True, exist_ok=True)
    by_region_dir.mkdir(parents=True, exist_ok=True)

    all_path = output_root / "all.csv"
    with all_path.open("w", encoding="utf-8", newline="") as all_file:
        writer = csv.DictWriter(all_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    for region_slug, rows in region_rows.items():
        target_path = by_region_dir / f"{region_slug}.csv"
        if not rows:
            if target_path.exists():
                target_path.unlink()
            print(
                f"Skipped empty region output {target_path}"
                f" ({REGION_LABELS[region_slug]})"
            )
            continue
        with target_path.open("w", encoding="utf-8", newline="") as target_file:
            writer = csv.DictWriter(target_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(
            f"Wrote {len(rows)} rows to {target_path}"
            f" ({REGION_LABELS[region_slug]})"
        )

    print(f"Wrote {len(all_rows)} rows to {all_path}")


if __name__ == "__main__":
    main()