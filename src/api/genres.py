from __future__ import annotations

import re
import sqlite3
from collections import defaultdict


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

REGIONAL_GENRE_NAME_SUFFIXES = (
	" EAST",
	" WEST",
	" TOKYO",
	" AICHI",
	" HOKKAIDO",
	" KANAGAWA",
	" OSAKA",
	" KAGAWA",
)


def normalize_genre_slug(raw_slug: str) -> str:
	for suffix in REGIONAL_GENRE_SUFFIXES:
		if raw_slug.endswith(suffix):
			return raw_slug[: -len(suffix)]
	return raw_slug


def normalize_genre_label(raw_name: str, fallback_slug: str) -> str:
	name = re.sub(r"\s+百名店(?:\s+[A-Z]+)?(?:\s+\d{4})?$", "", raw_name).strip()
	name = re.sub(r"\s+\d{4}$", "", name).strip()
	for suffix in REGIONAL_GENRE_NAME_SUFFIXES:
		if name.endswith(suffix):
			name = name[: -len(suffix)].strip()
			break
	return name or fallback_slug.replace("_", " ").title()


def list_genre_filters(db_path: str = "data/app/hyakummeiten.sqlite3") -> dict[str, object]:
	connection = sqlite3.connect(db_path)
	connection.row_factory = sqlite3.Row
	try:
		rows = connection.execute(
			"SELECT genre_slug, genre_name FROM shop_genres ORDER BY genre_slug, genre_name"
		).fetchall()
	finally:
		connection.close()

	grouped_slugs: dict[str, set[str]] = defaultdict(set)
	grouped_labels: dict[str, set[str]] = defaultdict(set)

	for row in rows:
		raw_slug = row["genre_slug"]
		base_slug = normalize_genre_slug(raw_slug)
		grouped_slugs[base_slug].add(raw_slug)
		grouped_labels[base_slug].add(normalize_genre_label(row["genre_name"], base_slug))

	items = []
	for base_slug in sorted(grouped_slugs):
		labels = sorted(grouped_labels[base_slug], key=lambda value: (len(value), value))
		items.append(
			{
				"slug": base_slug,
				"label": labels[0],
				"slugs": sorted(grouped_slugs[base_slug]),
			}
		)

	return {"items": items}