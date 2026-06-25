from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import HeroStats, to_plain_data


def hero_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown"


def hero_to_json(hero: HeroStats) -> str:
    return json.dumps(to_plain_data(hero), ensure_ascii=False, indent=2)


def write_hero(hero: HeroStats, output_dir: str | Path = "data/output") -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    path = output_path / f"{hero_slug(hero.name)}.json"
    path.write_text(hero_to_json(hero) + "\n", encoding="utf-8")
    return path


def write_all(heroes: list[HeroStats], output_dir: str | Path = "data/output") -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    path = output_path / "heroes.json"
    data: list[dict[str, Any]] = [to_plain_data(hero) for hero in heroes]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for hero in heroes:
        write_hero(hero, output_dir=output_path)
    return path
