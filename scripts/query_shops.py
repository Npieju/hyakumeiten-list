from __future__ import annotations

import argparse
import json
import sqlite3
import unicodedata
from typing import Any


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser()
	parser.add_argument("--db-path", default="data/app/hyakummeiten.sqlite3")
	parser.add_argument("--year", type=int, action="append", default=[])
	parser.add_argument("--genre-slug", action="append", default=[])
	parser.add_argument("--region", action="append", default=[])
	parser.add_argument("--prefecture", action="append", default=[])
	parser.add_argument("--name-query")
	parser.add_argument("--address-query")
	parser.add_argument("--min-lat", type=float)
	parser.add_argument("--max-lat", type=float)
	parser.add_argument("--min-lng", type=float)
	parser.add_argument("--max-lng", type=float)
	parser.add_argument("--has-multiple-years", action="store_true")
	parser.add_argument("--limit", type=int, default=20)
	parser.add_argument("--offset", type=int, default=0)
	return parser.parse_args()


def normalize_text(value: str) -> str:
	normalized = unicodedata.normalize("NFKC", value).strip().lower()
	return "".join(normalized.split())


def make_in_clause(values: list[Any]) -> str:
	return ", ".join("?" for _ in values)


def build_where_clause(args: argparse.Namespace) -> tuple[str, list[Any]]:
	clauses = ["1 = 1"]
	parameters: list[Any] = []

	if args.region:
		clauses.append(f"s.region IN ({make_in_clause(args.region)})")
		parameters.extend(args.region)

	if args.prefecture:
		clauses.append(f"s.prefecture IN ({make_in_clause(args.prefecture)})")
		parameters.extend(args.prefecture)

	if args.name_query:
		clauses.append("s.normalized_name LIKE ?")
		parameters.append(f"%{normalize_text(args.name_query)}%")

	if args.address_query:
		clauses.append("s.normalized_address LIKE ?")
		parameters.append(f"%{normalize_text(args.address_query)}%")

	if args.min_lat is not None:
		clauses.append("s.latitude >= ?")
		parameters.append(args.min_lat)

	if args.max_lat is not None:
		clauses.append("s.latitude <= ?")
		parameters.append(args.max_lat)

	if args.min_lng is not None:
		clauses.append("s.longitude >= ?")
		parameters.append(args.min_lng)

	if args.max_lng is not None:
		clauses.append("s.longitude <= ?")
		parameters.append(args.max_lng)

	if args.has_multiple_years:
		clauses.append(
			"(SELECT COUNT(*) FROM shop_years sy_multi WHERE sy_multi.shop_id = s.shop_id) > 1"
		)

	if args.genre_slug:
		genre_clause = [f"sg.genre_slug IN ({make_in_clause(args.genre_slug)})"]
		genre_parameters: list[Any] = list(args.genre_slug)
		if args.year:
			genre_clause.append(f"sg.year IN ({make_in_clause(args.year)})")
			genre_parameters.extend(args.year)
		clauses.append(
			"EXISTS ("
			"SELECT 1 FROM shop_genres sg "
			"WHERE sg.shop_id = s.shop_id AND "
			+ " AND ".join(genre_clause)
			+ ")"
		)
		parameters.extend(genre_parameters)
	elif args.year:
		clauses.append(
			"EXISTS ("
			f"SELECT 1 FROM shop_years sy WHERE sy.shop_id = s.shop_id AND sy.year IN ({make_in_clause(args.year)})"
			")"
		)
		parameters.extend(args.year)

	return " AND ".join(clauses), parameters


def load_years(connection: sqlite3.Connection, shop_ids: list[str]) -> dict[str, list[int]]:
	if not shop_ids:
		return {}
	query = (
		"SELECT shop_id, year FROM shop_years "
		f"WHERE shop_id IN ({make_in_clause(shop_ids)}) ORDER BY year, shop_id"
	)
	rows = connection.execute(query, shop_ids).fetchall()
	years_by_shop: dict[str, list[int]] = {shop_id: [] for shop_id in shop_ids}
	for row in rows:
		years_by_shop[row["shop_id"]].append(row["year"])
	return years_by_shop


def load_genres(
	connection: sqlite3.Connection,
	shop_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
	if not shop_ids:
		return {}
	query = (
		"SELECT shop_id, year, genre_slug, genre_name FROM shop_genres "
		f"WHERE shop_id IN ({make_in_clause(shop_ids)}) ORDER BY year, genre_slug, shop_id"
	)
	rows = connection.execute(query, shop_ids).fetchall()
	genres_by_shop: dict[str, list[dict[str, Any]]] = {shop_id: [] for shop_id in shop_ids}
	for row in rows:
		genres_by_shop[row["shop_id"]].append(
			{
				"year": row["year"],
				"genre_slug": row["genre_slug"],
				"genre_name": row["genre_name"],
			}
		)
	return genres_by_shop


def main() -> None:
	args = parse_args()
	connection = sqlite3.connect(args.db_path)
	connection.row_factory = sqlite3.Row
	try:
		where_clause, parameters = build_where_clause(args)

		total_query = f"SELECT COUNT(*) AS total FROM shops s WHERE {where_clause}"
		total = connection.execute(total_query, parameters).fetchone()["total"]

		items_query = (
			"SELECT s.shop_id, s.name, s.address, s.latitude, s.longitude, s.region, s.prefecture, "
			"s.tabelog_url, s.google_maps_url "
			f"FROM shops s WHERE {where_clause} ORDER BY s.name, s.shop_id LIMIT ? OFFSET ?"
		)
		rows = connection.execute(
			items_query,
			[*parameters, args.limit, args.offset],
		).fetchall()

		shop_ids = [row["shop_id"] for row in rows]
		years_by_shop = load_years(connection, shop_ids)
		genres_by_shop = load_genres(connection, shop_ids)

		payload = {
			"total": total,
			"items": [
				{
					"shop_id": row["shop_id"],
					"name": row["name"],
					"address": row["address"],
					"latitude": row["latitude"],
					"longitude": row["longitude"],
					"region": row["region"],
					"prefecture": row["prefecture"],
					"tabelog_url": row["tabelog_url"],
					"google_maps_url": row["google_maps_url"],
					"years": years_by_shop.get(row["shop_id"], []),
					"genres": genres_by_shop.get(row["shop_id"], []),
				}
				for row in rows
			],
		}
		print(json.dumps(payload, ensure_ascii=False, indent=2))
	finally:
		connection.close()



if __name__ == "__main__":
	main()