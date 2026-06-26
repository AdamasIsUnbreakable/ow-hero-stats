from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .export_json import hero_slug
from .fandom_client import API_ENDPOINT, USER_AGENT


HERO_ICON_CATEGORY = "Category:Overwatch_2_hero_icons"
DEFAULT_HERO_IMAGE_DIR = Path("site/public/assets/heroes")
PORTRAIT_TITLE_RE = re.compile(r"^File:(?P<hero>.+?) Hero\.(?P<ext>png|webp|jpg|jpeg)$", re.IGNORECASE)


@dataclass(frozen=True)
class ImageInfo:
    source_url: str
    width: int | None
    height: int | None
    mime: str | None
    size: int | None


def hero_name_from_file_title(title: str) -> str | None:
    normalized = title.strip()
    if normalized.casefold().startswith("file:icon-"):
        return None
    match = PORTRAIT_TITLE_RE.match(normalized)
    if not match:
        return None
    return match.group("hero").strip()


def portrait_slug_from_file_title(title: str) -> str | None:
    hero_name = hero_name_from_file_title(title)
    return hero_slug(hero_name) if hero_name else None


def filter_portrait_titles(titles: list[str]) -> list[str]:
    return [title for title in titles if hero_name_from_file_title(title)]


def build_manifest_entry(title: str, info: ImageInfo, output_dir: str | Path = DEFAULT_HERO_IMAGE_DIR) -> dict[str, Any]:
    hero_name = hero_name_from_file_title(title)
    slug = portrait_slug_from_file_title(title)
    if not hero_name or not slug:
        raise ValueError(f"Not a hero portrait title: {title}")

    local_path = _public_asset_path(Path(output_dir), slug, _extension_from_title(title))
    return {
        "hero_slug": slug,
        "hero_name": hero_name,
        "file_title": title,
        "local_path": local_path,
        "source_url": info.source_url,
        "width": info.width,
        "height": info.height,
        "mime": info.mime,
        "size": info.size,
    }


def download_hero_portraits(
    output_dir: str | Path = DEFAULT_HERO_IMAGE_DIR,
    refresh: bool = False,
    endpoint: str = API_ENDPOINT,
) -> dict[str, Any]:
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    category_titles = fetch_category_file_titles(session, endpoint=endpoint)
    selected_titles = filter_portrait_titles(category_titles)
    image_info = fetch_image_info(selected_titles, session, endpoint=endpoint)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    downloaded_count = 0
    skipped_existing_count = 0
    failed: list[dict[str, str]] = []
    entries: list[dict[str, Any]] = []

    for title in selected_titles:
        info = image_info.get(title)
        if not info:
            failed.append({"file_title": title, "error": "No imageinfo URL returned by Fandom API."})
            continue

        slug = portrait_slug_from_file_title(title)
        if not slug:
            continue
        target_path = output_path / f"{slug}{_extension_from_title(title)}"

        if target_path.exists() and not refresh:
            skipped_existing_count += 1
        else:
            try:
                _download_file(session, info.source_url, target_path)
                downloaded_count += 1
            except Exception as exc:  # noqa: BLE001 - keep downloading the rest and report per-file failures.
                failed.append({"file_title": title, "error": str(exc)})
                continue

        entries.append(build_manifest_entry(title, info, output_path))

    entries.sort(key=lambda entry: (entry["hero_name"].casefold(), entry["hero_slug"]))
    manifest_path = output_path / "manifest.json"
    manifest_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "category_file_count": len(category_titles),
        "selected_count": len(selected_titles),
        "downloaded_count": downloaded_count,
        "skipped_existing_count": skipped_existing_count,
        "failed_count": len(failed),
        "failed": failed,
        "manifest_path": manifest_path,
        "entries": entries,
    }


def fetch_category_file_titles(session: Any, endpoint: str = API_ENDPOINT) -> list[str]:
    titles: list[str] = []
    params: dict[str, Any] = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": HERO_ICON_CATEGORY,
        "cmtype": "file",
        "cmlimit": "max",
    }

    while True:
        payload = _get_json(session, endpoint, params)
        titles.extend(row["title"] for row in payload.get("query", {}).get("categorymembers", []))
        continuation = payload.get("continue")
        if not continuation:
            return titles
        params.update(continuation)


def fetch_image_info(titles: list[str], session: Any, endpoint: str = API_ENDPOINT) -> dict[str, ImageInfo]:
    image_info: dict[str, ImageInfo] = {}
    for chunk in _chunks(titles, 50):
        payload = _get_json(
            session,
            endpoint,
            {
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "iiprop": "url|size|mime",
                "titles": "|".join(chunk),
            },
        )
        for page in payload.get("query", {}).get("pages", {}).values():
            title = page.get("title")
            info_rows = page.get("imageinfo") or []
            if not title or not info_rows:
                continue
            info = info_rows[0]
            source_url = info.get("url")
            if not source_url:
                continue
            image_info[title] = ImageInfo(
                source_url=source_url,
                width=info.get("width"),
                height=info.get("height"),
                mime=info.get("mime"),
                size=info.get("size"),
            )
    return image_info


def _download_file(session: Any, url: str, path: Path) -> None:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    path.write_bytes(response.content)


def _get_json(session: Any, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    response = session.get(endpoint, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        info = payload["error"].get("info", "Unknown Fandom API error")
        raise RuntimeError(info)
    return payload


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _extension_from_title(title: str) -> str:
    suffix = Path(title).suffix.lower()
    return ".jpg" if suffix == ".jpeg" else suffix


def _public_asset_path(output_dir: Path, slug: str, extension: str) -> str:
    normalized = output_dir.as_posix().rstrip("/")
    marker = "site/public/"
    if normalized.startswith(marker):
        return f"{normalized.removeprefix(marker)}/{slug}{extension}"
    return f"assets/heroes/{slug}{extension}"
