from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

WHATS_NEW_URL = "https://learn.microsoft.com/en-us/fabric/fundamentals/whats-new"
ARCHIVE_URL = "https://learn.microsoft.com/en-us/fabric/fundamentals/whats-new-archive"
FETCH_TIMEOUT_SECONDS = 30

DATA_FILE = Path(__file__).resolve().parents[1] / "docs" / "data" / "releases.json"


@dataclass
class FeatureItem:
    title: str
    status: str
    month_label: str | None
    category: str | None
    summary: str | None
    learn_more_url: str | None
    source_page: str
    source_section: str | None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_title(title: str) -> str:
    text = title.lower().strip()
    text = re.sub(r"\((generally available|ga|preview)\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(generally available|preview|ga)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def lifecycle_key(title: str) -> str:
    return normalize_title(title)


def normalize_url(raw_url: str | None, source_page: str) -> str | None:
    if not raw_url:
        return None
    url = raw_url.strip()
    if not url:
        return None
    return urljoin(source_page, url)


def extract_rows_from_table(table, source_page: str, section_title: str, default_status: str | None) -> list[FeatureItem]:
    rows: list[FeatureItem] = []
    for tr in table.select("tbody tr"):
        cols = tr.find_all("td")
        if not cols:
            continue

        month = None
        title = ""
        summary = ""
        url = None

        if len(cols) >= 3:
            month = cols[0].get_text(" ", strip=True) or None
            title = cols[1].get_text(" ", strip=True)
            summary = cols[2].get_text(" ", strip=True)
            link = cols[1].find("a") or cols[2].find("a") or tr.find("a")
            if link and link.get("href"):
                url = link.get("href")
        else:
            title = cols[0].get_text(" ", strip=True)
            summary = cols[1].get_text(" ", strip=True) if len(cols) > 1 else ""
            link = cols[0].find("a") or cols[-1].find("a") or tr.find("a")
            if link and link.get("href"):
                url = link.get("href")

        status = default_status
        if not status:
            lower_title = title.lower()
            if "preview" in lower_title:
                status = "Preview"
            elif "generally available" in lower_title or "(ga)" in lower_title or lower_title.endswith(" ga"):
                status = "GA"

        if status not in {"GA", "Preview"}:
            continue

        rows.append(
            FeatureItem(
                title=title,
                status=status,
                month_label=month,
                category=section_title,
                summary=summary,
                learn_more_url=normalize_url(url, source_page),
                source_page=source_page,
                source_section=section_title,
            )
        )

    return rows


def parse_features(html: str, source_page: str) -> list[FeatureItem]:
    soup = BeautifulSoup(html, "html.parser")
    features: list[FeatureItem] = []

    for heading in soup.find_all(["h2", "h3"]):
        section = heading.get_text(" ", strip=True)
        lower = section.lower()

        status = None
        if "features currently in preview" in lower:
            status = "Preview"
        elif "generally available features" in lower:
            status = "GA"

        table = heading.find_next("table")
        if table is None:
            continue

        features.extend(extract_rows_from_table(table, source_page, section, status))

    return features


def fetch_features() -> list[FeatureItem]:
    items: list[FeatureItem] = []
    for url in [WHATS_NEW_URL, ARCHIVE_URL]:
        response = requests.get(url, timeout=FETCH_TIMEOUT_SECONDS)
        response.raise_for_status()
        items.extend(parse_features(response.text, url))
    return items


def build_unique_key(item: FeatureItem) -> str:
    month = item.month_label or "none"
    return f"{item.source_page}|{month}|{item.status}|{lifecycle_key(item.title)}"


def load_existing_data() -> dict:
    if not DATA_FILE.exists():
        return {"last_updated_utc": None, "stats": {}, "items": []}

    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if "items" not in payload or not isinstance(payload["items"], list):
        payload["items"] = []
    return payload


def upsert_items(existing: dict, fetched_items: Iterable[FeatureItem]) -> tuple[int, int, int]:
    inserted = 0
    updated = 0
    unchanged = 0

    now = utc_now_iso()
    items = existing["items"]
    by_key = {item["unique_key"]: item for item in items if "unique_key" in item}

    for feature in fetched_items:
      unique_key = build_unique_key(feature)
      normalized = normalize_title(feature.title)
      life_key = lifecycle_key(feature.title)

      row = by_key.get(unique_key)
      if row is None:
          inserted += 1
          row = {
              "unique_key": unique_key,
              "title": feature.title,
              "normalized_title": normalized,
              "lifecycle_group_key": life_key,
              "status": feature.status,
              "month_label": feature.month_label,
              "category": feature.category,
              "summary": feature.summary,
              "learn_more_url": feature.learn_more_url,
              "source_page": feature.source_page,
              "source_section": feature.source_section,
              "is_active": True,
              "superseded_by_key": None,
              "first_seen_utc": now,
              "last_seen_utc": now,
              "updated_utc": now,
          }
          items.append(row)
          by_key[unique_key] = row
          continue

      changed = any(
          [
              row.get("title") != feature.title,
              row.get("status") != feature.status,
              row.get("month_label") != feature.month_label,
              row.get("category") != feature.category,
              row.get("summary") != feature.summary,
              row.get("learn_more_url") != feature.learn_more_url,
              row.get("source_section") != feature.source_section,
          ]
      )

      row["title"] = feature.title
      row["normalized_title"] = normalized
      row["lifecycle_group_key"] = life_key
      row["status"] = feature.status
      row["month_label"] = feature.month_label
      row["category"] = feature.category
      row["summary"] = feature.summary
      row["learn_more_url"] = feature.learn_more_url
      row["source_page"] = feature.source_page
      row["source_section"] = feature.source_section
      row["last_seen_utc"] = now
      row["updated_utc"] = now

      if changed:
          updated += 1
      else:
          unchanged += 1

    return inserted, updated, unchanged


def supersede_preview_rows(existing: dict) -> int:
    now = utc_now_iso()
    items = existing["items"]
    active_ga = {}

    for row in items:
        if row.get("status") == "GA" and row.get("is_active"):
            active_ga[row.get("lifecycle_group_key")] = row.get("unique_key")

    superseded = 0
    for row in items:
        if row.get("status") != "Preview":
            continue
        if not row.get("is_active"):
            continue

        ga_key = active_ga.get(row.get("lifecycle_group_key"))
        if ga_key:
            row["is_active"] = False
            row["superseded_by_key"] = ga_key
            row["updated_utc"] = now
            superseded += 1

    return superseded


def write_data_file(payload: dict) -> None:
    items = payload.get("items", [])

    def sort_key(item: dict):
        return (item.get("updated_utc") or "", item.get("title") or "")

    payload["items"] = sorted(items, key=sort_key, reverse=True)
    DATA_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    existing = load_existing_data()
    fetched = fetch_features()

    inserted, updated, unchanged = upsert_items(existing, fetched)
    superseded = supersede_preview_rows(existing)

    items = existing.get("items", [])
    active_items = sum(1 for item in items if item.get("is_active"))

    existing["last_updated_utc"] = utc_now_iso()
    existing["stats"] = {
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "superseded": superseded,
        "total_items": len(items),
        "active_items": active_items,
    }

    write_data_file(existing)

    print(
        "Refresh complete:",
        f"inserted={inserted}",
        f"updated={updated}",
        f"unchanged={unchanged}",
        f"superseded={superseded}",
        f"total={len(items)}",
        f"active={active_items}",
    )


if __name__ == "__main__":
    main()
