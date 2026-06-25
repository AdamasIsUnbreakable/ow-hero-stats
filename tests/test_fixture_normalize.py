import json
import unittest
from pathlib import Path

from overwatch_stats.audit import hero_audit_summary
from overwatch_stats.normalize import normalize_hero
from overwatch_stats.parse_stats import COMPLEX_DAMAGE_WARNING


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ashe_cargo_sample.json"


class FixtureNormalizeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.hero = normalize_hero(self.fixture["hero"], self.fixture["abilities"])
        self.abilities = {ability.name: ability for ability in self.hero.abilities}

    def test_normalizes_ashe_fixture_identity_and_health(self):
        self.assertEqual(self.hero.name, "Ashe")
        self.assertEqual(self.hero.role, "Damage")
        self.assertEqual(self.hero.sub_role, "Sharpshooter")
        self.assertEqual(self.hero.health["health"], 250)
        self.assertGreaterEqual(len(self.hero.abilities), 2)

    def test_preserves_raw_values_and_parses_simple_viper_fields(self):
        viper = self.abilities["The Viper"]

        self.assertEqual(
            viper.raw["reload time"],
            "0.5 seconds (initial animation) <br/>+0.25 seconds per bullet",
        )
        self.assertEqual(viper.parsed["ammo"].value, 12)

        falloff = viper.parsed["damage_falloff_range"]
        self.assertEqual(falloff.min_value, 20)
        self.assertEqual(falloff.max_value, 40)
        self.assertEqual(falloff.unit, "meters")

    def test_preserves_raw_values_and_parses_simple_dynamite_fields(self):
        dynamite = self.abilities["Dynamite"]

        self.assertEqual(dynamite.raw["damage"], "50 direct + 25 splash")

        cooldown = dynamite.parsed["cooldown"]
        self.assertEqual(cooldown.value, 12)
        self.assertEqual(cooldown.unit, "seconds")

        duration = dynamite.parsed["duration"]
        self.assertEqual(duration.value, 5)
        self.assertEqual(duration.unit, "seconds")

        projectile_speed = dynamite.parsed["pspeed"]
        self.assertEqual(projectile_speed.value, 25)
        self.assertEqual(projectile_speed.unit, "meters_per_second")

    def test_dynamite_complex_damage_is_low_confidence_with_warning(self):
        dynamite = self.abilities["Dynamite"]
        damage = dynamite.parsed["damage"]

        self.assertIsNone(damage.value)
        self.assertEqual(damage.confidence, "low")
        self.assertIn(COMPLEX_DAMAGE_WARNING, damage.warnings)
        self.assertIn(f"damage: {COMPLEX_DAMAGE_WARNING}", dynamite.parse_warnings)

    def test_fixture_hero_audit_summary_includes_dynamite_warning(self):
        summary = hero_audit_summary(self.hero, ability_row_count=len(self.fixture["abilities"]))

        self.assertEqual(summary["scope"], "hero")
        self.assertEqual(summary["hero_name"], "Ashe")
        self.assertGreaterEqual(summary["confidence_counts"]["low"], 1)
        self.assertIn("Dynamite", summary["warnings_by_ability"])


if __name__ == "__main__":
    unittest.main()
