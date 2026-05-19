from __future__ import annotations

import hashlib
from typing import Any, Mapping

from src.providers.base import (
	AvailabilityResult,
	ProviderAdapter,
	ProviderCandidate,
	ProviderLink,
	default_expires_at,
	utc_now_iso,
)


class ExampleProviderAdapter(ProviderAdapter):
	name = "example_provider"

	def search_candidates(self, shop: Mapping[str, Any]) -> list[ProviderCandidate]:
		shop_id = str(shop["shop_id"])
		bucket = int(hashlib.sha1(shop_id.encode("utf-8")).hexdigest()[-1], 16) % 3
		if bucket == 0:
			score = 0.96
			candidate_name = str(shop["name"])
			candidate_address = str(shop["address"])
		else:
			score = 0.72
			candidate_name = f"{shop['name']} (example)"
			candidate_address = str(shop["address"])

		provider_shop_id = shop_id.replace(":", "-")
		return [
			ProviderCandidate(
				provider=self.name,
				provider_shop_id=provider_shop_id,
				name=candidate_name,
				url=f"https://example.com/shops/{provider_shop_id}",
				address=candidate_address,
				score=score,
				raw_payload={"source_shop_id": shop_id},
			)
		]

	def resolve_shop(self, candidate: ProviderCandidate) -> ProviderLink:
		match_status = "auto_linked" if candidate.score >= 0.9 else "review_required"
		return ProviderLink(
			provider=self.name,
			provider_shop_id=candidate.provider_shop_id,
			provider_url=candidate.url,
			capability_status="supported",
			match_status=match_status,
			match_confidence=candidate.score,
			matched_by="example_provider_stub",
			notes="deterministic stub provider adapter",
		)

	def fetch_availability(
		self,
		link: Mapping[str, Any],
		date: str,
		party_size: int,
		time_window: str,
	) -> AvailabilityResult:
		_ = (link, date, party_size, time_window)
		return AvailabilityResult(
			provider=self.name,
			status="unknown",
			status_reason="example_provider_noop",
			reservation_url=None,
			available_slots=[],
			checked_at=utc_now_iso(),
			expires_at=default_expires_at(),
			raw_payload_hash=None,
		)


def get_provider() -> ProviderAdapter:
	return ExampleProviderAdapter()