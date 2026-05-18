from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from build_region_csv import PREFECTURE_TO_REGION, extract_prefecture


SCHEMA_SQL = """
CREATE TABLE shops (
	shop_id TEXT PRIMARY KEY,
	tabelog_url TEXT NOT NULL UNIQUE,
	name TEXT NOT NULL,
	normalized_name TEXT NOT NULL,
	address TEXT NOT NULL,
	normalized_address TEXT NOT NULL,
	google_maps_url TEXT NOT NULL,
	prefecture TEXT NOT NULL,
	region TEXT NOT NULL,
	created_at TEXT NOT NULL,
	updated_at TEXT NOT NULL
);

CREATE INDEX idx_shops_region ON shops(region);
CREATE INDEX idx_shops_prefecture ON shops(prefecture);
CREATE INDEX idx_shops_normalized_name ON shops(normalized_name);

CREATE TABLE shop_years (
	shop_id TEXT NOT NULL,
	year INTEGER NOT NULL,
	release_date TEXT NOT NULL,
	PRIMARY KEY (shop_id, year),
	FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
);

CREATE INDEX idx_shop_years_year ON shop_years(year);

CREATE TABLE shop_genres (
	shop_id TEXT NOT NULL,
	year INTEGER NOT NULL,
	genre_slug TEXT NOT NULL,
	genre_name TEXT NOT NULL,
	PRIMARY KEY (shop_id, year, genre_slug),
	FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
);

CREATE INDEX idx_shop_genres_slug_year ON shop_genres(genre_slug, year);
CREATE INDEX idx_shop_genres_year ON shop_genres(year);

CREATE TABLE reservation_links (
	link_id INTEGER PRIMARY KEY AUTOINCREMENT,
	shop_id TEXT NOT NULL,
	provider TEXT NOT NULL,
	provider_shop_id TEXT,
	provider_url TEXT,
	capability_status TEXT NOT NULL,
	match_status TEXT NOT NULL,
	match_confidence REAL,
	matched_by TEXT NOT NULL,
	last_verified_at TEXT,
	notes TEXT NOT NULL DEFAULT '',
	FOREIGN KEY (shop_id) REFERENCES shops(shop_id),
	UNIQUE (shop_id, provider),
	UNIQUE (provider, provider_shop_id)
);

CREATE INDEX idx_reservation_links_provider ON reservation_links(provider);
CREATE INDEX idx_reservation_links_match_status ON reservation_links(match_status);

CREATE TABLE availability_cache (
	shop_id TEXT NOT NULL,
	provider TEXT NOT NULL,
	query_date TEXT NOT NULL,
	party_size INTEGER NOT NULL,
	time_window TEXT NOT NULL,
	status TEXT NOT NULL,
	status_reason TEXT NOT NULL,
	reservation_url TEXT,
	available_slots_json TEXT NOT NULL DEFAULT '[]',
	checked_at TEXT NOT NULL,
	expires_at TEXT NOT NULL,
	raw_payload_hash TEXT,
	PRIMARY KEY (shop_id, provider, query_date, party_size, time_window),
	FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
);

CREATE INDEX idx_availability_cache_lookup
ON availability_cache(query_date, party_size, time_window, provider, status, expires_at);

CREATE TABLE link_review_queue (
	review_id INTEGER PRIMARY KEY AUTOINCREMENT,
	shop_id TEXT NOT NULL,
	provider TEXT NOT NULL,
	candidate_name TEXT NOT NULL,
	candidate_url TEXT NOT NULL,
	candidate_address TEXT NOT NULL,
	score REAL NOT NULL,
	review_status TEXT NOT NULL DEFAULT 'pending',
	created_at TEXT NOT NULL,
	reviewed_at TEXT,
	FOREIGN KEY (shop_id) REFERENCES shops(shop_id)
);
"""


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser()
	parser.add_argument("--input-dir", default="data")
	parser.add_argument("--output-path", default="data/app/hyakummeiten.sqlite3")
	return parser.parse_args()


def canonicalize_tabelog_url(url: str) -> str:
	parts = urlsplit(url.strip())
	path = parts.path.rstrip("/") + "/"
	return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def build_shop_id(tabelog_url: str) -> str:
	path_tail = urlsplit(tabelog_url).path.rstrip("/").split("/")[-1]
	if path_tail.isdigit():
		return f"tabelog:{path_tail}"
	hash_value = hashlib.sha1(tabelog_url.encode("utf-8")).hexdigest()[:16]
	return f"tabelog:{hash_value}"


def normalize_text(value: str) -> str:
	normalized = unicodedata.normalize("NFKC", value).strip().lower()
	return re.sub(r"\s+", "", normalized)


def prefer_value(current: str, candidate: str) -> str:
	if not current:
		return candidate
	if len(candidate) > len(current):
		return candidate
	return current


def iter_source_rows(input_root: Path) -> list[tuple[int, dict[str, str]]]:
	source_rows: list[tuple[int, dict[str, str]]] = []
	for year_dir in sorted(input_root.glob("[0-9][0-9][0-9][0-9]")):
		if not year_dir.name.isdigit():
			continue
		by_genre_dir = year_dir / "by_genre"
		for csv_path in sorted(by_genre_dir.glob("*.csv")):
			with csv_path.open("r", encoding="utf-8", newline="") as source_file:
				reader = csv.DictReader(source_file)
				if reader.fieldnames is None:
					raise SystemExit(f"No CSV header found in {csv_path}")
				for row in reader:
					source_rows.append((int(year_dir.name), row))
	if not source_rows:
		raise SystemExit(f"No yearly by_genre CSV files found in {input_root}")
	return source_rows


def build_shop_records(
	source_rows: list[tuple[int, dict[str, str]]],
	now: str,
) -> tuple[
	dict[str, dict[str, str]],
	dict[tuple[str, int], str],
	set[tuple[str, int, str, str]],
]:
	shops: dict[str, dict[str, str]] = {}
	shop_years: dict[tuple[str, int], str] = {}
	shop_genres: set[tuple[str, int, str, str]] = set()

	for fallback_year, row in source_rows:
		tabelog_url = canonicalize_tabelog_url(row.get("Website", ""))
		if not tabelog_url:
			raise SystemExit(f"Missing Website: {row}")

		shop_id = build_shop_id(tabelog_url)
		name = row.get("Name", "").strip()
		address = row.get("Address", "").strip()
		google_maps_url = row.get("Google Maps URL", "").strip()
		prefecture = extract_prefecture(address) or ""
		region = PREFECTURE_TO_REGION.get(prefecture, "unknown")

		existing_shop = shops.get(shop_id)
		if existing_shop is None:
			shops[shop_id] = {
				"shop_id": shop_id,
				"tabelog_url": tabelog_url,
				"name": name,
				"normalized_name": normalize_text(name),
				"address": address,
				"normalized_address": normalize_text(address),
				"google_maps_url": google_maps_url,
				"prefecture": prefecture,
				"region": region,
				"created_at": now,
				"updated_at": now,
			}
		else:
			existing_shop["name"] = prefer_value(existing_shop["name"], name)
			existing_shop["address"] = prefer_value(existing_shop["address"], address)
			existing_shop["google_maps_url"] = prefer_value(
				existing_shop["google_maps_url"],
				google_maps_url,
			)
			if prefecture and not existing_shop["prefecture"]:
				existing_shop["prefecture"] = prefecture
				existing_shop["region"] = region
			existing_shop["normalized_name"] = normalize_text(existing_shop["name"])
			existing_shop["normalized_address"] = normalize_text(existing_shop["address"])
			existing_shop["updated_at"] = now

		year = int(row.get("Year", "") or fallback_year)
		release_date = row.get("Release Date", "").strip()
		shop_year_key = (shop_id, year)
		if shop_year_key not in shop_years or (release_date and not shop_years[shop_year_key]):
			shop_years[shop_year_key] = release_date

		genre_slug = row.get("Genre Slug", "").strip()
		genre_name = row.get("Genre", "").strip()
		if not genre_slug:
			raise SystemExit(f"Missing Genre Slug: {row}")
		if not genre_name:
			raise SystemExit(f"Missing Genre: {row}")
		shop_genres.add((shop_id, year, genre_slug, genre_name))

	return shops, shop_years, shop_genres


def create_database(output_path: Path) -> sqlite3.Connection:
	output_path.parent.mkdir(parents=True, exist_ok=True)
	if output_path.exists():
		output_path.unlink()
	connection = sqlite3.connect(output_path)
	connection.execute("PRAGMA foreign_keys = ON")
	connection.executescript(SCHEMA_SQL)
	return connection


def insert_records(
	connection: sqlite3.Connection,
	shops: dict[str, dict[str, str]],
	shop_years: dict[tuple[str, int], str],
	shop_genres: set[tuple[str, int, str, str]],
) -> None:
	connection.executemany(
		"""
		INSERT INTO shops (
			shop_id,
			tabelog_url,
			name,
			normalized_name,
			address,
			normalized_address,
			google_maps_url,
			prefecture,
			region,
			created_at,
			updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		""",
		[
			(
				shop["shop_id"],
				shop["tabelog_url"],
				shop["name"],
				shop["normalized_name"],
				shop["address"],
				shop["normalized_address"],
				shop["google_maps_url"],
				shop["prefecture"],
				shop["region"],
				shop["created_at"],
				shop["updated_at"],
			)
			for shop in sorted(shops.values(), key=lambda item: item["shop_id"])
		],
	)

	connection.executemany(
		"""
		INSERT INTO shop_years (shop_id, year, release_date)
		VALUES (?, ?, ?)
		""",
		[
			(shop_id, year, release_date)
			for (shop_id, year), release_date in sorted(shop_years.items())
		],
	)

	connection.executemany(
		"""
		INSERT INTO shop_genres (shop_id, year, genre_slug, genre_name)
		VALUES (?, ?, ?, ?)
		""",
		sorted(shop_genres),
	)

	connection.commit()


def main() -> None:
	args = parse_args()
	input_root = Path(args.input_dir)
	output_path = Path(args.output_path)
	now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

	source_rows = iter_source_rows(input_root)
	shops, shop_years, shop_genres = build_shop_records(source_rows, now)

	connection = create_database(output_path)
	try:
		insert_records(connection, shops, shop_years, shop_genres)
	finally:
		connection.close()

	print(f"Wrote {len(shops)} shops to {output_path}")
	print(f"Wrote {len(shop_years)} shop_years rows to {output_path}")
	print(f"Wrote {len(shop_genres)} shop_genres rows to {output_path}")


if __name__ == "__main__":
	main()