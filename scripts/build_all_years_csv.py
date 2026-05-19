from __future__ import annotations

import argparse
import csv
from pathlib import Path

from build_region_csv import PREFECTURE_TO_REGION, REGION_LABELS, extract_prefecture


MULTI_VALUE_SEPARATOR = " | "
MERGED_GENRE_GROUPS = {
    "ramen": {
        "label": "Ramen",
        "genre_slugs": {
            "ramen_aichi",
            "ramen_east",
            "ramen_hokkaido",
            "ramen_kanagawa",
            "ramen_osaka",
            "ramen_tokyo",
            "ramen_west",
        },
    },
    "sushi_seafood": {
        "label": "Sushi & Seafood",
        "genre_slugs": {
            "sushi_east",
            "sushi_tokyo",
            "sushi_west",
            "unagi",
        },
    },
    "meat_grill": {
        "label": "Meat & Grill",
        "genre_slugs": {
            "steak_east",
            "steak_west",
            "tonkatsu",
            "toriryori",
            "yakitori_east",
            "yakitori_west",
            "yakiniku_east",
            "yakiniku_tokyo",
            "yakiniku_west",
        },
    },
    "udon_soba": {
        "label": "Udon & Soba",
        "genre_slugs": {
            "soba_east",
            "soba_west",
            "udon_east",
            "udon_kagawa",
            "udon_west",
        },
    },
    "japanese_kitchen": {
        "label": "Japanese Kitchen",
        "genre_slugs": {
            "japanese_east",
            "japanese_tokyo",
            "japanese_west",
            "okonomiyaki",
            "shokudo",
            "sukiyaki_shabushabu",
            "tempura",
        },
    },
    "western_european": {
        "label": "Western & European",
        "genre_slugs": {
            "creative_innovative",
            "french_east",
            "french_tokyo",
            "french_west",
            "italian_east",
            "italian_tokyo",
            "italian_west",
            "spanish",
            "yoshoku_east",
            "yoshoku_west",
        },
    },
    "asian_chinese": {
        "label": "Asian & Chinese",
        "genre_slugs": {
            "asia_ethnic_east",
            "asia_ethnic_tokyo",
            "asia_ethnic_west",
            "chinese_east",
            "chinese_tokyo",
            "chinese_west",
            "gyoza",
        },
    },
    "sweets_cafe": {
        "label": "Sweets & Cafe",
        "genre_slugs": {
            "cafe_east",
            "cafe_west",
            "ice_gelato",
            "kissaten",
            "sweets_east",
            "sweets_tokyo",
            "sweets_west",
            "wagashi_east",
            "wagashi_tokyo",
            "wagashi_west",
        },
    },
    "bakery_fastfood": {
        "label": "Bakery & Fast Food",
        "genre_slugs": {
            "bread_east",
            "bread_tokyo",
            "bread_west",
            "hamburger",
            "pizza",
        },
    },
    "curry_izakaya_bar": {
        "label": "Curry, Izakaya & Bar",
        "genre_slugs": {
            "bar",
            "curry_east",
            "curry_tokyo",
            "curry_west",
            "izakaya_east",
            "izakaya_west",
            "tachinomi",
        },
    },
}
MY_MAP_GROUPS = {
    "lunch": {
        "label": "Lunch",
        "genre_groups": [
            "ramen",
            "udon_soba",
            "asian_chinese",
            "bakery_fastfood",
            "curry_izakaya_bar",
        ],
    },
    "dinner": {
        "label": "Dinner",
        "genre_groups": [
            "sushi_seafood",
            "meat_grill",
            "japanese_kitchen",
            "western_european",
            "asian_chinese",
            "curry_izakaya_bar",
        ],
    },
    "snack": {
        "label": "Snack & Cafe",
        "genre_groups": [
            "sweets_cafe",
            "bakery_fastfood",
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


def collect_group_rows(
    rows: list[dict[str, str]],
) -> tuple[dict[str, list[dict[str, str]]], set[str]]:
    grouped_rows = {group_slug: [] for group_slug in MERGED_GENRE_GROUPS}
    unmatched_genre_slugs: set[str] = set()

    for row in rows:
        row_genre_slugs = set(split_multi_value(row.get("Genre Slug", "")))
        if not row_genre_slugs:
            continue

        matched_group = False
        for group_slug, group in MERGED_GENRE_GROUPS.items():
            if row_genre_slugs & group["genre_slugs"]:
                grouped_rows[group_slug].append(row)
                matched_group = True

        if not matched_group:
            unmatched_genre_slugs.update(row_genre_slugs)
            continue

        matched_slugs = set().union(
            *[
                group["genre_slugs"]
                for group in MERGED_GENRE_GROUPS.values()
                if row_genre_slugs & group["genre_slugs"]
            ]
        )
        unmatched_genre_slugs.update(row_genre_slugs - matched_slugs)

    return grouped_rows, unmatched_genre_slugs


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


def collect_mymap_rows(
    grouped_rows: dict[str, list[dict[str, str]]],
) -> dict[str, list[dict[str, str]]]:
    mymap_rows: dict[str, list[dict[str, str]]] = {}
    for mymap_group_slug, mymap_group in MY_MAP_GROUPS.items():
        rows: list[dict[str, str]] = []
        for genre_group_slug in mymap_group["genre_groups"]:
            rows.extend(grouped_rows[genre_group_slug])
        mymap_rows[mymap_group_slug] = rows
    return mymap_rows


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
    grouped_rows, unmatched_genre_slugs = collect_group_rows(all_rows)
    if unmatched_genre_slugs:
        unmatched_list = ", ".join(sorted(unmatched_genre_slugs))
        raise SystemExit(f"Unmapped genre slugs found in all_years rows: {unmatched_list}")

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
        grouped_rows,
        MERGED_GENRE_GROUPS,
        fieldnames,
        "genre",
    )
    for mymap_group_slug, mymap_group in MY_MAP_GROUPS.items():
        write_group_outputs(
            for_mymap_dir / mymap_group_slug,
            {
                genre_group_slug: grouped_rows[genre_group_slug]
                for genre_group_slug in mymap_group["genre_groups"]
            },
            {
                genre_group_slug: MERGED_GENRE_GROUPS[genre_group_slug]
                for genre_group_slug in mymap_group["genre_groups"]
            },
            fieldnames,
            f"for_mymap {mymap_group_slug}",
        )

    print(f"Wrote {len(all_rows)} rows to {all_path}")


if __name__ == "__main__":
    main()