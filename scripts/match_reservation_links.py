from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from src.providers.base import ProviderCandidate, ProviderLink
from src.providers.registry import get_provider


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser()
	parser.add_argument("--provider", required=True)
	parser.add_argument("--db-path", default="data/app/hyakummeiten.sqlite3")
	parser.add_argument("--limit", type=int, default=50)
	parser.add_argument("--offset", type=int, default=0)
	parser.add_argument("--min-score-auto", type=float, default=0.9)
	return parser.parse_args()


def load_shops(
	connection: sqlite3.Connection,
	limit: int,
	offset: int,
) -> list[sqlite3.Row]:
	connection.row_factory = sqlite3.Row
	return connection.execute(
		"""
		SELECT
			shop_id,
			name,
			normalized_name,
			address,
			normalized_address,
			tabelog_url,
			google_maps_url,
			prefecture,
			region
		FROM shops
		ORDER BY shop_id
		LIMIT ? OFFSET ?
		""",
		(limit, offset),
	).fetchall()


def upsert_reservation_link(
	connection: sqlite3.Connection,
	shop_id: str,
	provider_name: str,
	link: ProviderLink,
	now: str,
) -> None:
	connection.execute(
		"""
		INSERT INTO reservation_links (
			shop_id,
			provider,
			provider_shop_id,
			provider_url,
			capability_status,
			match_status,
			match_confidence,
			matched_by,
			last_verified_at,
			notes
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(shop_id, provider) DO UPDATE SET
			provider_shop_id = excluded.provider_shop_id,
			provider_url = excluded.provider_url,
			capability_status = excluded.capability_status,
			match_status = excluded.match_status,
			match_confidence = excluded.match_confidence,
			matched_by = excluded.matched_by,
			last_verified_at = excluded.last_verified_at,
			notes = excluded.notes
		""",
		(
			shop_id,
			provider_name,
			link.provider_shop_id,
			link.provider_url,
			link.capability_status,
			link.match_status,
			link.match_confidence,
			link.matched_by,
			now,
			link.notes,
		),
	)


def replace_review_queue_row(
	connection: sqlite3.Connection,
	shop_id: str,
	provider_name: str,
	candidate: ProviderCandidate,
	now: str,
) -> None:
	connection.execute(
		"DELETE FROM link_review_queue WHERE shop_id = ? AND provider = ? AND review_status = 'pending'",
		(shop_id, provider_name),
	)
	connection.execute(
		"""
		INSERT INTO link_review_queue (
			shop_id,
			provider,
			candidate_name,
			candidate_url,
			candidate_address,
			score,
			review_status,
			created_at,
			reviewed_at
		) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, NULL)
		""",
		(
			shop_id,
			provider_name,
			candidate.name,
			candidate.url,
			candidate.address,
			candidate.score,
			now,
		),
	)


def clear_pending_review_rows(
	connection: sqlite3.Connection,
	shop_id: str,
	provider_name: str,
) -> None:
	connection.execute(
		"DELETE FROM link_review_queue WHERE shop_id = ? AND provider = ? AND review_status = 'pending'",
		(shop_id, provider_name),
	)


def main() -> None:
	args = parse_args()
	provider = get_provider(args.provider)
	now = utc_now_iso()

	connection = sqlite3.connect(args.db_path)
	connection.execute("PRAGMA foreign_keys = ON")
	try:
		shops = load_shops(connection, args.limit, args.offset)
		auto_linked = 0
		review_required = 0
		skipped = 0

		with connection:
			for shop in shops:
				candidates = provider.search_candidates(shop)
				if not candidates:
					skipped += 1
					clear_pending_review_rows(connection, shop["shop_id"], provider.name)
					continue

				best_candidate = max(candidates, key=lambda candidate: candidate.score)
				link = provider.resolve_shop(best_candidate)
				if best_candidate.score >= args.min_score_auto:
					link.match_status = "auto_linked"
					clear_pending_review_rows(connection, shop["shop_id"], provider.name)
					auto_linked += 1
				else:
					link.match_status = "review_required"
					replace_review_queue_row(
						connection,
						shop["shop_id"],
						provider.name,
						best_candidate,
						now,
					)
					review_required += 1

				upsert_reservation_link(
					connection,
					shop["shop_id"],
					provider.name,
					link,
					now,
				)

		print(f"provider={provider.name}")
		print(f"processed={len(shops)}")
		print(f"auto_linked={auto_linked}")
		print(f"review_required={review_required}")
		print(f"skipped={skipped}")
	finally:
		connection.close()


if __name__ == "__main__":
	main()