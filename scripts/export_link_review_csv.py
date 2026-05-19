from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


FIELDNAMES = [
	"review_id",
	"shop_id",
	"shop_name",
	"shop_address",
	"tabelog_url",
	"google_maps_url",
	"provider",
	"candidate_name",
	"candidate_url",
	"candidate_address",
	"score",
	"review_status",
	"created_at",
]


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser()
	parser.add_argument("--provider", required=True)
	parser.add_argument("--db-path", default="data/app/hyakummeiten.sqlite3")
	parser.add_argument("--output")
	parser.add_argument("--allow-empty", action="store_true")
	return parser.parse_args()


def default_output_path(provider: str) -> Path:
	return Path("data/linkage") / provider / "review_candidates.csv"


def load_review_rows(connection: sqlite3.Connection, provider: str) -> list[dict[str, str]]:
	connection.row_factory = sqlite3.Row
	rows = connection.execute(
		"""
		SELECT
			q.review_id,
			q.shop_id,
			s.name AS shop_name,
			s.address AS shop_address,
			s.tabelog_url,
			s.google_maps_url,
			q.provider,
			q.candidate_name,
			q.candidate_url,
			q.candidate_address,
			q.score,
			q.review_status,
			q.created_at
		FROM link_review_queue q
		JOIN shops s ON s.shop_id = q.shop_id
		WHERE q.provider = ?
		  AND q.review_status = 'pending'
		ORDER BY q.score DESC, q.review_id ASC
		""",
		(provider,),
	).fetchall()
	return [
		{
			"review_id": str(row["review_id"]),
			"shop_id": row["shop_id"],
			"shop_name": row["shop_name"],
			"shop_address": row["shop_address"],
			"tabelog_url": row["tabelog_url"],
			"google_maps_url": row["google_maps_url"],
			"provider": row["provider"],
			"candidate_name": row["candidate_name"],
			"candidate_url": row["candidate_url"],
			"candidate_address": row["candidate_address"],
			"score": str(row["score"]),
			"review_status": row["review_status"],
			"created_at": row["created_at"],
		}
		for row in rows
	]


def main() -> None:
	args = parse_args()
	output_path = Path(args.output) if args.output else default_output_path(args.provider)

	connection = sqlite3.connect(args.db_path)
	try:
		rows = load_review_rows(connection, args.provider)
	finally:
		connection.close()

	if not rows and not args.allow_empty:
		raise SystemExit(
			f"No pending review rows for provider={args.provider!r}. Use --allow-empty to write a header-only CSV."
		)

	output_path.parent.mkdir(parents=True, exist_ok=True)
	with output_path.open("w", encoding="utf-8", newline="") as output_file:
		writer = csv.DictWriter(output_file, fieldnames=FIELDNAMES)
		writer.writeheader()
		writer.writerows(rows)

	print(f"provider={args.provider}")
	print(f"rows={len(rows)}")
	print(f"output={output_path}")


if __name__ == "__main__":
	main()