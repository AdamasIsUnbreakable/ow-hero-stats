import unittest

from overwatch_stats.audit import build_all_audit, render_all_audit


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


if __name__ == "__main__":
    unittest.main()
