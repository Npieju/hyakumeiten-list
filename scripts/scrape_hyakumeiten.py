from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://award.tabelog.com"
HYAKUMEITEN_ROOT = f"{BASE_URL}/hyakumeiten"

ADDRESS_OVERRIDES = {
    "https://tabelog.com/tokyo/A1303/A130302/13154404/": "東京都豊島区南大塚1-50-5 コーポ大塚マンション 1F",
    "https://tabelog.com/hokkaido/A0104/A010401/1001167/": "北海道旭川市東5条11丁目2-1",
    "https://tabelog.com/tokyo/A1307/A130703/13213368/": "東京都渋谷区広尾5-1-32 ST広尾 2F",
    "https://tabelog.com/fukuoka/A4001/A400101/40001706/": "福岡県福岡市博多区博多駅前4-3-11",
    "https://tabelog.com/chiba/A1201/A120101/12046922/": "千葉県千葉市中央区中央3-15-4",
    "https://tabelog.com/osaka/A2701/A270101/27113792/": "大阪府大阪市北区堂山町16-2",
    "https://tabelog.com/aichi/A2301/A230101/23082892/": "愛知県名古屋市中区栄2-14-1",
}
COORDINATE_OVERRIDES = {
    "https://tabelog.com/tokyo/A1303/A130302/13154404/": (35.7317076, 139.7292447),
    "https://tabelog.com/hokkaido/A0104/A010401/1001167/": (43.7801047, 142.3772754),
    "https://tabelog.com/tokyo/A1307/A130703/13213368/": (35.6515, 139.7226),
    "https://tabelog.com/fukuoka/A4001/A400101/40001706/": (33.5855, 130.4150),
    "https://tabelog.com/chiba/A1201/A120101/12046922/": (35.6074, 140.1227),
    "https://tabelog.com/kanagawa/A1401/A140306/14072173/": (35.4746, 139.5463),
    "https://tabelog.com/osaka/A2701/A270101/27113792/": (34.7041, 135.5036),
    "https://tabelog.com/aichi/A2301/A230101/23082892/": (35.1654, 136.9015),
}
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
GENRE_LINK_PATTERN = re.compile(r"^/hyakumeiten/(?P<slug>[a-z0-9_]+)$")
SHOP_PATH_PATTERN = re.compile(r"^/[a-z]+/A\d+/A\d+/\d+/?$")
SHOP_LINK_SELECTORS = (
    "a.hyakumeiten-shop__target[href]",
    "a.list-shop__link-page[href]",
    "a.shop__name[href]",
    "a.shop-button__detail[href]",
    "a.hyakumeiten-rstlist__target[href]",
    "a.hyakumeiten-keyvisual__target[href]",
    "a.rstlist__target[href]",
)
LISTING_NAME_SELECTORS = (
    ".hyakumeiten-shop__name",
    ".shop__name",
    ".rstlist__name",
    ".hyakummeiten-rstlist__name",
)
LISTING_AREA_SELECTORS = (
    ".hyakumeiten-shop__station",
    ".shop__area",
    ".rstlist__info",
    ".hyakummeiten-rstlist__info",
)
REQUEST_TIMEOUT = 30
REQUEST_RETRIES = 3
REQUEST_RETRY_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class Genre:
    slug: str
    title: str
    year: int
    release_date: str
    url: str


@dataclass(frozen=True)
class Shop:
    name: str
    address: str
    description: str
    website: str
    tabelog_reservation_url: str
    google_maps_url: str
    latitude: str
    longitude: str
    year: int
    genre: str
    genre_slug: str
    release_date: str


@dataclass(frozen=True)
class ShopLink:
    url: str
    listed_name: str
    listed_area: str


@dataclass(frozen=True)
class UnavailableShop:
    website: str
    year: int
    genre: str
    genre_slug: str
    release_date: str
    reason: str
    status_code: int | None
    listed_name: str
    listed_area: str


def print_progress(message: str) -> None:
    print(f"[progress] {message}", file=sys.stderr, flush=True)


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        }
    )
    return session


def fetch_response(session: requests.Session, url: str) -> requests.Response:
    last_error: requests.RequestException | None = None

    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            return session.get(url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as error:
            last_error = error
            if attempt == REQUEST_RETRIES:
                raise

            print_progress(
                f"retrying request {attempt}/{REQUEST_RETRIES - 1} after error for {url}: {error}"
            )
            time.sleep(REQUEST_RETRY_DELAY_SECONDS * attempt)

    if last_error is not None:
        raise last_error

    raise RuntimeError(f"request failed without an exception for {url}")


def fetch_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = fetch_response(session, url)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def extract_candidate_slugs(session: requests.Session) -> list[str]:
    soup = fetch_soup(session, HYAKUMEITEN_ROOT)
    slugs: set[str] = set()

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        match = GENRE_LINK_PATTERN.match(href)
        if match:
            slugs.add(match.group("slug"))

    return sorted(slugs)


def parse_genre_title(title_text: str, year: int) -> str:
    cleaned = title_text.strip()
    cleaned = cleaned.removeprefix("食べログ ")
    cleaned = cleaned.removesuffix(" [食べログ]")
    cleaned = cleaned.removesuffix(f" 百名店 {year}")
    return cleaned.strip()


def resolve_genres(session: requests.Session, year: int) -> list[Genre]:
    genres: list[Genre] = []
    candidate_slugs = extract_candidate_slugs(session)
    total_candidates = len(candidate_slugs)

    print_progress(f"resolving {year} genres from {total_candidates} candidates")

    for index, slug in enumerate(candidate_slugs, start=1):
        genre_url = f"{HYAKUMEITEN_ROOT}/{slug}/{year}"
        print_progress(f"checking genre {index}/{total_candidates}: {slug}")
        response = fetch_response(session, genre_url)
        if response.status_code == 404:
            continue

        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title_tag = soup.find("title")
        if title_tag is None or str(year) not in title_tag.get_text(strip=True):
            continue

        release_node = soup.select_one(".hyakumeiten-search__release-day")
        release_date = release_node.get_text(" ", strip=True) if release_node else ""
        title = parse_genre_title(title_tag.get_text(strip=True), year)

        genres.append(
            Genre(
                slug=slug,
                title=title,
                year=year,
                release_date=release_date,
                url=genre_url,
            )
        )

    return sorted(genres, key=lambda genre: genre.slug)


def iter_restaurant_json_ld(soup: BeautifulSoup) -> Iterable[dict[str, object]]:
    for script in soup.select('script[type="application/ld+json"]'):
        raw_text = script.string or script.get_text(strip=True)
        if not raw_text:
            continue

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            continue

        candidates: list[dict] = []
        if isinstance(payload, dict):
            if payload.get("@type") == "Restaurant":
                candidates.append(payload)
            graph = payload.get("@graph")
            if isinstance(graph, list):
                candidates.extend(
                    item
                    for item in graph
                    if isinstance(item, dict) and item.get("@type") == "Restaurant"
                )
        elif isinstance(payload, list):
            candidates.extend(
                item
                for item in payload
                if isinstance(item, dict) and item.get("@type") == "Restaurant"
            )

        for restaurant in candidates:
            yield restaurant


def parse_restaurant_json_ld(soup: BeautifulSoup) -> tuple[str, str, str, str]:
    for restaurant in iter_restaurant_json_ld(soup):
            name = str(restaurant.get("name", "")).strip()
            address_payload = restaurant.get("address") or {}
            if not isinstance(address_payload, dict):
                address_payload = {}
            address = "".join(
                str(address_payload.get(key, "")).strip()
                for key in ("addressRegion", "addressLocality", "streetAddress")
            )
            geo_payload = restaurant.get("geo") or {}
            if not isinstance(geo_payload, dict):
                geo_payload = {}
            latitude = str(geo_payload.get("latitude", "")).strip()
            longitude = str(geo_payload.get("longitude", "")).strip()
            if name and address:
                return name, address, latitude, longitude

    return "", "", "", ""


def extract_reserve_action_url(shop_url: str, payload: object) -> str:
    actions = payload if isinstance(payload, list) else [payload]
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("@type") != "ReserveAction":
            continue
        targets = action.get("target")
        targets = targets if isinstance(targets, list) else [targets]
        for target in targets:
            if isinstance(target, dict):
                candidates = [target.get("urlTemplate"), target.get("url")]
            else:
                candidates = [target]
            for candidate in candidates:
                if not candidate:
                    continue
                return urljoin(shop_url, str(candidate).strip())
    return ""


def parse_tabelog_reservation_url(shop_url: str, soup: BeautifulSoup) -> str:
    for restaurant in iter_restaurant_json_ld(soup):
        reservation_url = extract_reserve_action_url(
            shop_url,
            restaurant.get("potentialAction"),
        )
        if reservation_url:
            return reservation_url

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "").strip()
        if not href:
            continue
        absolute_url = urljoin(shop_url, href)
        parsed = urlparse(absolute_url)
        if parsed.netloc == "yoyaku.tabelog.com":
            return absolute_url
        if parsed.netloc == "tabelog.com" and "faq_yoyaku" in parsed.query:
            return absolute_url

    if soup.select_one(".js-show-yoyaku-modal-trigger, .rstdtl-side-yoyaku__booking"):
        return shop_url

    reserve_status = soup.select_one(".rstinfo-table__reserve-status")
    if reserve_status is not None:
        reserve_text = reserve_status.get_text(" ", strip=True)
        if reserve_text and "予約可" in reserve_text:
            return shop_url

    return ""


def format_coordinate(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return f"{float(text):.7f}"
    except ValueError:
        return text


def build_google_maps_url(address: str, name: str) -> str:
    query = quote(f"{name} {address}".strip())
    if "13154404" in query and "東京都豊島区南大塚1-50-5" not in query:
        query = quote(f"{name} 東京都豊島区南大塚1-50-5 コーポ大塚マンション 1F".strip())
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def normalize_shop_url(url: str) -> str | None:
    parsed = urlparse(urljoin(BASE_URL, url))
    if parsed.netloc != "tabelog.com":
        return None
    if not SHOP_PATH_PATTERN.match(parsed.path):
        return None
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}/"


def extract_first_text(anchor: BeautifulSoup, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        node = anchor.select_one(selector)
        if node is None:
            continue
        text = node.get_text(" ", strip=True)
        if text:
            return text
    return ""


def extract_shop_links(soup: BeautifulSoup) -> list[ShopLink]:
    shop_links: list[ShopLink] = []
    seen_links: set[str] = set()

    for selector in SHOP_LINK_SELECTORS:
        for anchor in soup.select(selector):
            href = anchor.get("href", "")
            shop_url = normalize_shop_url(href)
            if shop_url is None or shop_url in seen_links:
                continue
            seen_links.add(shop_url)
            listed_name = extract_first_text(anchor, LISTING_NAME_SELECTORS)
            listed_area = extract_first_text(anchor, LISTING_AREA_SELECTORS)
            if not listed_name:
                listed_name = anchor.get_text(" ", strip=True)
            shop_links.append(
                ShopLink(
                    url=shop_url,
                    listed_name=listed_name,
                    listed_area=listed_area,
                )
            )

    return shop_links


def fetch_shop(
    session: requests.Session,
    genre: Genre,
    shop_link: ShopLink,
) -> tuple[Shop, UnavailableShop | None]:
    try:
        soup = fetch_soup(session, shop_link.url)
    except requests.HTTPError as error:
        status_code = error.response.status_code if error.response is not None else None
        if status_code == 404:
            print_progress(f"including unavailable shop page as fallback row: {shop_link.url}")
            latitude, longitude = COORDINATE_OVERRIDES.get(shop_link.url, ("", ""))
            return (
                Shop(
                    name=shop_link.listed_name,
                    address=ADDRESS_OVERRIDES.get(shop_link.url, ""),
                    description=f"食べログ {genre.title} 百名店 {genre.year}",
                    website=shop_link.url,
                    tabelog_reservation_url="",
                    google_maps_url=build_google_maps_url(
                        ADDRESS_OVERRIDES.get(shop_link.url, shop_link.listed_area),
                        shop_link.listed_name,
                    ),
                    latitude=format_coordinate(latitude),
                    longitude=format_coordinate(longitude),
                    year=genre.year,
                    genre=genre.title,
                    genre_slug=genre.slug,
                    release_date=genre.release_date,
                ),
                UnavailableShop(
                    website=shop_link.url,
                    year=genre.year,
                    genre=genre.title,
                    genre_slug=genre.slug,
                    release_date=genre.release_date,
                    reason="http_404",
                    status_code=status_code,
                    listed_name=shop_link.listed_name,
                    listed_area=shop_link.listed_area,
                ),
            )
        raise

    name, address, latitude, longitude = parse_restaurant_json_ld(soup)

    if not name:
        heading = soup.select_one(".display-name span")
        name = heading.get_text(strip=True) if heading else ""
    if not address:
        address_node = soup.select_one(".rstinfo-table__address")
        address = address_node.get_text("", strip=True) if address_node else ""
    address = ADDRESS_OVERRIDES.get(shop_link.url, address)
    override_latitude, override_longitude = COORDINATE_OVERRIDES.get(shop_link.url, ("", ""))
    latitude = format_coordinate(override_latitude or latitude)
    longitude = format_coordinate(override_longitude or longitude)
    tabelog_reservation_url = parse_tabelog_reservation_url(shop_link.url, soup)

    description = f"食べログ {genre.title} 百名店 {genre.year}"
    return (
        Shop(
            name=name,
            address=address,
            description=description,
            website=shop_link.url,
            tabelog_reservation_url=tabelog_reservation_url,
            google_maps_url=build_google_maps_url(address, name),
            latitude=latitude,
            longitude=longitude,
            year=genre.year,
            genre=genre.title,
            genre_slug=genre.slug,
            release_date=genre.release_date,
        ),
        None,
    )


def scrape_genre_shops(
    session: requests.Session,
    genre: Genre,
    throttle_seconds: float,
    workers: int,
) -> tuple[list[Shop], list[UnavailableShop]]:
    print_progress(f"loading genre page: {genre.slug}")
    soup = fetch_soup(session, genre.url)
    shop_links = extract_shop_links(soup)

    total_shops = len(shop_links)
    unavailable_shops: list[UnavailableShop] = []
    print_progress(f"found {total_shops} shops for {genre.slug}")
    if workers <= 1:
        shops: list[Shop] = []
        for index, shop_link in enumerate(shop_links, start=1):
            if index == 1 or index == total_shops or index % 10 == 0:
                print_progress(f"fetching {genre.slug} shop {index}/{total_shops}")
            shop, unavailable_shop = fetch_shop(session, genre, shop_link)
            shops.append(shop)
            if unavailable_shop is not None:
                unavailable_shops.append(unavailable_shop)
            if throttle_seconds > 0:
                time.sleep(throttle_seconds)
        if unavailable_shops:
            print_progress(
                f"recorded {len(unavailable_shops)} unavailable shop pages for {genre.slug}"
            )
        return shops, unavailable_shops

    indexed_shops: list[tuple[int, Shop]] = []
    indexed_unavailable_shops: list[tuple[int, UnavailableShop]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_index = {
            executor.submit(fetch_shop, session, genre, shop_link): index
            for index, shop_link in enumerate(shop_links, start=1)
        }
        completed = 0
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            shop, unavailable_shop = future.result()
            indexed_shops.append((index, shop))
            if unavailable_shop is not None:
                indexed_unavailable_shops.append((index, unavailable_shop))
            completed += 1
            if completed == 1 or completed == total_shops or completed % 10 == 0:
                print_progress(f"fetched {genre.slug} shop {completed}/{total_shops}")
            if throttle_seconds > 0:
                time.sleep(throttle_seconds)

    if indexed_unavailable_shops:
        print_progress(
            f"recorded {len(indexed_unavailable_shops)} unavailable shop pages for {genre.slug}"
        )
    indexed_shops.sort(key=lambda item: item[0])
    indexed_unavailable_shops.sort(key=lambda item: item[0])
    return [shop for _, shop in indexed_shops], [shop for _, shop in indexed_unavailable_shops]


def write_csv(path: Path, rows: Iterable[dict[str, str | int]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def genre_rows(genres: Iterable[Genre]) -> Iterable[dict[str, str | int]]:
    for genre in genres:
        yield {
            "Year": genre.year,
            "Genre": genre.title,
            "Genre Slug": genre.slug,
            "Release Date": genre.release_date,
            "URL": genre.url,
        }


def shop_rows(shops: Iterable[Shop]) -> Iterable[dict[str, str | int]]:
    for shop in shops:
        yield {
            "Name": shop.name,
            "Address": shop.address,
            "Description": shop.description,
            "Website": shop.website,
            "Tabelog Reservation URL": shop.tabelog_reservation_url,
            "Google Maps URL": shop.google_maps_url,
            "Latitude": shop.latitude,
            "Longitude": shop.longitude,
            "Year": shop.year,
            "Genre": shop.genre,
            "Genre Slug": shop.genre_slug,
            "Release Date": shop.release_date,
        }


def unavailable_shop_rows(
    unavailable_shops: Iterable[UnavailableShop],
) -> Iterable[dict[str, str | int]]:
    for unavailable_shop in unavailable_shops:
        yield {
            "Website": unavailable_shop.website,
            "Year": unavailable_shop.year,
            "Genre": unavailable_shop.genre,
            "Genre Slug": unavailable_shop.genre_slug,
            "Release Date": unavailable_shop.release_date,
            "Reason": unavailable_shop.reason,
            "Status Code": unavailable_shop.status_code or "",
            "Listed Name": unavailable_shop.listed_name,
            "Listed Area": unavailable_shop.listed_area,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--genres-only", action="store_true")
    parser.add_argument("--genre", dest="genre_slugs", action="append")
    parser.add_argument("--throttle-seconds", type=float, default=0.3)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    session = build_session()
    output_root = Path(args.output_dir) / str(args.year)

    all_genres = resolve_genres(session, args.year)
    genres = all_genres
    if args.genre_slugs:
        allowed = set(args.genre_slugs)
        genres = [genre for genre in all_genres if genre.slug in allowed]
        print_progress(
            f"filtered genres to {len(genres)} selected entries: {sorted(allowed)}"
        )

    if not all_genres:
        raise SystemExit(f"No genres found for year {args.year}.")

    write_csv(
        output_root / "genres.csv",
        genre_rows(all_genres),
        ["Year", "Genre", "Genre Slug", "Release Date", "URL"],
    )

    if args.genres_only:
        print(f"Wrote {len(all_genres)} genres to {output_root / 'genres.csv'}")
        return

    if not genres:
        raise SystemExit(
            f"No matching genres found for year {args.year}: {args.genre_slugs}"
        )

    all_shops: list[Shop] = []
    unavailable_shops: list[UnavailableShop] = []
    combined_output_name = "selected.csv" if args.genre_slugs else "all.csv"
    unavailable_output_name = (
        "selected_unavailable.csv" if args.genre_slugs else "unavailable.csv"
    )
    total_genres = len(genres)
    for index, genre in enumerate(genres, start=1):
        print_progress(f"scraping genre {index}/{total_genres}: {genre.slug}")
        shops, genre_unavailable_shops = scrape_genre_shops(
            session,
            genre,
            args.throttle_seconds,
            max(1, args.workers),
        )
        all_shops.extend(shops)
        unavailable_shops.extend(genre_unavailable_shops)
        write_csv(
            output_root / "by_genre" / f"{genre.slug}.csv",
            shop_rows(shops),
            [
                "Name",
                "Address",
                "Description",
                "Website",
                "Tabelog Reservation URL",
                "Google Maps URL",
                "Latitude",
                "Longitude",
                "Year",
                "Genre",
                "Genre Slug",
                "Release Date",
            ],
        )
        print(f"Wrote {len(shops)} shops for {genre.slug}")

    write_csv(
        output_root / combined_output_name,
        shop_rows(all_shops),
        [
            "Name",
            "Address",
            "Description",
            "Website",
            "Tabelog Reservation URL",
            "Google Maps URL",
            "Latitude",
            "Longitude",
            "Year",
            "Genre",
            "Genre Slug",
            "Release Date",
        ],
    )
    print(f"Wrote {len(all_shops)} shops to {output_root / combined_output_name}")

    write_csv(
        output_root / unavailable_output_name,
        unavailable_shop_rows(unavailable_shops),
        [
            "Website",
            "Year",
            "Genre",
            "Genre Slug",
            "Release Date",
            "Reason",
            "Status Code",
            "Listed Name",
            "Listed Area",
        ],
    )
    print(
        f"Wrote {len(unavailable_shops)} unavailable shops to {output_root / unavailable_output_name}"
    )


if __name__ == "__main__":
    main()