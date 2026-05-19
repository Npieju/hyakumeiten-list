from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

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


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser()
	parser.add_argument("--provider", required=True)
	parser.add_argument("--date", required=True)
	parser.add_argument("--party-size", required=True, type=int)
	parser.add_argument("--time-window", required=True, choices=["lunch", "dinner"])
	parser.add_argument("--db-path", default="data/app/hyakummeiten.sqlite3")
	parser.add_argument("--limit", type=int, default=10)
	parser.add_argument("--offset", type=int, default=0)
	return parser.parse_args()


def utc_now() -> datetime:
	return datetime.now(timezone.utc)


def to_iso(value: datetime) -> str:
	return value.isoformat(timespec="seconds")


def compute_expires_at(status: str, checked_at: datetime) -> str:
	minutes = TTL_MINUTES.get(status, TTL_MINUTES["unknown"])
	return to_iso(checked_at + timedelta(minutes=minutes))


def load_links(connection: sqlite3.Connection, provider: str, limit: int, offset: int) -> list[sqlite3.Row]:
	connection.row_factory = sqlite3.Row
	return connection.execute(
		"""
		SELECT
			r.shop_id,
			r.provider,
			r.provider_shop_id,
			r.provider_url,
			r.capability_status,
			r.match_status,
			r.match_confidence,
			s.name,
			s.address
		FROM reservation_links r
		JOIN shops s ON s.shop_id = r.shop_id
		WHERE r.provider = ?
		  AND r.match_status != 'rejected'
		ORDER BY r.shop_id
		LIMIT ? OFFSET ?
		""",
		(provider, limit, offset),
	).fetchall()


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
		"shop_id": row["shop_id"],
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


def main() -> None:
	args = parse_args()
	provider = get_provider(args.provider)
	now = utc_now()
	connection = sqlite3.connect(args.db_path)
	connection.execute("PRAGMA foreign_keys = ON")
	try:
		links = load_links(connection, args.provider, args.limit, args.offset)
		cache_hits = 0
		live_checks = 0
		items: list[dict[str, Any]] = []

		with connection:
			for link in links:
				cached = load_cache_row(
					connection,
					link["shop_id"],
					args.provider,
					args.date,
					args.party_size,
					args.time_window,
				)
				if is_cache_fresh(cached, now):
					cache_hits += 1
					items.append(serialize_cache_row(cached, "cache"))
					continue

				checked_at = utc_now()
				result = provider.fetch_availability(
					link,
					args.date,
					args.party_size,
					args.time_window,
				)
				result.checked_at = to_iso(checked_at)
				result.expires_at = compute_expires_at(result.status, checked_at)
				save_result(
					connection,
					link["shop_id"],
					args.provider,
					args.date,
					args.party_size,
					args.time_window,
					result,
				)
				live_checks += 1
				items.append(
					{
						"shop_id": link["shop_id"],
						"provider": args.provider,
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

		payload = {
			"provider": args.provider,
			"query_date": args.date,
			"party_size": args.party_size,
			"time_window": args.time_window,
			"total": len(links),
			"cache_hits": cache_hits,
			"live_checks": live_checks,
			"items": items,
		}
		print(json.dumps(payload, ensure_ascii=False, indent=2))
	finally:
		connection.close()


if __name__ == "__main__":
	main()