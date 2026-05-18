from __future__ import annotations

import argparse
import csv
from pathlib import Path


PREFECTURE_TO_REGION = {
    "北海道": "tohoku_hokkaido",
    "青森県": "tohoku_hokkaido",
    "岩手県": "tohoku_hokkaido",
    "宮城県": "tohoku_hokkaido",
    "秋田県": "tohoku_hokkaido",
    "山形県": "tohoku_hokkaido",
    "福島県": "tohoku_hokkaido",
    "茨城県": "kanto",
    "栃木県": "kanto",
    "群馬県": "kanto",
    "埼玉県": "kanto",
    "千葉県": "kanto",
    "東京都": "kanto",
    "神奈川県": "kanto",
    "新潟県": "chubu",
    "富山県": "chubu",
    "石川県": "chubu",
    "福井県": "chubu",
    "山梨県": "chubu",
    "長野県": "chubu",
    "岐阜県": "chubu",
    "静岡県": "chubu",
    "愛知県": "chubu",
    "三重県": "chubu",
    "滋賀県": "kansai",
    "京都府": "kansai",
    "大阪府": "kansai",
    "兵庫県": "kansai",
    "奈良県": "kansai",
    "和歌山県": "kansai",
    "鳥取県": "chugoku_shikoku_kyushu",
    "島根県": "chugoku_shikoku_kyushu",
    "岡山県": "chugoku_shikoku_kyushu",
    "広島県": "chugoku_shikoku_kyushu",
    "山口県": "chugoku_shikoku_kyushu",
    "徳島県": "chugoku_shikoku_kyushu",
    "香川県": "chugoku_shikoku_kyushu",
    "愛媛県": "chugoku_shikoku_kyushu",
    "高知県": "chugoku_shikoku_kyushu",
    "福岡県": "chugoku_shikoku_kyushu",
    "佐賀県": "chugoku_shikoku_kyushu",
    "長崎県": "chugoku_shikoku_kyushu",
    "熊本県": "chugoku_shikoku_kyushu",
    "大分県": "chugoku_shikoku_kyushu",
    "宮崎県": "chugoku_shikoku_kyushu",
    "鹿児島県": "chugoku_shikoku_kyushu",
    "沖縄県": "chugoku_shikoku_kyushu",
}

REGION_LABELS = {
    "tohoku_hokkaido": "東北北海道",
    "kanto": "関東",
    "chubu": "中部",
    "kansai": "関西",
    "chugoku_shikoku_kyushu": "中国四国九州",
    "unknown": "未分類",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--input-dir", default="data")
    return parser.parse_args()


def extract_prefecture(address: str) -> str | None:
    for prefecture in PREFECTURE_TO_REGION:
        if address.startswith(prefecture):
            return prefecture
    return None


def main() -> None:
    args = parse_args()
    year_dir = Path(args.input_dir) / str(args.year)
    by_genre_dir = year_dir / "by_genre"
    by_region_dir = year_dir / "by_region"
    all_path = year_dir / "all.csv"

    source_paths = sorted(by_genre_dir.glob("*.csv"))
    if not source_paths:
        raise SystemExit(f"No genre CSV files found in {by_genre_dir}")

    all_rows: list[dict[str, str]] = []
    region_rows: dict[str, list[dict[str, str]]] = {
        slug: [] for slug in REGION_LABELS
    }
    fieldnames: list[str] | None = None

    for genre_path in source_paths:
        with genre_path.open("r", encoding="utf-8", newline="") as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise SystemExit(f"No CSV header found in {genre_path}")
            if fieldnames is None:
                fieldnames = reader.fieldnames

            for row in reader:
                all_rows.append(row)
                prefecture = extract_prefecture(row.get("Address", ""))
                region_slug = (
                    PREFECTURE_TO_REGION[prefecture]
                    if prefecture is not None
                    else "unknown"
                )
                region_rows[region_slug].append(row)

    if fieldnames is None:
        raise SystemExit(f"No CSV header found in {by_genre_dir}")

    by_region_dir.mkdir(parents=True, exist_ok=True)

    with all_path.open("w", encoding="utf-8", newline="") as all_file:
        writer = csv.DictWriter(all_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    for region_slug, rows in region_rows.items():
        target_path = by_region_dir / f"{region_slug}.csv"
        if not rows:
            if target_path.exists():
                target_path.unlink()
            print(
                f"Skipped empty region output {target_path}"
                f" ({REGION_LABELS[region_slug]})"
            )
            continue
        with target_path.open("w", encoding="utf-8", newline="") as target_file:
            writer = csv.DictWriter(target_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(
            f"Wrote {len(rows)} rows to {target_path}"
            f" ({REGION_LABELS[region_slug]})"
        )

    print(f"Wrote {len(all_rows)} rows to {all_path}")


if __name__ == "__main__":
    main()