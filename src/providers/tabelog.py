from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Mapping

import requests

from src.providers.base import (
	AvailabilityResult,
	ProviderAdapter,
	ProviderCandidate,
	ProviderLink,
	default_expires_at,
	utc_now_iso,
)


BOOKING_CALENDAR_URL = "https://tabelog.com/booking/calendar/find_vacancy_date_with_status/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"


def extract_provider_shop_id(url: str) -> str | None:
	path_tail = url.rstrip("/").split("/")[-1]
	return path_tail or None


def map_day_status(day_payload: Mapping[str, Any]) -> tuple[str, str]:
	availability = int(day_payload.get("available", 0) or 0)
	if bool(day_payload.get("holiday")):
		return "temporarily_closed", "tabelog_holiday"
	if availability > 0:
		return "bookable", "tabelog_public_calendar"
	return "sold_out", "tabelog_public_calendar"


def link_value(link: Mapping[str, Any], key: str) -> Any:
	if hasattr(link, "keys") and key in link.keys():
		return link[key]
	return None


class TabelogAdapter(ProviderAdapter):
	name = "tabelog"

	def __init__(self) -> None:
		self.session = requests.Session()
		self.session.headers.update({
			"User-Agent": USER_AGENT,
			"X-Requested-With": "XMLHttpRequest",
		})

	def search_candidates(self, shop: Mapping[str, Any]) -> list[ProviderCandidate]:
		tabelog_url = str(shop.get("tabelog_url") or "").strip()
		provider_shop_id = extract_provider_shop_id(tabelog_url)
		if not tabelog_url or not provider_shop_id:
			return []

		return [
			ProviderCandidate(
				provider=self.name,
				provider_shop_id=provider_shop_id,
				name=str(shop.get("name") or ""),
				url=tabelog_url,
				address=str(shop.get("address") or ""),
				score=1.0,
				raw_payload={"source": "tabelog_url"},
			)
		]

	def resolve_shop(self, candidate: ProviderCandidate) -> ProviderLink:
		return ProviderLink(
			provider=self.name,
			provider_shop_id=candidate.provider_shop_id,
			provider_url=candidate.url,
			capability_status="supported",
			match_status="auto_linked",
			match_confidence=candidate.score,
			matched_by="tabelog_adapter",
			notes="Resolved directly from Tabelog restaurant URL.",
		)

	def fetch_availability(
		self,
		link: Mapping[str, Any],
		date: str,
		party_size: int,
		time_window: str,
	) -> AvailabilityResult:
		provider_shop_id = str(link_value(link, "provider_shop_id") or "").strip()
		reservation_url = str(link_value(link, "provider_url") or "").strip() or None
		if not provider_shop_id:
			return AvailabilityResult(
				provider=self.name,
				status="provider_unlinked",
				status_reason="missing_tabelog_shop_id",
				reservation_url=reservation_url,
				available_slots=[],
				checked_at=utc_now_iso(),
				expires_at=default_expires_at(),
			)

		referer = reservation_url or f"https://tabelog.com/{provider_shop_id}/"
		response = self.session.get(
			BOOKING_CALENDAR_URL,
			params={"rst_id": provider_shop_id},
			headers={"Referer": referer},
			timeout=30,
		)
		if response.status_code == 400:
			return AvailabilityResult(
				provider=self.name,
				status="not_supported",
				status_reason="tabelog_booking_not_supported",
				reservation_url=reservation_url,
				available_slots=[],
				checked_at=utc_now_iso(),
				expires_at=default_expires_at(),
				raw_payload_hash="sha1:" + hashlib.sha1(response.text.encode("utf-8")).hexdigest(),
			)
		response.raise_for_status()
		payload = response.json()

		target_date = datetime.strptime(date, "%Y-%m-%d")
		date_list = payload.get("list")
		if not isinstance(date_list, list):
			date_list = payload.get("date_with_status", {}).get("dateList", [])

		target_day = next(
			(
				item
				for item in date_list
				if item.get("year") == target_date.year
				and item.get("month") == target_date.month
				and item.get("day") == target_date.day
			),
			None,
		)

		if target_day is None:
			return AvailabilityResult(
				provider=self.name,
				status="booking_closed",
				status_reason="tabelog_date_out_of_window",
				reservation_url=reservation_url,
				available_slots=[],
				checked_at=utc_now_iso(),
				expires_at=default_expires_at(),
				raw_payload_hash="sha1:" + hashlib.sha1(response.text.encode("utf-8")).hexdigest(),
			)

		status, status_reason = map_day_status(target_day)
		available_slots = []
		if status == "bookable":
			available_slots = ["lunch available"] if time_window == "lunch" else ["dinner available"]

		return AvailabilityResult(
			provider=self.name,
			status=status,
			status_reason=status_reason,
			reservation_url=reservation_url,
			available_slots=available_slots,
			checked_at=utc_now_iso(),
			expires_at=default_expires_at(),
			raw_payload_hash="sha1:" + hashlib.sha1(response.text.encode("utf-8")).hexdigest(),
		)


def get_provider() -> ProviderAdapter:
	return TabelogAdapter()