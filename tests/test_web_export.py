import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from overwatch_stats.audit import build_all_audit
from overwatch_stats.export_json import hero_slug
from overwatch_stats.normalize import normalize_hero
from overwatch_stats.parse_stats import COMPONENT_DAMAGE_WARNING
from overwatch_stats.overrides import HERO_OVERRIDES, build_ruleset_data
from overwatch_stats.web_export import (
    SCHEMA_VERSION,
    build_audit_summary,
    build_hero_detail,
    build_hero_index,
    build_quality_report,
    build_search_index,
    build_icon_quality,
    build_perk_quality,
    build_manifest,
    clean_display_text,
    display_unit,
    icon_asset_issue,
    write_web_data,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ashe_cargo_sample.json"


class WebExportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.hero = normalize_hero(self.fixture["hero"], self.fixture["abilities"])

    def test_slugs_are_stable(self):
        self.assertEqual(hero_slug("Ashe"), "ashe")
        self.assertEqual(hero_slug("Soldier: 76"), "soldier-76")
        self.assertEqual(hero_slug("D.Va"), "d-va")

    def test_hero_index_entry_is_lightweight(self):
        index = build_hero_index([self.hero])
        entry = index[0]

        self.assertEqual(entry["name"], "Ashe")
        self.assertEqual(entry["slug"], "ashe")
        self.assertEqual(entry["role"], "Damage")
        self.assertEqual(entry["sub_role"], "Sharpshooter")
        self.assertEqual(entry["health"]["health"], 250)
        self.assertEqual(entry["ability_count"], 2)
        self.assertGreaterEqual(entry["warning_count"], 1)
        self.assertIn("low", entry["confidence_counts"])
        self.assertEqual(entry["detail_path"], "heroes/ashe.json")
        self.assertNotIn("abilities", entry)
        self.assertNotIn("raw", entry)

    def test_search_index_contains_ability_perk_and_tag_metadata(self):
        index = build_search_index([self.hero])
        self.assertEqual(index[0]["slug"], "ashe")
        self.assertIn("The Viper", [ability["name"] for ability in index[0]["abilities"]])
        self.assertTrue(all("description" in ability and "tags" in ability for ability in index[0]["abilities"]))

    def test_hero_detail_includes_raw_and_parsed_stats(self):
        detail = build_hero_detail(self.hero)
        abilities = {ability["name"]: ability for ability in detail["abilities"]}
        dynamite = abilities["Dynamite"]

        self.assertEqual(detail["schema_version"], SCHEMA_VERSION)
        self.assertEqual(detail["slug"], "ashe")
        self.assertEqual(detail["abilities"][0]["ability_index"], 0)
        self.assertEqual(detail["abilities"][1]["ability_index"], 1)
        self.assertEqual(dynamite["raw"]["damage"], "50 direct + 25 splash")
        self.assertEqual(dynamite["raw_display"]["damage"], "50 direct + 25 splash")
        self.assertEqual(dynamite["stats"]["cooldown"]["value"], 12)
        self.assertEqual(dynamite["stats"]["pspeed"]["field"], "pspeed")
        self.assertEqual(dynamite["stats"]["pspeed"]["label"], "Projectile Speed")
        self.assertEqual(dynamite["stats"]["pspeed"]["unit"], "meters_per_second")
        self.assertEqual(dynamite["stats"]["pspeed"]["display_unit"], "m/s")
        self.assertEqual(dynamite["stats"]["cooldown"]["display_unit"], "s")
        self.assertIsNone(dynamite["stats"]["damage"]["value"])
        self.assertEqual(dynamite["stats"]["damage"]["raw"], "50 direct + 25 splash")
        self.assertEqual(dynamite["stats"]["damage"]["raw_display"], "50 direct + 25 splash")
        self.assertEqual(dynamite["stats"]["damage"]["confidence"], "medium")
        self.assertIn(COMPONENT_DAMAGE_WARNING, dynamite["stats"]["damage"]["warnings"])
        self.assertEqual(
            dynamite["stats"]["damage"]["components"],
            [
                {
                    "label": "direct",
                    "raw": "50 direct",
                    "raw_display": "50 direct",
                    "value": 50,
                    "min_value": None,
                    "max_value": None,
                    "unit": "damage",
                    "display_unit": "damage",
                    "warnings": [],
                    "notes": [],
                },
                {
                    "label": "splash",
                    "raw": "25 splash",
                    "raw_display": "25 splash",
                    "value": 25,
                    "min_value": None,
                    "max_value": None,
                    "unit": "damage",
                    "display_unit": "damage",
                    "warnings": [],
                    "notes": [],
                },
            ],
        )

        viper = abilities["The Viper"]
        self.assertEqual(viper["stats"]["damage_falloff_range"]["field"], "damage_falloff_range")
        self.assertEqual(viper["stats"]["damage_falloff_range"]["label"], "Damage Falloff Range")

    def test_hero_detail_audit_includes_warnings_by_ability(self):
        detail = build_hero_detail(self.hero)

        self.assertIn("warnings_by_ability", detail["audit"])
        self.assertIn("Dynamite", detail["audit"]["warnings_by_ability"])
        self.assertIn(
            f"damage: {COMPONENT_DAMAGE_WARNING}",
            detail["audit"]["warnings_by_ability"]["Dynamite"],
        )

    def test_manifest_contains_schema_version_and_paths(self):
        manifest = build_manifest(hero_count=1, generated_at="2026-06-25T23:00:00Z")

        self.assertEqual(manifest["schema_version"], SCHEMA_VERSION)
        self.assertEqual(manifest["schema_version"], "3.0.0")
        self.assertEqual(manifest["data_files"]["search_index"], "search.index.json")
        self.assertEqual(manifest["rulesets"]["default"], "5v5")
        self.assertEqual([item["id"] for item in manifest["rulesets"]["available"]], ["5v5", "6v6"])
        self.assertEqual(manifest["rulesets"]["available"][1]["status"], "partial")
        self.assertEqual(manifest["hero_count"], 1)
        self.assertEqual(manifest["data_files"]["hero_index"], "heroes.index.json")
        self.assertEqual(manifest["data_files"]["audit_summary"], "audit-summary.json")
        self.assertEqual(manifest["data_files"]["quality_report"], "quality-report.json")
        self.assertEqual(manifest["data_files"]["hero_detail_dir"], "heroes/")

    def test_override_layer_keeps_base_and_records_sparse_ruleset_patch(self):
        HERO_OVERRIDES["test-hero"] = [{
            "ruleset": "6v6",
            "path": ["health", "armor"],
            "value": 100,
            "reason": "Fixture correction",
            "source": "Fixture source",
        }]
        try:
            result = build_ruleset_data("test-hero", {"health": {"health": 250, "armor": 0}})
        finally:
            HERO_OVERRIDES.pop("test-hero")

        self.assertEqual(result["base"]["health"]["armor"], 0)
        self.assertEqual(result["ruleset_overrides"]["6v6"]["health"]["armor"], 100)
        self.assertEqual(result["overrides_applied"][0]["reason"], "Fixture correction")

    def test_override_layer_supports_ability_index_patch(self):
        base = {
            "abilities": [{
                "ability_index": 0,
                "name": "The Viper",
                "slot": "Primary Fire",
                "type": "Weapon",
                "stats": {"damage": {"value": 40}},
            }],
        }
        path = ["abilities", {"ability_index": 0}, "stats", "damage", "value"]
        HERO_OVERRIDES["ashe"] = [{
            "ruleset": "6v6",
            "path": path,
            "value": 45,
            "reason": "Fixture correction",
            "source": "Fixture source",
        }]
        try:
            result = build_ruleset_data("ashe", base)
        finally:
            HERO_OVERRIDES.pop("ashe")

        abilities = result["ruleset_overrides"]["6v6"]["abilities"]
        self.assertIsInstance(abilities, list)
        self.assertNotIn("abilities", abilities[0])
        self.assertEqual(abilities[0]["ability_index"], 0)
        self.assertEqual(abilities[0]["stats"]["damage"]["value"], 45)
        self.assertEqual(base["abilities"][0]["stats"]["damage"]["value"], 40)
        self.assertEqual(result["overrides_applied"], [{
            "ruleset": "6v6",
            "path": path,
            "value": 45,
            "reason": "Fixture correction",
            "source": "Fixture source",
        }])

    def test_override_layer_supports_name_slot_type_patch(self):
        selector = {"name": "The Viper", "slot": "Primary Fire", "type": "Weapon"}
        base = {"abilities": [{**selector, "ability_index": 0, "stats": {"damage": {"value": 40}}}]}
        HERO_OVERRIDES["ashe"] = [{
            "ruleset": "6v6",
            "path": ["abilities", selector, "stats", "damage", "value"],
            "value": 45,
            "reason": "Fixture correction",
            "source": "Fixture source",
        }]
        try:
            result = build_ruleset_data("ashe", base)
        finally:
            HERO_OVERRIDES.pop("ashe")

        patch = result["ruleset_overrides"]["6v6"]["abilities"][0]
        self.assertEqual({key: patch[key] for key in selector}, selector)
        self.assertEqual(patch["stats"]["damage"]["value"], 45)

    def test_default_ruleset_correction_updates_generated_base_without_mutating_source(self):
        source_base = {"health": {"health": 250, "armor": 0}}
        HERO_OVERRIDES["test-hero"] = [{
            "ruleset": "5v5",
            "path": ["health", "armor"],
            "value": 25,
            "reason": "Fixture correction",
            "source": "Fixture source",
        }]
        try:
            result = build_ruleset_data("test-hero", source_base)
        finally:
            HERO_OVERRIDES.pop("test-hero")

        self.assertEqual(source_base["health"]["armor"], 0)
        self.assertEqual(result["base"]["health"]["armor"], 25)
        self.assertEqual(result["overrides_applied"][0]["ruleset"], "5v5")

    def test_override_rejects_missing_or_ambiguous_ability_selector(self):
        base = {"abilities": [
            {"ability_index": 0, "name": "Pulse", "slot": "Primary"},
            {"ability_index": 1, "name": "Pulse", "slot": "Secondary"},
        ]}
        for selector, expected in [({"name": "Typo"}, "missing"), ({"name": "Pulse"}, "ambiguous")]:
            with self.subTest(selector=selector):
                HERO_OVERRIDES["test-hero"] = [{
                    "ruleset": "6v6",
                    "path": ["abilities", selector, "stats", "damage", "value"],
                    "value": 45,
                }]
                try:
                    with self.assertRaisesRegex(ValueError, expected):
                        build_ruleset_data("test-hero", base)
                finally:
                    HERO_OVERRIDES.pop("test-hero")

    def test_quality_report_counts_fixture_hero(self):
        report = build_quality_report([self.hero], generated_at="2026-06-25T23:00:00Z")

        self.assertEqual(report["schema_version"], SCHEMA_VERSION)
        self.assertEqual(report["summary"]["hero_count"], 1)
        self.assertEqual(report["summary"]["ability_count"], 2)
        self.assertGreater(report["summary"]["warning_count"], 0)
        self.assertEqual(report["summary"]["component_stat_count"], 2)
        self.assertEqual(report["heroes"][0]["name"], "Ashe")
        self.assertIn("ability_warning_count", report["heroes"][0])
        self.assertIn("stat_warning_count", report["heroes"][0])
        self.assertIn("empty_stat_count", report["heroes"][0])
        self.assertIn("unparsed_nonempty_stat_count", report["heroes"][0])
        self.assertGreater(report["heroes"][0]["empty_stat_count"], 0)
        self.assertEqual(report["heroes"][0]["unparsed_nonempty_stat_count"], 0)
        self.assertEqual(
            report["heroes"][0]["warning_count"],
            report["heroes"][0]["ability_warning_count"] + report["heroes"][0]["stat_warning_count"],
        )
        self.assertEqual(report["heroes"][0]["component_stat_count"], 2)
        self.assertIn("Ashe", report["coverage_flags"]["heroes_with_component_stats"])
        most_common_warnings = report["warnings"]["most_common"]
        self.assertTrue(most_common_warnings)
        self.assertTrue(any(warning["level"] == "stat" for warning in most_common_warnings))
        self.assertTrue(any(warning["field"] == "damage" for warning in most_common_warnings))
        self.assertIn("damage", report["fields"]["warnings_by_field"])
        self.assertIn("dps", report["fields"]["empty_by_field"])
        self.assertNotIn("reload_time", report["fields"]["unparsed_nonempty_by_field"])
        self.assertEqual(report["fields"]["unparsed_by_field"], report["fields"]["unparsed_nonempty_by_field"])
        self.assertIn("damage", report["fields"]["component_stats_by_field"])
        self.assertIn("meters_per_second", report["fields"]["machine_units_by_unit"])
        self.assertIn("m/s", report["fields"]["display_units_by_unit"])
        self.assertEqual(report["coverage_flags"]["stats_missing_display_unit"], [])
        self.assertEqual(report["icons"]["missing_icon_count"], 2)
        self.assertIn("Ashe", report["icons"]["heroes_with_missing_icons"])
        self.assertIn("Ashe", report["perks"]["heroes_with_unexpected_minor_count"])
        self.assertIn("Ashe", report["perks"]["heroes_with_unexpected_major_count"])
        self.assertEqual(
            report["asset_reports"]["ability_icon_coverage"],
            "assets/abilities/coverage-report.json",
        )

    def test_icon_quality_distinguishes_assets_from_fallbacks(self):
        hero = normalize_hero(
            {"Name": "Ashe", "Role": "Damage"},
            [
                {"ability_name": "Coach Gun", "ability_type": "Ability", "ability_image": ""},
                {"ability_name": "Dynamite", "ability_type": "Ability"},
                {"ability_name": "Initials", "ability_type": "Passive", "ability_image": "CR"},
                {"ability_name": "The Viper", "ability_type": "Weapon", "ability_image": "Ability-ashe1.png"},
            ],
        )

        report = build_icon_quality([hero])
        self.assertEqual(report["missing_icon_count"], 3)
        self.assertEqual(icon_asset_issue(""), "missing image asset")
        self.assertEqual(icon_asset_issue(None), "missing image asset")
        self.assertEqual(icon_asset_issue("CR"), "text-only fallback")
        self.assertIsNone(icon_asset_issue("assets/abilities/ashe/coach-gun.png"))

    def test_perk_quality_flags_only_unexpected_counts(self):
        hero = normalize_hero(
            {"Name": "Ashe", "Role": "Damage"},
            [
                {"ability_name": "Minor One", "ability_type": "Minor Perk"},
                {"ability_name": "Minor Two", "ability_type": "Minor Perk"},
                {"ability_name": "Major One", "ability_type": "Major Perk"},
                {"ability_name": "Major Two", "ability_type": "Major Perk"},
            ],
        )
        self.assertEqual(build_perk_quality([hero])["heroes_with_unexpected_minor_count"], {})
        self.assertEqual(build_perk_quality([hero])["heroes_with_unexpected_major_count"], {})

        hero.abilities.pop()
        report = build_perk_quality([hero])
        self.assertEqual(report["heroes_with_unexpected_major_count"]["Ashe"]["count"], 1)

        hero.abilities.extend(
            [
                normalize_hero({}, [{"ability_name": "Minor Three", "ability_type": "Minor Perk"}]).abilities[0],
                normalize_hero({}, [{"ability_name": "Major Three", "ability_type": "Major Perk"}]).abilities[0],
                normalize_hero({}, [{"ability_name": "Major Four", "ability_type": "Major Perk"}]).abilities[0],
            ]
        )
        report = build_perk_quality([hero])
        self.assertEqual(report["heroes_with_unexpected_minor_count"]["Ashe"]["count"], 3)
        self.assertEqual(report["heroes_with_unexpected_major_count"]["Ashe"]["count"], 3)

    def test_removed_perks_do_not_affect_current_perk_counts(self):
        rows = [
            {"ability_name": "Minor One", "ability_type": "Minor Perk"},
            {"ability_name": "Minor Two", "ability_type": "Minor Perk"},
            {"ability_name": "Major One", "ability_type": "Major Perk"},
            {"ability_name": "Major Two", "ability_type": "Major Perk"},
            {"ability_name": "Old Minor", "ability_type": "Minor Perk", "removed": True},
            {"ability_name": "Old Major", "ability_type": "Major Perk", "removed": "removed"},
        ]
        hero = normalize_hero({"Name": "Ashe", "Role": "Damage"}, rows)

        report = build_perk_quality([hero])
        self.assertNotIn("Ashe", report["heroes_with_unexpected_minor_count"])
        self.assertNotIn("Ashe", report["heroes_with_unexpected_major_count"])

        hero = normalize_hero(
            {"Name": "Ashe", "Role": "Damage"},
            rows + [{"ability_name": "Current Minor Three", "ability_type": "Minor Perk"}],
        )
        report = build_perk_quality([hero])
        self.assertEqual(report["heroes_with_unexpected_minor_count"]["Ashe"]["count"], 3)

    def test_write_web_data_outputs_valid_json_files(self):
        heroes, validation = build_all_audit(["Ashe"], [self.fixture["hero"]], self.fixture["abilities"])
        audit_summary = build_audit_summary(["Ashe"], [self.fixture["hero"]], heroes, self.fixture["abilities"], validation)

        with TemporaryDirectory() as temp_dir:
            paths = write_web_data(heroes, audit_summary, output_dir=temp_dir)

            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            index = json.loads(paths["hero_index"].read_text(encoding="utf-8"))
            audit = json.loads(paths["audit_summary"].read_text(encoding="utf-8"))
            quality = json.loads(paths["quality_report"].read_text(encoding="utf-8"))
            detail = json.loads((Path(temp_dir) / "heroes" / "ashe.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["data_files"]["hero_index"], "heroes.index.json")
        self.assertEqual(manifest["data_files"]["quality_report"], "quality-report.json")
        self.assertEqual(index[0]["detail_path"], "heroes/ashe.json")
        self.assertEqual(audit["scope"], "all")
        self.assertEqual(quality["schema_version"], SCHEMA_VERSION)
        self.assertEqual(quality["summary"]["hero_count"], 1)
        self.assertEqual(quality["summary"]["component_stat_count"], 2)
        self.assertEqual(
            quality["heroes"][0]["warning_count"],
            quality["heroes"][0]["ability_warning_count"] + quality["heroes"][0]["stat_warning_count"],
        )
        self.assertGreater(quality["heroes"][0]["empty_stat_count"], 0)
        self.assertEqual(quality["heroes"][0]["unparsed_nonempty_stat_count"], 0)
        self.assertIn("damage", quality["fields"]["warnings_by_field"])
        self.assertIn("dps", quality["fields"]["empty_by_field"])
        self.assertNotIn("reload_time", quality["fields"]["unparsed_nonempty_by_field"])
        self.assertIn("damage", quality["fields"]["component_stats_by_field"])
        self.assertIn("meters_per_second", quality["fields"]["machine_units_by_unit"])
        self.assertIn("m/s", quality["fields"]["display_units_by_unit"])
        self.assertEqual(quality["coverage_flags"]["stats_missing_display_unit"], [])
        self.assertIn("Ashe", quality["coverage_flags"]["heroes_with_component_stats"])
        self.assertEqual(detail["name"], "Ashe")
        self.assertEqual(detail["base"]["health"], detail["health"])
        self.assertEqual(detail["ruleset_overrides"]["6v6"], {})
        self.assertEqual(detail["overrides_applied"], [])
        self.assertEqual(detail["abilities"][0]["ability_index"], 0)
        self.assertEqual(detail["abilities"][1]["ability_index"], 1)
        self.assertEqual(detail["abilities"][1]["stats"]["damage"]["value"], None)
        self.assertEqual(detail["abilities"][1]["stats"]["damage"]["components"][0]["label"], "direct")
        self.assertEqual(detail["abilities"][1]["stats"]["damage"]["components"][0]["display_unit"], "damage")

    def test_clean_display_text_removes_html_but_keeps_original_separate(self):
        raw = '2 seconds<br><span class="tooltip" title="extra">5 seconds</span>'

        self.assertEqual(clean_display_text(raw), "2 seconds; 5 seconds")

    def test_clean_display_text_removes_wiki_icon_markup(self):
        raw = "[[File:Ability.png|40px|link=Projectile]] [[Projectile|Projectile]]"

        self.assertEqual(clean_display_text(raw), "Projectile")

    def test_display_unit_mapping(self):
        self.assertEqual(display_unit("fire_rate", "shots_per_second"), "shots/s")
        self.assertEqual(display_unit("pspeed", "meters_per_second"), "m/s")
        self.assertEqual(display_unit("dps", "per_second"), "damage/s")
        self.assertEqual(display_unit("hps", "per_second"), "healing/s")
        self.assertEqual(display_unit("fire_rate", "percent"), "%")
        self.assertEqual(display_unit("custom", "some_machine_unit"), "some machine unit")


if __name__ == "__main__":
    unittest.main()
