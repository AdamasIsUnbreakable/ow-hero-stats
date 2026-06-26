from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_ENDPOINT = "https://overwatch.fandom.com/api.php"
USER_AGENT = "OWHeroStatsExporter/0.1 (local research tool; Cargo API)"


class FandomApiError(RuntimeError):
    pass


class FandomClient:
    def __init__(
        self,
        endpoint: str = API_ENDPOINT,
        cache_dir: str | Path = "data/cache",
        refresh: bool = False,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> None:
        self.endpoint = endpoint
        self.cache_dir = Path(cache_dir)
        self.refresh = refresh
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        import requests

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def cargo_query(
        self,
        tables: str,
        fields: str,
        where: str | None = None,
        order_by: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "action": "cargoquery",
            "format": "json",
            "tables": tables,
            "fields": fields,
            "limit": limit,
            "offset": offset,
        }
        if where:
            params["where"] = where
        if order_by:
            params["order_by"] = order_by
        payload = self._get_json(params)
        if "error" in payload:
            info = payload["error"].get("info", "Unknown API error")
            raise FandomApiError(info)
        return [row.get("title", row) for row in payload.get("cargoquery", [])]

    def get_hero_metadata(self, hero_name: str) -> dict[str, Any] | None:
        where = f"Name='{_escape_cargo_value(hero_name)}'"
        rows = self.cargo_query(
            tables="Characters",
            fields="Name,Role,SubRole,Health,Armor,Shield,Abilities",
            where=where,
            limit=1,
        )
        return rows[0] if rows else None

    def get_all_heroes(self) -> list[dict[str, Any]]:
        return self._query_all(
            tables="Characters",
            fields="Name,Role,SubRole,Health,Armor,Shield,Abilities",
            order_by="Name",
        )

    def get_hero_page_names(self) -> list[str]:
        params: dict[str, Any] = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": "Category:Heroes",
            "cmnamespace": 0,
            "cmlimit": 500,
        }
        payload = self._get_json(params)
        if "error" in payload:
            info = payload["error"].get("info", "Unknown API error")
            raise FandomApiError(info)
        names = [row["title"] for row in payload.get("query", {}).get("categorymembers", [])]
        return [name for name in names if name != "Heroes"]

    def get_hero_abilities(self, hero_name: str) -> list[dict[str, Any]]:
        where = f"hero_name='{_escape_cargo_value(hero_name)}'"
        return self.cargo_query(
            tables="Abilities",
            fields=ABILITY_FIELDS,
            where=where,
            order_by="ability_key,ability_name",
            limit=500,
        )

    def get_all_abilities(self) -> list[dict[str, Any]]:
        return self._query_all(
            tables="Abilities",
            fields=ABILITY_FIELDS,
            order_by="hero_name,ability_key,ability_name",
        )

    def _query_all(self, tables: str, fields: str, order_by: str | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        limit = 500
        while True:
            chunk = self.cargo_query(tables=tables, fields=fields, order_by=order_by, limit=limit, offset=offset)
            rows.extend(chunk)
            if len(chunk) < limit:
                return rows
            offset += limit

    def _get_json(self, params: dict[str, Any]) -> dict[str, Any]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_path(params)
        if cache_path.exists() and not self.refresh:
            with cache_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)["raw_response"]

        for attempt in range(self.max_retries + 1):
            response = self.session.get(self.endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            if not _is_rate_limit_error(payload) or attempt >= self.max_retries:
                break
            time.sleep(self.retry_delay * (attempt + 1))
        if "error" in payload:
            return payload
        cache_record = {
            "hero_name": _hero_from_where(params.get("where")),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_endpoint": self.endpoint,
            "query_params": params,
            "raw_response": payload,
        }
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(cache_record, handle, ensure_ascii=False, indent=2)
        return payload

    def _cache_path(self, params: dict[str, Any]) -> Path:
        query = json.dumps(params, sort_keys=True, ensure_ascii=True)
        digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
        action = params.get("tables", "query").lower()
        return self.cache_dir / f"{action}-{digest}.json"


ABILITY_FIELDS = ",".join(
    [
        "hero_name",
        "ability_name",
        "ability_image",
        "ability_key",
        "removed",
        "ability_type",
        "shot_type",
        "official_description",
        "damage",
        "damage_falloff_range",
        "headshot",
        "headshot_mod",
        "heal",
        "cooldown",
        "charges",
        "fire_rate",
        "ammo",
        "reload_time",
        "cast_time",
        "duration",
        "pspeed",
        "pradius",
        "spread",
        "radius",
        "range_distance",
        "dps",
        "hps",
        "ability_keywords",
        "ability_details",
    ]
)


def _escape_cargo_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _hero_from_where(where: object) -> str | None:
    if not isinstance(where, str):
        return None
    for key in ("hero_name", "Name"):
        marker = f"{key}='"
        if marker in where:
            return where.split(marker, 1)[1].split("'", 1)[0]
    return None


def _is_rate_limit_error(payload: dict[str, Any]) -> bool:
    error = payload.get("error")
    if not isinstance(error, dict):
        return False
    code = str(error.get("code", "")).lower()
    info = str(error.get("info", "")).lower()
    return "rate" in code or "rate limit" in info
