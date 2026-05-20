from __future__ import annotations

from urllib.parse import quote


SHOP_DATA_OVERRIDES: dict[str, dict[str, str | float]] = {
    "https://tabelog.com/tokyo/A1307/A130703/13246316/": {
        "latitude": 35.658054,
        "longitude": 139.751663,
    },
    "https://tabelog.com/yamanashi/A1902/A190202/19012518/": {
        "latitude": 35.708889,
        "longitude": 138.446396,
    },
    "https://tabelog.com/yamaguchi/A3505/A350501/35009481/": {
        "latitude": 34.055725,
        "longitude": 131.806595,
    },
    "https://tabelog.com/aichi/A2301/A230103/23008421/": {
        "latitude": 35.179325,
        "longitude": 136.926056,
    },
    "https://tabelog.com/aichi/A2301/A230109/23063362/": {
        "latitude": 35.181438,
        "longitude": 136.90657,
    },
    "https://tabelog.com/tokyo/A1308/A130801/13118721/": {
        "latitude": 35.668591,
        "longitude": 139.74234,
    },
    "https://tabelog.com/tokyo/A1303/A130301/13259485/": {
        "latitude": 35.66367,
        "longitude": 139.697723,
    },
    "https://tabelog.com/tokyo/A1301/A130101/13030881/": {
        "latitude": 35.670601,
        "longitude": 139.772003,
    },
    "https://tabelog.com/tokyo/A1308/A130801/13002772/": {
        "latitude": 35.658054,
        "longitude": 139.751663,
    },
    "https://tabelog.com/tokyo/A1313/A131301/13178685/": {
        "latitude": 35.670601,
        "longitude": 139.772003,
    },
    "https://tabelog.com/kyoto/A2601/A260301/26006453/": {
        "latitude": 35.011669,
        "longitude": 135.768112,
    },
    "https://tabelog.com/tokyo/A1301/A130101/13016506/": {
        "latitude": 35.670601,
        "longitude": 139.772003,
    },
    "https://tabelog.com/tokyo/A1317/A131701/13216607/": {
        "latitude": 35.641479,
        "longitude": 139.698196,
    },
    "https://tabelog.com/osaka/A2701/A270201/27124954/": {
        "latitude": 34.69389,
        "longitude": 135.502228,
    },
    "https://tabelog.com/kyoto/A2601/A260201/26039693/": {
        "latitude": 35.009998,
        "longitude": 135.751389,
    },
    "https://tabelog.com/aichi/A2301/A230109/23066675/": {
        "latitude": 35.181438,
        "longitude": 136.90657,
    },
    "https://tabelog.com/tokyo/A1303/A130301/13175455/": {
        "website": "https://tabelog.com/tokyo/A1318/A131811/13249143/",
        "address": "東京都渋谷区西原3-23-1",
        "latitude": 35.6705902,
        "longitude": 139.6835137,
    },
    "https://tabelog.com/osaka/A2701/A270102/27088894/": {
        "latitude": 34.705555,
        "longitude": 135.509995,
    },
    "https://tabelog.com/osaka/A2701/A270101/27113322/": {
        "latitude": 34.697323,
        "longitude": 135.498657,
    },
    "https://tabelog.com/osaka/A2701/A270101/27125082/": {
        "latitude": 34.705555,
        "longitude": 135.509995,
    },
}


def build_google_maps_url(address: str, name: str) -> str:
    query = quote(" ".join(part for part in (name.strip(), address.strip()) if part))
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def apply_row_overrides(row: dict[str, str]) -> dict[str, str]:
    website = row.get("Website", "").strip()
    override = SHOP_DATA_OVERRIDES.get(website)
    if override is None:
        return row

    updated = dict(row)
    if "website" in override:
        updated["Website"] = str(override["website"])
    if "address" in override:
        updated["Address"] = str(override["address"])
    if "latitude" in override:
        updated["Latitude"] = f"{float(override['latitude']):.7f}"
    if "longitude" in override:
        updated["Longitude"] = f"{float(override['longitude']):.7f}"

    updated["Google Maps URL"] = build_google_maps_url(
        updated.get("Address", ""),
        updated.get("Name", ""),
    )
    return updated