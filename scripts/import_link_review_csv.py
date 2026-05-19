from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


FIELDNAMES = [
	"review_id",
	"shop_id",
	"provider",
	"decision",
	"provider_shop_id",
	"provider_url",
	"capability_status",
	"notes",
]

ALLOWED_DECISIONS = {"approve", "reject"}
ALLOWED_CAPABILITY_STATUSES = {"supported", "not_supported", "unknown"}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser()
	parser.add_argument("--provider", required=True)
	parser.add_argument("--input", required=True)
	parser.add_argument("--db-path", default="data/app/hyakummeiten.sqlite3")
	parser.add_argument("--dry-run", action="store_true")
	return parser.parse_args()


def load_rows(input_path: Path) -> list[dict[str, str]]:
	with input_path.open("r", encoding="utf-8", newline="") as input_file:
		reader = csv.DictReader(input_file)
		fieldnames = reader.fieldnames or []
		if fieldnames != FIELDNAMES:
			raise SystemExit(
				"Invalid CSV header. Expected: " + ", ".join(FIELDNAMES)
			)
		return [
			{key: (value or "").strip() for key, value in row.items()}
			for row in reader
		]


def validate_row(row: dict[str, str], provider: str, row_number: int) -> None:
	if not row["review_id"].isdigit():
		raise SystemExit(f"Row {row_number}: review_id must be a positive integer")
	if not row["shop_id"]:
		raise SystemExit(f"Row {row_number}: shop_id is required")
	if row["provider"] != provider:
		raise SystemExit(
			f"Row {row_number}: provider mismatch. Expected {provider!r}, got {row['provider']!r}"
		)
	if row["decision"] not in ALLOWED_DECISIONS:
		raise SystemExit(
			f"Row {row_number}: decision must be one of {sorted(ALLOWED_DECISIONS)}"
		)
	if row["capability_status"] not in ALLOWED_CAPABILITY_STATUSES:
		raise SystemExit(
			"Row "
			+ str(row_number)
			+ f": capability_status must be one of {sorted(ALLOWED_CAPABILITY_STATUSES)}"
		)
	if row["decision"] == "approve":
		if not row["provider_shop_id"]:
			raise SystemExit(f"Row {row_number}: provider_shop_id is required for approve")
		if not row["provider_url"]:
			raise SystemExit(f"Row {row_number}: provider_url is required for approve")


def fetch_review_row(
	connection: sqlite3.Connection,
	review_id: int,
	provider: str,
	shop_id: str,
) -> sqlite3.Row:
	connection.row_factory = sqlite3.Row
	row = connection.execute(
		"""
		SELECT review_id, shop_id, provider, score, review_status
		FROM link_review_queue
		WHERE review_id = ? AND provider = ?
		""",
		(review_id, provider),
	).fetchone()
	if row is None:
		raise SystemExit(
			f"review_id={review_id} provider={provider!r} was not found in link_review_queue"
		)
	if row["shop_id"] != shop_id:
		raise SystemExit(
			f"review_id={review_id} shop_id mismatch. Expected {row['shop_id']!r}, got {shop_id!r}"
		)
	return row


def apply_review_decision(
	connection: sqlite3.Connection,
	row: dict[str, str],
	queue_row: sqlite3.Row,
	now: str,
) -> None:
	decision = row["decision"]
	match_status = "manually_confirmed" if decision == "approve" else "rejected"
	provider_shop_id = row["provider_shop_id"] or None
	provider_url = row["provider_url"] or None
	notes = row["notes"]

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
			row["shop_id"],
			row["provider"],
			provider_shop_id,
			provider_url,
			row["capability_status"],
			match_status,
			queue_row["score"],
			"manual_review_csv",
			now,
			notes,
		),
	)

	connection.execute(
		"""
		UPDATE link_review_queue
		SET review_status = ?, reviewed_at = ?
		WHERE review_id = ?
		""",
		(match_status, now, queue_row["review_id"]),
	)


def main() -> None:
	args = parse_args()
	input_path = Path(args.input)
	rows = load_rows(input_path)
	for index, row in enumerate(rows, start=2):
		validate_row(row, args.provider, index)

	if args.dry_run:
		print(f"provider={args.provider}")
		print(f"validated_rows={len(rows)}")
		print("dry_run=ok")
		return

	now = datetime.now(timezone.utc).isoformat(timespec="seconds")
	connection = sqlite3.connect(args.db_path)
	connection.execute("PRAGMA foreign_keys = ON")
	try:
		with connection:
			for row in rows:
				queue_row = fetch_review_row(
					connection,
					int(row["review_id"]),
					args.provider,
					row["shop_id"],
				)
				apply_review_decision(connection, row, queue_row, now)
	finally:
		connection.close()

	print(f"provider={args.provider}")
	print(f"imported_rows={len(rows)}")
	print(f"input={input_path}")


if __name__ == "__main__":
	main()