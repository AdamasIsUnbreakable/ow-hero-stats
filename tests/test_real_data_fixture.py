import json
import unittest
from pathlib import Path

from overwatch_stats.audit import non_empty_unparsed_fields, render_hero_audit, warnings_by_ability
from overwatch_stats.normalize import normalize_hero


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ashe_cargo_sample.json"


class RealDataFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.hero = normalize_hero(self.fixture["hero"], self.fixture["abilities"])

    def test_fixture_normalizes_representative_cargo_rows(self):
        self.assertEqual(self.hero.name, "Ashe")
        self.assertEqual(len(self.hero.abilities), 2)
        self.assertEqual(self.hero.abilities[0].raw["reload time"], self.fixture["abilities"][0]["reload time"])
        self.assertEqual(self.hero.abilities[0].parsed["ammo"].value, 12)
        self.assertEqual(self.hero.abilities[0].parsed["damage_falloff_range"].max_value, 40)

    def test_fixture_preserves_ambiguous_damage_with_warning(self):
        dynamite = self.hero.abilities[1]
        damage = dynamite.parsed["damage"]
        self.assertEqual(damage.raw, "50 direct + 25 splash")
        self.assertIsNone(damage.value)
        self.assertEqual(damage.confidence, "low")
        self.assertTrue(damage.warnings)
        self.assertIn("Dynamite", warnings_by_ability(self.hero.abilities))

    def test_fixture_audit_reports_unparsed_and_warning_sections(self):
        report = render_hero_audit(self.hero, len(self.fixture["abilities"]))
        self.assertIn("Hero audit: Ashe", report)
        self.assertIn("Non-empty raw fields left unparsed", report)
        self.assertIn("Parse warnings by ability", report)
        self.assertTrue(non_empty_unparsed_fields(self.hero.abilities))


if __name__ == "__main__":
    unittest.main()
