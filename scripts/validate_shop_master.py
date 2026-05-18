from __future__ import annotations

import argparse
import sqlite3


REQUIRED_TABLES = {
	"app_metadata",
	"shops",
	"shop_years",
	"shop_genres",
	"reservation_links",
	"availability_cache",
	"link_review_queue",
}

REQUIRED_SHOPS_COLUMNS = {
	"shop_id",
	"tabelog_url",
	"name",
	"normalized_name",
	"address",
	"normalized_address",
	"google_maps_url",
	"latitude",
	"longitude",
	"prefecture",
	"region",
	"created_at",
	"updated_at",
}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser()
	parser.add_argument("--db-path", default="data/app/hyakummeiten.sqlite3")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	connection = sqlite3.connect(args.db_path)
	try:
		table_rows = connection.execute(
			"SELECT name FROM sqlite_master WHERE type = 'table'"
		).fetchall()
		tables = {row[0] for row in table_rows}
		missing_tables = REQUIRED_TABLES - tables
		if missing_tables:
			raise SystemExit(f"Missing tables: {sorted(missing_tables)}")

		shops_columns = {
			row[1] for row in connection.execute("PRAGMA table_info(shops)").fetchall()
		}
		missing_columns = REQUIRED_SHOPS_COLUMNS - shops_columns
		if missing_columns:
			raise SystemExit(f"Missing shops columns: {sorted(missing_columns)}")

		metadata = dict(connection.execute("SELECT key, value FROM app_metadata").fetchall())
		if "schema_version" not in metadata:
			raise SystemExit("Missing schema_version in app_metadata")
		if "generated_at" not in metadata:
			raise SystemExit("Missing generated_at in app_metadata")

		counts = {
			"shops": connection.execute("SELECT COUNT(*) FROM shops").fetchone()[0],
			"shop_years": connection.execute("SELECT COUNT(*) FROM shop_years").fetchone()[0],
			"shop_genres": connection.execute("SELECT COUNT(*) FROM shop_genres").fetchone()[0],
		}
		missing_coordinates = connection.execute(
			"SELECT COUNT(*) FROM shops WHERE latitude IS NULL OR longitude IS NULL"
		).fetchone()[0]
		if missing_coordinates:
			raise SystemExit(f"Missing coordinates in shops: {missing_coordinates}")

		print(f"schema_version={metadata['schema_version']}")
		print(f"generated_at={metadata['generated_at']}")
		for name, count in counts.items():
			print(f"{name}={count}")
		print("shops_coordinates=ok")
	finally:
		connection.close()


if __name__ == "__main__":
	main()