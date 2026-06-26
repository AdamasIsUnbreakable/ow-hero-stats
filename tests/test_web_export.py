import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from overwatch_stats.audit import build_all_audit
from overwatch_stats.export_json import hero_slug
from overwatch_stats.normalize import normalize_hero
from overwatch_stats.parse_stats import COMPONENT_DAMAGE_WARNING
from overwatch_stats.web_export import (
    SCHEMA_VERSION,
    build_audit_summary,
    build_hero_detail,
    build_hero_index,
    build_quality_report,
    build_manifest,
    clean_display_text,
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

    def test_hero_detail_includes_raw_and_parsed_stats(self):
        detail = build_hero_detail(self.hero)
        abilities = {ability["name"]: ability for ability in detail["abilities"]}
        dynamite = abilities["Dynamite"]

        self.assertEqual(detail["schema_version"], SCHEMA_VERSION)
        self.assertEqual(detail["slug"], "ashe")
        self.assertEqual(dynamite["raw"]["damage"], "50 direct + 25 splash")
        self.assertEqual(dynamite["raw_display"]["damage"], "50 direct + 25 splash")
        self.assertEqual(dynamite["stats"]["cooldown"]["value"], 12)
        self.assertEqual(dynamite["stats"]["pspeed"]["field"], "pspeed")
        self.assertEqual(dynamite["stats"]["pspeed"]["label"], "Projectile Speed")
        self.assertEqual(dynamite["stats"]["pspeed"]["unit"], "meters_per_second")
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
        self.assertEqual(manifest["schema_version"], "1.2.0")
        self.assertEqual(manifest["hero_count"], 1)
        self.assertEqual(manifest["data_files"]["hero_index"], "heroes.index.json")
        self.assertEqual(manifest["data_files"]["audit_summary"], "audit-summary.json")
        self.assertEqual(manifest["data_files"]["quality_report"], "quality-report.json")
        self.assertEqual(manifest["data_files"]["hero_detail_dir"], "heroes/")

    def test_quality_report_counts_fixture_hero(self):
        report = build_quality_report([self.hero], generated_at="2026-06-25T23:00:00Z")

        self.assertEqual(report["schema_version"], SCHEMA_VERSION)
        self.assertEqual(report["summary"]["hero_count"], 1)
        self.assertEqual(report["summary"]["ability_count"], 2)
        self.assertGreater(report["summary"]["warning_count"], 0)
        self.assertEqual(report["summary"]["component_stat_count"], 1)
        self.assertEqual(report["heroes"][0]["name"], "Ashe")
        self.assertEqual(report["heroes"][0]["component_stat_count"], 1)
        self.assertIn("Ashe", report["coverage_flags"]["heroes_with_component_stats"])
        self.assertTrue(report["warnings"]["most_common"])

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
        self.assertEqual(quality["summary"]["component_stat_count"], 1)
        self.assertIn("Ashe", quality["coverage_flags"]["heroes_with_component_stats"])
        self.assertEqual(detail["name"], "Ashe")
        self.assertEqual(detail["abilities"][1]["stats"]["damage"]["value"], None)
        self.assertEqual(detail["abilities"][1]["stats"]["damage"]["components"][0]["label"], "direct")

    def test_clean_display_text_removes_html_but_keeps_original_separate(self):
        raw = '2 seconds<br><span class="tooltip" title="extra">5 seconds</span>'

        self.assertEqual(clean_display_text(raw), "2 seconds; 5 seconds")


if __name__ == "__main__":
    unittest.main()
