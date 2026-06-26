from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .export_json import hero_slug
from .fandom_client import API_ENDPOINT, USER_AGENT


HERO_ICON_CATEGORY = "Category:Overwatch_2_hero_icons"
ABILITY_ICON_CATEGORY = "Category:Ability_icons"
DEFAULT_HERO_IMAGE_DIR = Path("site/public/assets/heroes")
DEFAULT_ABILITY_IMAGE_DIR = Path("site/public/assets/abilities")
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


def ability_icon_key_from_file_title(title: str) -> str | None:
    stem = _file_stem(title)
    if stem is None:
        return None
    cleaned = re.sub(r"^(?:icon[-_. ]*)?ability[-_. ]*", "", stem, flags=re.IGNORECASE)
    cleaned = re.sub(r"^perk[-_. ]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^passive[-_. ]*", "", cleaned, flags=re.IGNORECASE)
    return _match_key(cleaned)


def ability_match_key(name: str) -> str:
    return _match_key(name)


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


def build_ability_manifest_entry(
    title: str,
    info: ImageInfo,
    ability: dict[str, str],
    output_dir: str | Path = DEFAULT_ABILITY_IMAGE_DIR,
) -> dict[str, Any]:
    extension = _extension_from_title(title)
    hero_slug_value = ability["hero_slug"]
    ability_slug = hero_slug(ability["ability_name"])
    local_path = _public_asset_path(Path(output_dir), f"{hero_slug_value}/{ability_slug}", extension)
    return {
        "hero_slug": hero_slug_value,
        "hero_name": ability["hero_name"],
        "ability_name": ability["ability_name"],
        "ability_slug": ability_slug,
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


def download_ability_icons(
    heroes_data_dir: str | Path = "site/public/data/v1/heroes",
    output_dir: str | Path = DEFAULT_ABILITY_IMAGE_DIR,
    refresh: bool = False,
    endpoint: str = API_ENDPOINT,
) -> dict[str, Any]:
    import requests

    abilities_by_hero = _load_needed_abilities(Path(heroes_data_dir))
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    parent_members = fetch_category_members(session, ABILITY_ICON_CATEGORY, endpoint=endpoint)
    hero_categories = {
        member["title"]
        for member in parent_members
        if member.get("ns") == 14 and _hero_from_ability_category(member["title"]) in abilities_by_hero
    }
    generic_titles = [member["title"] for member in parent_members if member.get("ns") == 6]

    category_file_count = len(generic_titles)
    titles_by_hero: dict[str, list[str]] = {}
    for category_title in sorted(hero_categories):
        hero_key = _hero_from_ability_category(category_title)
        if not hero_key:
            continue
        titles = fetch_category_file_titles(session, category_title, endpoint=endpoint)
        titles_by_hero[hero_key] = titles
        category_file_count += len(titles)

    matches = match_ability_icon_titles(abilities_by_hero, titles_by_hero, generic_titles)
    image_info = fetch_image_info([match["file_title"] for match in matches], session, endpoint=endpoint)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    downloaded_count = 0
    skipped_existing_count = 0
    failed: list[dict[str, str]] = []
    entries: list[dict[str, Any]] = []

    for match in matches:
        title = match["file_title"]
        info = image_info.get(title)
        if not info:
            failed.append({"file_title": title, "error": "No imageinfo URL returned by Fandom API."})
            continue

        hero_dir = output_path / match["hero_slug"]
        hero_dir.mkdir(parents=True, exist_ok=True)
        target_path = hero_dir / f"{hero_slug(match['ability_name'])}{_extension_from_title(title)}"

        if target_path.exists() and not refresh:
            skipped_existing_count += 1
        else:
            try:
                _download_file(session, info.source_url, target_path)
                downloaded_count += 1
            except Exception as exc:  # noqa: BLE001 - keep downloading the rest and report per-file failures.
                failed.append({"file_title": title, "error": str(exc)})
                continue

        entries.append(build_ability_manifest_entry(title, info, match, output_path))

    entries.sort(key=lambda entry: (entry["hero_name"].casefold(), entry["ability_name"].casefold()))
    manifest_path = output_path / "manifest.json"
    manifest_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "category_file_count": category_file_count,
        "hero_category_count": len(hero_categories),
        "needed_ability_count": sum(len(abilities) for abilities in abilities_by_hero.values()),
        "selected_count": len(matches),
        "downloaded_count": downloaded_count,
        "skipped_existing_count": skipped_existing_count,
        "failed_count": len(failed),
        "failed": failed,
        "manifest_path": manifest_path,
        "entries": entries,
    }


def match_ability_icon_titles(
    abilities_by_hero: dict[str, list[dict[str, str]]],
    titles_by_hero: dict[str, list[str]],
    generic_titles: list[str] | None = None,
) -> list[dict[str, str]]:
    generic_titles = generic_titles or []
    matches: list[dict[str, str]] = []
    generic_by_key = _titles_by_icon_key(generic_titles)

    for hero_key, abilities in abilities_by_hero.items():
        hero_titles = titles_by_hero.get(hero_key, [])
        titles_by_key = _titles_by_icon_key(hero_titles)
        matched_ability_ids: set[int] = set()
        used_titles: set[str] = set()
        for ability in abilities:
            key = ability_match_key(ability["ability_name"])
            title = titles_by_key.get(key) or generic_by_key.get(key)
            if not title:
                continue
            matches.append({**ability, "file_title": title})
            matched_ability_ids.add(id(ability))
            used_titles.add(title)

        secondary_title = _secondary_fire_icon_title(hero_key, hero_titles, used_titles)
        if secondary_title:
            secondary_ability = next(
                (
                    ability
                    for ability in abilities
                    if id(ability) not in matched_ability_ids
                    and _ability_slot_priority(ability) == 1
                ),
                None,
            )
            if secondary_ability:
                matches.append({**secondary_ability, "file_title": secondary_title})
                matched_ability_ids.add(id(secondary_ability))
                used_titles.add(secondary_title)

        numbered_titles = _numbered_ability_icon_titles(hero_key, hero_titles, used_titles)
        if numbered_titles:
            unmatched = [
                ability
                for ability in abilities
                if id(ability) not in matched_ability_ids and not _is_perk_ability(ability)
            ]
            unmatched.sort(key=_ability_slot_priority)
            for ability, title in zip(unmatched, numbered_titles, strict=False):
                matches.append({**ability, "file_title": title})
                matched_ability_ids.add(id(ability))
                used_titles.add(title)
    return matches


def fetch_category_file_titles(session: Any, category_title: str = HERO_ICON_CATEGORY, endpoint: str = API_ENDPOINT) -> list[str]:
    return [
        member["title"]
        for member in fetch_category_members(session, category_title, endpoint=endpoint, cmtype="file")
        if member.get("title")
    ]


def fetch_category_members(
    session: Any,
    category_title: str,
    endpoint: str = API_ENDPOINT,
    cmtype: str | None = None,
) -> list[dict[str, Any]]:
    titles: list[str] = []
    params: dict[str, Any] = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": category_title,
        "cmlimit": "max",
    }
    if cmtype:
        params["cmtype"] = cmtype

    while True:
        payload = _get_json(session, endpoint, params)
        titles.extend(payload.get("query", {}).get("categorymembers", []))
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
    return f"assets/{output_dir.name}/{slug}{extension}"


def _load_needed_abilities(heroes_data_dir: Path) -> dict[str, list[dict[str, str]]]:
    abilities_by_hero: dict[str, list[dict[str, str]]] = {}
    for path in sorted(heroes_data_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        hero_slug_value = payload["slug"]
        abilities_by_hero[hero_slug_value] = [
            {
                "hero_slug": hero_slug_value,
                "hero_name": payload["name"],
                "ability_name": ability["name"],
                "slot": ability.get("slot") or "",
                "type": ability.get("type") or "",
            }
            for ability in payload.get("abilities", [])
            if ability.get("name")
        ]
    return abilities_by_hero


def _numbered_ability_icon_titles(hero_key: str, titles: list[str], used_titles: set[str]) -> list[str]:
    numbered: list[tuple[int, str]] = []
    pattern = re.compile(rf"^File:Ability[-_. ]*{re.escape(hero_key)}(?P<number>\d+)\.", re.IGNORECASE)
    for title in titles:
        if title in used_titles:
            continue
        match = pattern.match(title)
        if match:
            numbered.append((int(match.group("number")), title))
    return [title for _, title in sorted(numbered)]


def _secondary_fire_icon_title(hero_key: str, titles: list[str], used_titles: set[str]) -> str | None:
    hero_key_compact = ability_match_key(hero_key)
    for title in titles:
        if title in used_titles:
            continue
        key = ability_icon_key_from_file_title(title) or ""
        if key.startswith("zoom") and hero_key_compact in key and key.endswith("secondary"):
            return title
    return None


def _is_perk_ability(ability: dict[str, str]) -> bool:
    return "perk" in ability.get("type", "").casefold()


def _ability_slot_priority(ability: dict[str, str]) -> int:
    slot = ability.get("slot", "").casefold()
    ability_type = ability.get("type", "").casefold()
    if "primary fire" in slot:
        return 0
    if "secondary fire" in slot:
        return 1
    if "ability 1" in slot:
        return 2
    if "ability 2" in slot:
        return 3
    if "ability 3" in slot:
        return 4
    if "ultimate" in slot or "ultimate" in ability_type:
        return 5
    if "passive" in slot or "passive" in ability_type:
        return 6
    return 7


def _titles_by_icon_key(titles: list[str]) -> dict[str, str]:
    by_key: dict[str, str] = {}
    for title in titles:
        key = ability_icon_key_from_file_title(title)
        if key:
            by_key.setdefault(key, title)
    return by_key


def _hero_from_ability_category(title: str) -> str | None:
    match = re.fullmatch(r"Category:(?P<hero>.+?) ability icons", title, re.IGNORECASE)
    if not match:
        return None
    return hero_slug(match.group("hero"))


def _file_stem(title: str) -> str | None:
    if not title.casefold().startswith("file:"):
        return None
    return Path(title.split(":", 1)[1]).stem


def _match_key(value: str) -> str:
    normalized = value.casefold().replace("&", "and")
    normalized = re.sub(r"\(.*?\)", "", normalized)
    normalized = normalized.replace("'s", "s")
    return re.sub(r"[^a-z0-9]+", "", normalized)
