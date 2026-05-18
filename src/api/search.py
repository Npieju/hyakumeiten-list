from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SearchFilters:
	db_path: str = "data/app/hyakummeiten.sqlite3"
	years: list[int] = field(default_factory=list)
	genre_slugs: list[str] = field(default_factory=list)
	regions: list[str] = field(default_factory=list)
	prefectures: list[str] = field(default_factory=list)
	name_query: str | None = None
	address_query: str | None = None
	min_lat: float | None = None
	max_lat: float | None = None
	min_lng: float | None = None
	max_lng: float | None = None
	has_multiple_years: bool = False
	limit: int = 100
	offset: int = 0


def normalize_text(value: str) -> str:
	normalized = unicodedata.normalize("NFKC", value).strip().lower()
	return "".join(normalized.split())


def make_in_clause(values: list[Any]) -> str:
	return ", ".join("?" for _ in values)


def build_where_clause(filters: SearchFilters) -> tuple[str, list[Any]]:
	clauses = ["1 = 1"]
	parameters: list[Any] = []

	if filters.regions:
		clauses.append(f"s.region IN ({make_in_clause(filters.regions)})")
		parameters.extend(filters.regions)

	if filters.prefectures:
		clauses.append(f"s.prefecture IN ({make_in_clause(filters.prefectures)})")
		parameters.extend(filters.prefectures)

	if filters.name_query:
		clauses.append("s.normalized_name LIKE ?")
		parameters.append(f"%{normalize_text(filters.name_query)}%")

	if filters.address_query:
		clauses.append("s.normalized_address LIKE ?")
		parameters.append(f"%{normalize_text(filters.address_query)}%")

	if filters.min_lat is not None:
		clauses.append("s.latitude >= ?")
		parameters.append(filters.min_lat)

	if filters.max_lat is not None:
		clauses.append("s.latitude <= ?")
		parameters.append(filters.max_lat)

	if filters.min_lng is not None:
		clauses.append("s.longitude >= ?")
		parameters.append(filters.min_lng)

	if filters.max_lng is not None:
		clauses.append("s.longitude <= ?")
		parameters.append(filters.max_lng)

	if filters.has_multiple_years:
		clauses.append(
			"(SELECT COUNT(*) FROM shop_years sy_multi WHERE sy_multi.shop_id = s.shop_id) > 1"
		)

	if filters.genre_slugs:
		genre_clause = [f"sg.genre_slug IN ({make_in_clause(filters.genre_slugs)})"]
		genre_parameters: list[Any] = list(filters.genre_slugs)
		if filters.years:
			genre_clause.append(f"sg.year IN ({make_in_clause(filters.years)})")
			genre_parameters.extend(filters.years)
		clauses.append(
			"EXISTS ("
			"SELECT 1 FROM shop_genres sg "
			"WHERE sg.shop_id = s.shop_id AND "
			+ " AND ".join(genre_clause)
			+ ")"
		)
		parameters.extend(genre_parameters)
	elif filters.years:
		clauses.append(
			"EXISTS ("
			f"SELECT 1 FROM shop_years sy WHERE sy.shop_id = s.shop_id AND sy.year IN ({make_in_clause(filters.years)})"
			")"
		)
		parameters.extend(filters.years)

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


def search_shops(filters: SearchFilters) -> dict[str, Any]:
	connection = sqlite3.connect(filters.db_path)
	connection.row_factory = sqlite3.Row
	try:
		where_clause, parameters = build_where_clause(filters)

		total_query = f"SELECT COUNT(*) AS total FROM shops s WHERE {where_clause}"
		total = connection.execute(total_query, parameters).fetchone()["total"]

		items_query = (
			"SELECT s.shop_id, s.name, s.address, s.latitude, s.longitude, s.region, s.prefecture, "
			"s.tabelog_url, s.google_maps_url "
			f"FROM shops s WHERE {where_clause} ORDER BY s.name, s.shop_id LIMIT ? OFFSET ?"
		)
		rows = connection.execute(
			items_query,
			[*parameters, filters.limit, filters.offset],
		).fetchall()

		shop_ids = [row["shop_id"] for row in rows]
		years_by_shop = load_years(connection, shop_ids)
		genres_by_shop = load_genres(connection, shop_ids)
		returned = len(rows)
		truncated = total > filters.offset + returned
		warning = "too_many_results_in_viewport" if truncated else None

		return {
			"total": total,
			"returned": returned,
			"truncated": truncated,
			"warning": warning,
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
	finally:
		connection.close()