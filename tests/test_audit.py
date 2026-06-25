import unittest

from overwatch_stats.audit import all_audit_summary, build_all_audit, hero_audit_summary, render_all_audit
from overwatch_stats.normalize import normalize_hero


class AuditTests(unittest.TestCase):
    def test_all_audit_report_includes_source_counts_and_mismatches(self):
        playable = ["Ana", "Ashe"]
        character_rows = [
            {"Name": "Ana", "Role": "Support"},
            {"Name": "Extra Person", "Role": "Damage"},
        ]
        ability_rows = [
            {"hero name": "Ana", "ability name": "Biotic Rifle", "damage": "75"},
            {"hero name": "Training bot", "ability name": "Training Shot", "damage": "1"},
        ]

        heroes, validation = build_all_audit(playable, character_rows, ability_rows)
        report = render_all_audit(playable, character_rows, heroes, ability_rows, validation)

        self.assertIn("Playable heroes: 2", report)
        self.assertIn("Characters rows: 2", report)
        self.assertIn("Abilities hero groups: 2", report)
        self.assertIn("Heroes missing metadata (1):", report)
        self.assertIn("Heroes missing abilities (1):", report)
        self.assertIn("Extra Characters rows not in playable hero list (1):", report)
        self.assertIn("Ability hero names not in playable hero list (1):", report)

    def test_all_audit_summary_is_stable_json_shape(self):
        playable = ["Ana", "Ashe"]
        character_rows = [{"Name": "Ana", "Role": "Support"}]
        ability_rows = [{"hero name": "Ana", "ability name": "Biotic Rifle", "damage": "75"}]

        heroes, validation = build_all_audit(playable, character_rows, ability_rows)
        summary = all_audit_summary(playable, character_rows, heroes, ability_rows, validation)

        self.assertEqual(summary["scope"], "all")
        self.assertEqual(summary["totals"]["playable_heroes"], 2)
        self.assertEqual(summary["totals"]["character_rows"], 1)
        self.assertEqual(summary["totals"]["ability_hero_groups"], 1)
        self.assertEqual(summary["source_validation"]["heroes_missing_metadata"], ["Ashe"])
        self.assertEqual(summary["source_validation"]["heroes_missing_abilities"], ["Ashe"])
        self.assertIn("confidence_counts", summary)

    def test_hero_audit_summary_is_stable_json_shape(self):
        hero = normalize_hero(
            {"Name": "Ashe", "Role": "Damage", "SubRole": "Sharpshooter"},
            [{"hero name": "Ashe", "ability name": "Dynamite", "damage": "50 direct + 25 splash"}],
        )

        summary = hero_audit_summary(hero, ability_row_count=1)

        self.assertEqual(summary["scope"], "hero")
        self.assertEqual(summary["hero_name"], "Ashe")
        self.assertEqual(summary["ability_rows"], 1)
        self.assertEqual(summary["confidence_counts"]["low"], 1)
        self.assertIn("Dynamite", summary["warnings_by_ability"])


if __name__ == "__main__":
    unittest.main()
