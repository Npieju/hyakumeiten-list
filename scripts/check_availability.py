from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from src.api.availability import ReservationQuery, search_availability
from src.api.search import SearchFilters


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


def main() -> None:
	args = parse_args()
	payload = search_availability(
		SearchFilters(db_path=args.db_path, limit=args.limit, offset=args.offset),
		ReservationQuery(
			date=args.date,
			party_size=args.party_size,
			time_window=args.time_window,
			providers=[args.provider],
		),
		limit=args.limit,
		offset=args.offset,
	)
	payload["provider"] = args.provider
	payload["query_date"] = args.date
	payload["party_size"] = args.party_size
	payload["time_window"] = args.time_window
	print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()