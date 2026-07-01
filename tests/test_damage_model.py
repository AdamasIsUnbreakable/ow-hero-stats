import json
import subprocess
import unittest
from pathlib import Path


MODEL = Path(__file__).parents[1] / "site" / "src" / "damage-model.js"


class DamageModelTests(unittest.TestCase):
    def run_model(self, expression: str):
        script = f"require({json.dumps(str(MODEL))}); console.log(JSON.stringify({expression}));"
        result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
        return json.loads(result.stdout)

    def test_falloff_headshot_and_dps_share_one_evaluation(self):
        ability = {"stats": {"damage": {"min_value": 20, "max_value": 60, "components": []}, "damage_falloff_range": {"min_value": 10, "max_value": 30}, "fire_rate": {"value": 2}, "headshot_mod": {"value": 2}, "headshot": {"value": True}}}
        result = self.run_model(f"OWDamageModel.evaluate({{ruleset:'6v6', ability:{json.dumps(ability)}, distance:20, headshot:true}})")
        self.assertEqual(result["damage"], 80)
        self.assertEqual(result["dps"], 160)
        self.assertEqual(result["ruleset"], "6v6")

    def test_armor_rules(self):
        result = self.run_model("[OWDamageModel.damageToArmor(10, 'normal'), OWDamageModel.damageToArmor(10, 'beam')]")
        self.assertEqual(result, [5, 7])

    def test_normal_armor_exact_threshold_around_fourteen_damage(self):
        result = self.run_model(
            "[13, 14, 15].map(damage => OWDamageModel.damageToArmor(damage, 'normal'))"
        )
        self.assertEqual(result, [6.5, 7, 8])

    def test_low_and_high_normal_damage_armor_hits(self):
        result = self.run_model(
            "[OWDamageModel.damageToArmor(1, 'normal'), OWDamageModel.damageToArmor(100, 'normal')]"
        )
        self.assertEqual(result, [0.5, 93])

    def test_shot_overflow_uses_exact_normal_armor_inverse(self):
        ability = {"stats": {"damage": {"value": 20, "components": []}}}
        target = {"health": 11, "armor": 5, "shield": 0}
        result = self.run_model(
            f"OWDamageModel.shotsToKill({{ability:{json.dumps(ability)}, target:{json.dumps(target)}}})"
        )
        self.assertEqual(result["shots"], 2)

    def test_shield_armor_and_health_are_consumed_in_order(self):
        ability = {"stats": {"damage": {"value": 20, "components": []}}}
        target = {"health": 11, "armor": 5, "shield": 10}
        result = self.run_model(
            f"OWDamageModel.shotsToKill({{ability:{json.dumps(ability)}, target:{json.dumps(target)}}})"
        )
        self.assertEqual(result["shots"], 2)
        self.assertEqual(result["targetTotal"], 26)

    def test_beam_damage_breaks_armor_before_health(self):
        ability = {
            "shot_type": ["Beam"],
            "stats": {"damage": {"value": 10, "components": []}},
        }
        target = {"health": 10, "armor": 7, "shield": 0}
        result = self.run_model(
            f"OWDamageModel.shotsToKill({{ability:{json.dumps(ability)}, target:{json.dumps(target)}}})"
        )
        self.assertEqual(result["damageType"], "beam")
        self.assertEqual(result["shots"], 2)

    def test_target_without_armor_uses_raw_damage(self):
        ability = {"stats": {"damage": {"value": 40, "components": []}}}
        target = {"health": 100, "armor": 0, "shield": 0}
        result = self.run_model(
            f"OWDamageModel.shotsToKill({{ability:{json.dumps(ability)}, target:{json.dumps(target)}}})"
        )
        self.assertEqual(result["shots"], 3)

    def test_gameplay_note_mention_does_not_make_simple_damage_unsupported(self):
        ability = {
            "name": "Rocket Hammer",
            "raw_display": {"ability_details": "Charge interrupts this attack."},
            "stats": {"damage": {"value": 100, "components": []}},
        }
        result = self.run_model(f"OWDamageModel.classify({json.dumps(ability)})")
        self.assertTrue(result["supported"])

    def test_partial_falloff_refuses_damage_after_known_start(self):
        ability = {
            "stats": {
                "damage": {"value": 50, "components": []},
                "damage_falloff_range": {"min_value": 20, "max_value": 40},
            }
        }
        result = self.run_model(f"OWDamageModel.evaluate({{ability:{json.dumps(ability)}, distance:30}})")
        self.assertFalse(result["supported"])
        self.assertIn("not safely parsed", result["reason"])

    def test_armor_piercing_damage_is_not_given_normal_armor_math(self):
        ability = {
            "raw_display": {"ability_keywords": "armor piercing"},
            "stats": {"damage": {"value": 75, "components": []}},
        }
        result = self.run_model(f"OWDamageModel.classify({json.dumps(ability)})")
        self.assertTrue(result["supported"])
        self.assertEqual(result["damageType"], "armor_piercing")
        armor_result = self.run_model(
            f"OWDamageModel.shotsToKill({{ability:{json.dumps(ability)}, target:{{health:200, armor:50}}}})"
        )
        self.assertFalse(armor_result["supported"])
        self.assertIn("armor rule", armor_result["reason"])

    def test_complex_damage_is_refused(self):
        ability = {"stats": {"damage": {"value": None, "components": [{"label": "splash", "value": 50}]}}}
        result = self.run_model(f"OWDamageModel.classify({json.dumps(ability)})")
        self.assertFalse(result["supported"])
        self.assertIn("Multi-component", result["reason"])


if __name__ == "__main__":
    unittest.main()
