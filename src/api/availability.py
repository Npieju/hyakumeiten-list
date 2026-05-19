from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from src.api.search import SearchFilters, search_shops
from src.providers.base import AvailabilityResult
from src.providers.registry import get_provider


TTL_MINUTES = {
	"bookable": 15,
	"sold_out": 15,
	"booking_closed": 60,
	"not_supported": 7 * 24 * 60,
	"provider_unlinked": 7 * 24 * 60,
	"provider_error": 5,
	"unknown": 10,
}

SUMMARY_PRIORITY = [
	"bookable",
	"sold_out",
	"booking_closed",
	"temporarily_closed",
	"not_supported",
	"provider_unlinked",
	"provider_error",
	"unknown",
]


@dataclass(slots=True)
class ReservationQuery:
	date: str
	party_size: int
	time_window: str
	statuses: list[str] = field(default_factory=list)
	providers: list[str] = field(default_factory=list)


def utc_now() -> datetime:
	return datetime.now(timezone.utc)


def to_iso(value: datetime) -> str:
	return value.isoformat(timespec="seconds")


def compute_expires_at(status: str, checked_at: datetime) -> str:
	minutes = TTL_MINUTES.get(status, TTL_MINUTES["unknown"])
	return to_iso(checked_at + timedelta(minutes=minutes))


def load_links_for_shops(
	connection: sqlite3.Connection,
	shop_ids: list[str],
	providers: list[str],
) -> dict[str, list[sqlite3.Row]]:
	connection.row_factory = sqlite3.Row
	if not shop_ids:
		return {}

	placeholders = ", ".join("?" for _ in shop_ids)
	parameters: list[Any] = list(shop_ids)
	provider_clause = ""
	if providers:
		provider_placeholders = ", ".join("?" for _ in providers)
		provider_clause = f" AND r.provider IN ({provider_placeholders})"
		parameters.extend(providers)

	rows = connection.execute(
		"""
		SELECT
			r.shop_id,
			r.provider,
			r.provider_shop_id,
			r.provider_url,
			r.capability_status,
			r.match_status,
			r.match_confidence,
			r.matched_by,
			r.notes
		FROM reservation_links r
		WHERE r.shop_id IN ("""
		+ placeholders
		+ ") AND r.match_status != 'rejected'"
		+ provider_clause
		+ " ORDER BY r.provider, r.shop_id",
		parameters,
	).fetchall()

	links_by_shop = {shop_id: [] for shop_id in shop_ids}
	for row in rows:
		links_by_shop[row["shop_id"]].append(row)
	return links_by_shop


def load_cache_row(
	connection: sqlite3.Connection,
	shop_id: str,
	provider: str,
	query_date: str,
	party_size: int,
	time_window: str,
) -> sqlite3.Row | None:
	connection.row_factory = sqlite3.Row
	return connection.execute(
		"""
		SELECT *
		FROM availability_cache
		WHERE shop_id = ?
		  AND provider = ?
		  AND query_date = ?
		  AND party_size = ?
		  AND time_window = ?
		""",
		(shop_id, provider, query_date, party_size, time_window),
	).fetchone()


def is_cache_fresh(row: sqlite3.Row | None, now: datetime) -> bool:
	if row is None:
		return False
	expires_at = datetime.fromisoformat(row["expires_at"])
	return expires_at > now


def serialize_cache_row(row: sqlite3.Row, source: str) -> dict[str, Any]:
	return {
		"provider": row["provider"],
		"status": row["status"],
		"status_reason": row["status_reason"],
		"reservation_url": row["reservation_url"],
		"available_slots": json.loads(row["available_slots_json"]),
		"checked_at": row["checked_at"],
		"expires_at": row["expires_at"],
		"raw_payload_hash": row["raw_payload_hash"],
		"source": source,
	}


def save_result(
	connection: sqlite3.Connection,
	shop_id: str,
	provider: str,
	query_date: str,
	party_size: int,
	time_window: str,
	result: AvailabilityResult,
) -> None:
	connection.execute(
		"""
		INSERT INTO availability_cache (
			shop_id,
			provider,
			query_date,
			party_size,
			time_window,
			status,
			status_reason,
			reservation_url,
			available_slots_json,
			checked_at,
			expires_at,
			raw_payload_hash
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(shop_id, provider, query_date, party_size, time_window) DO UPDATE SET
			status = excluded.status,
			status_reason = excluded.status_reason,
			reservation_url = excluded.reservation_url,
			available_slots_json = excluded.available_slots_json,
			checked_at = excluded.checked_at,
			expires_at = excluded.expires_at,
			raw_payload_hash = excluded.raw_payload_hash
		""",
		(
			shop_id,
			provider,
			query_date,
			party_size,
			time_window,
			result.status,
			result.status_reason,
			result.reservation_url,
			json.dumps(result.available_slots, ensure_ascii=False),
			result.checked_at,
			result.expires_at,
			result.raw_payload_hash,
		),
	)


def summarize_status(provider_rows: list[dict[str, Any]]) -> dict[str, str]:
	for status in SUMMARY_PRIORITY:
		for row in provider_rows:
			if row["status"] == status:
				return {"status": status, "status_reason": row["status_reason"]}
	return {"status": "unknown", "status_reason": "no_provider_result"}


def search_availability(
	filters: SearchFilters,
	reservation: ReservationQuery,
	limit: int,
	offset: int,
	live_check_limit: int = 50,
) -> dict[str, Any]:
	static_filters = SearchFilters(
		db_path=filters.db_path,
		years=filters.years,
		genre_slugs=filters.genre_slugs,
		regions=filters.regions,
		prefectures=filters.prefectures,
		name_query=filters.name_query,
		address_query=filters.address_query,
		min_lat=filters.min_lat,
		max_lat=filters.max_lat,
		min_lng=filters.min_lng,
		max_lng=filters.max_lng,
		has_multiple_years=filters.has_multiple_years,
		limit=max(limit, live_check_limit),
		offset=offset,
	)
	static_payload = search_shops(static_filters)
	static_items = static_payload["items"]
	static_total = static_payload["total"]
	shop_ids = [item["shop_id"] for item in static_items]

	connection = sqlite3.connect(filters.db_path)
	connection.execute("PRAGMA foreign_keys = ON")
	try:
		links_by_shop = load_links_for_shops(connection, shop_ids, reservation.providers)
		now = utc_now()
		cache_hits = 0
		live_checks = 0
		limited_live_checks = 0
		items: list[dict[str, Any]] = []

		with connection:
			for shop in static_items:
				provider_results: list[dict[str, Any]] = []
				links = links_by_shop.get(shop["shop_id"], [])
				if not links:
					provider_results.append(
						{
							"provider": None,
							"status": "provider_unlinked",
							"status_reason": "no_provider_link",
							"reservation_url": None,
							"available_slots": [],
							"checked_at": None,
							"expires_at": None,
							"raw_payload_hash": None,
							"source": "synthetic",
						}
					)
				else:
					for link in links:
						if link["capability_status"] == "not_supported":
							provider_results.append(
								{
									"provider": link["provider"],
									"status": "not_supported",
									"status_reason": "provider_marked_not_supported",
									"reservation_url": link["provider_url"],
									"available_slots": [],
									"checked_at": None,
									"expires_at": None,
									"raw_payload_hash": None,
									"source": "synthetic",
								}
							)
							continue

						cached = load_cache_row(
							connection,
							shop["shop_id"],
							link["provider"],
							reservation.date,
							reservation.party_size,
							reservation.time_window,
						)
						if is_cache_fresh(cached, now):
							cache_hits += 1
							provider_results.append(serialize_cache_row(cached, "cache"))
							continue

						if live_checks >= live_check_limit:
							limited_live_checks += 1
							provider_results.append(
								{
									"provider": link["provider"],
									"status": "unknown",
									"status_reason": "live_check_limit_exceeded",
									"reservation_url": link["provider_url"],
									"available_slots": [],
									"checked_at": None,
									"expires_at": None,
									"raw_payload_hash": None,
									"source": "skipped",
								}
							)
							continue

						checked_at = utc_now()
						provider = get_provider(link["provider"])
						result = provider.fetch_availability(
							link,
							reservation.date,
							reservation.party_size,
							reservation.time_window,
						)
						result.checked_at = to_iso(checked_at)
						result.expires_at = compute_expires_at(result.status, checked_at)
						save_result(
							connection,
							shop["shop_id"],
							link["provider"],
							reservation.date,
							reservation.party_size,
							reservation.time_window,
							result,
						)
						live_checks += 1
						provider_results.append(
							{
								"provider": link["provider"],
								"status": result.status,
								"status_reason": result.status_reason,
								"reservation_url": result.reservation_url,
								"available_slots": result.available_slots,
								"checked_at": result.checked_at,
								"expires_at": result.expires_at,
								"raw_payload_hash": result.raw_payload_hash,
								"source": "live",
							}
						)

				reservation_summary = summarize_status(provider_results)
				if reservation.statuses and reservation_summary["status"] not in reservation.statuses:
					continue

				items.append(
					{
						**shop,
						"reservation_summary": reservation_summary,
						"providers": provider_results,
					}
				)

		denominator = cache_hits + live_checks
		cache_hit_ratio = 0.0 if denominator == 0 else cache_hits / denominator
		warning = "live_check_limit_exceeded" if limited_live_checks else None
		return {
			"total": static_total,
			"cache_hit_ratio": cache_hit_ratio,
			"live_checks": live_checks,
			"warning": warning,
			"items": items[:limit],
		}
	finally:
		connection.close()