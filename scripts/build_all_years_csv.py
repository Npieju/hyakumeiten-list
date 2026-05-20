from __future__ import annotations

import argparse
import csv
from pathlib import Path

from build_region_csv import PREFECTURE_TO_REGION, REGION_LABELS, extract_prefecture


MULTI_VALUE_SEPARATOR = " | "
REGIONAL_GENRE_SUFFIXES = (
    "_east",
    "_west",
    "_tokyo",
    "_aichi",
    "_hokkaido",
    "_kanagawa",
    "_osaka",
    "_kagawa",
)
MY_MAP_GROUPS = {
    "casual_lunch": {
        "label": "Casual Lunch",
        "genre_slugs": [
            "ramen",
            "udon",
            "soba",
            "curry",
            "gyoza",
            "tonkatsu",
            "hamburger",
            "yoshoku",
            "shokudo",
        ],
    },
    "washoku_izakaya": {
        "label": "Washoku & Izakaya",
        "genre_slugs": [
            "japanese",
            "sushi",
            "unagi",
            "tempura",
            "sukiyaki_shabushabu",
            "yakitori",
            "toriryori",
            "izakaya",
            "tachinomi",
            "okonomiyaki",
        ],
    },
    "dinner_restaurants": {
        "label": "Dinner Restaurants",
        "genre_slugs": [
            "chinese",
            "italian",
            "pizza",
            "french",
            "spanish",
            "creative_innovative",
            "steak",
            "yakiniku",
            "asia_ethnic",
            "bar",
        ],
    },
    "cafe_sweets": {
        "label": "Cafe & Sweets",
        "genre_slugs": [
            "sweets",
            "wagashi",
            "cafe",
            "kissaten",
            "bread",
            "ice_gelato",
        ],
    },
}


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


def normalize_genre_slug(raw_slug: str) -> str:
    for suffix in REGIONAL_GENRE_SUFFIXES:
        if raw_slug.endswith(suffix):
            return raw_slug[: -len(suffix)]
    return raw_slug


def collect_mymap_rows(
    neutral_genre_rows: dict[str, list[dict[str, str]]],
) -> tuple[dict[str, dict[str, list[dict[str, str]]]], set[str], set[str]]:
    grouped_rows: dict[str, dict[str, list[dict[str, str]]]] = {}
    assigned_genre_slugs: set[str] = set()

    for mymap_slug, mymap_group in MY_MAP_GROUPS.items():
        grouped_rows[mymap_slug] = {}
        for genre_slug in mymap_group["genre_slugs"]:
            grouped_rows[mymap_slug][genre_slug] = neutral_genre_rows.get(genre_slug, [])
            assigned_genre_slugs.add(genre_slug)

    known_genre_slugs = set(neutral_genre_rows)
    missing_genre_slugs = assigned_genre_slugs - known_genre_slugs
    unassigned_genre_slugs = known_genre_slugs - assigned_genre_slugs
    return grouped_rows, missing_genre_slugs, unassigned_genre_slugs


def collect_neutral_genre_rows(
    rows: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    grouped_rows: dict[str, list[dict[str, str]]] = {}

    for row in rows:
        normalized_slugs = {
            normalize_genre_slug(raw_slug)
            for raw_slug in split_multi_value(row.get("Genre Slug", ""))
            if raw_slug
        }
        for normalized_slug in sorted(normalized_slugs):
            grouped_rows.setdefault(normalized_slug, []).append(row)

    return grouped_rows


def write_group_outputs(
    output_dir: Path,
    group_rows: dict[str, list[dict[str, str]]],
    group_definitions: dict[str, dict[str, object]],
    fieldnames: list[str],
    output_label: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_paths = {path.name for path in output_dir.glob("*.csv")}
    expected_paths = {f"{group_slug}.csv" for group_slug in group_definitions}
    for stale_name in sorted(existing_paths - expected_paths):
        stale_path = output_dir / stale_name
        stale_path.unlink()
        print(f"Removed stale {output_label} output {stale_path}")

    for group_slug, group in group_definitions.items():
        target_path = output_dir / f"{group_slug}.csv"
        rows = group_rows[group_slug]
        if not rows:
            if target_path.exists():
                target_path.unlink()
            print(
                f"Skipped empty {output_label} output {target_path}"
                f" ({group['label']})"
            )
            continue

        with target_path.open("w", encoding="utf-8", newline="") as target_file:
            writer = csv.DictWriter(target_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(
            f"Wrote {len(rows)} rows to {target_path}"
            f" ({group['label']})"
        )
def main() -> None:
    args = parse_args()
    input_root = Path(args.input_dir)
    output_root = Path(args.output_dir)
    by_region_dir = output_root / "by_region"
    by_genre_dir = output_root / "by_genre"
    for_mymap_dir = output_root / "for_mymap"

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
    neutral_genre_rows = collect_neutral_genre_rows(all_rows)
    grouped_rows, missing_genre_slugs, unassigned_genre_slugs = collect_mymap_rows(
        neutral_genre_rows
    )
    if missing_genre_slugs:
        missing_list = ", ".join(sorted(missing_genre_slugs))
        raise SystemExit(f"Unknown by_genre slugs referenced by for_mymap: {missing_list}")
    if unassigned_genre_slugs:
        unassigned_list = ", ".join(sorted(unassigned_genre_slugs))
        raise SystemExit(f"Unassigned by_genre slugs for for_mymap: {unassigned_list}")

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
    by_genre_dir.mkdir(parents=True, exist_ok=True)
    for_mymap_dir.mkdir(parents=True, exist_ok=True)
    expected_mymap_dirs = set(MY_MAP_GROUPS)
    existing_mymap_dirs = {
        path.name for path in for_mymap_dir.iterdir() if path.is_dir()
    }
    for stale_dir_name in sorted(existing_mymap_dirs - expected_mymap_dirs):
        stale_dir_path = for_mymap_dir / stale_dir_name
        for stale_csv in stale_dir_path.glob("*.csv"):
            stale_csv.unlink()
        stale_dir_path.rmdir()
        print(f"Removed stale for_mymap directory {stale_dir_path}")

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

    write_group_outputs(
        by_genre_dir,
        neutral_genre_rows,
        {
            genre_slug: {"label": genre_slug}
            for genre_slug in sorted(neutral_genre_rows)
        },
        fieldnames,
        "genre",
    )

    for mymap_group_slug, mymap_group in MY_MAP_GROUPS.items():
        write_group_outputs(
            for_mymap_dir / mymap_group_slug,
            grouped_rows[mymap_group_slug],
            {
                genre_slug: {"label": genre_slug}
                for genre_slug in mymap_group["genre_slugs"]
            },
            fieldnames,
            f"for_mymap {mymap_group_slug}",
        )

    print(f"Wrote {len(all_rows)} rows to {all_path}")


if __name__ == "__main__":
    main()