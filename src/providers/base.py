from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_expires_at(minutes: int = 15) -> str:
	return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(
		timespec="seconds"
	)


@dataclass(slots=True)
class ProviderCandidate:
	provider: str
	provider_shop_id: str
	name: str
	url: str
	address: str
	score: float = 0.0
	raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderLink:
	provider: str
	provider_shop_id: str | None
	provider_url: str | None
	capability_status: str
	match_status: str
	match_confidence: float | None
	matched_by: str
	notes: str = ""


@dataclass(slots=True)
class AvailabilityResult:
	provider: str
	status: str
	status_reason: str
	reservation_url: str | None
	available_slots: list[str]
	checked_at: str
	expires_at: str
	raw_payload_hash: str | None = None


class ProviderAdapter(ABC):
	name: str

	@abstractmethod
	def search_candidates(self, shop: Mapping[str, Any]) -> list[ProviderCandidate]:
		raise NotImplementedError

	@abstractmethod
	def resolve_shop(self, candidate: ProviderCandidate) -> ProviderLink:
		raise NotImplementedError

	@abstractmethod
	def fetch_availability(
		self,
		link: Mapping[str, Any],
		date: str,
		party_size: int,
		time_window: str,
	) -> AvailabilityResult:
		raise NotImplementedError