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
	parser.add_argument("--provider", action="append", default=[])
	parser.add_argument("--date", required=True)
	parser.add_argument("--party-size", required=True, type=int)
	parser.add_argument("--time-window", required=True, choices=["lunch", "dinner"])
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
	parser.add_argument("--status", action="append", default=[])
	parser.add_argument("--limit", type=int, default=10)
	parser.add_argument("--offset", type=int, default=0)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	payload = search_availability(
		SearchFilters(
			db_path=args.db_path,
			years=args.year,
			genre_slugs=args.genre_slug,
			regions=args.region,
			prefectures=args.prefecture,
			name_query=args.name_query,
			address_query=args.address_query,
			min_lat=args.min_lat,
			max_lat=args.max_lat,
			min_lng=args.min_lng,
			max_lng=args.max_lng,
			has_multiple_years=args.has_multiple_years,
			limit=args.limit,
			offset=args.offset,
		),
		ReservationQuery(
			date=args.date,
			party_size=args.party_size,
			time_window=args.time_window,
			statuses=args.status,
			providers=args.provider,
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