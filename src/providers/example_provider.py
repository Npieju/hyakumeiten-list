from __future__ import annotations

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
		_ = shop
		return []

	def resolve_shop(self, candidate: ProviderCandidate) -> ProviderLink:
		return ProviderLink(
			provider=self.name,
			provider_shop_id=candidate.provider_shop_id,
			provider_url=candidate.url,
			capability_status="unknown",
			match_status="review_required",
			match_confidence=candidate.score,
			matched_by="example_provider_noop",
			notes="no-op provider adapter",
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