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
        result = self.run_model(f"OWDamageModel.evaluate({{ruleset:'5v5', ability:{json.dumps(ability)}, distance:20, headshot:true}})")
        self.assertEqual(result["damage"], 80)
        self.assertEqual(result["dps"], 160)
        self.assertEqual(result["ruleset"], "5v5")

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
        ability = {"stats": {"damage": {"value": None, "components": [{"label": "stage one", "value": 50}]}}}
        result = self.run_model(f"OWDamageModel.classify({json.dumps(ability)})")
        self.assertFalse(result["supported"])
        self.assertIn("Multi-component", result["reason"])

    def test_vendetta_complex_entries_expose_stage_selection(self):
        fang = {"name": "Palatine Fang", "type": "Weapon", "stats": {"damage": {"components": [{"label": "swing", "value": 45}, {"label": "overhead strike", "value": 120}]}}}
        blade = {"name": "Sundering Blade", "type": "Ability", "stats": {"damage": {"components": [{"label": "direct/indirect stage 1", "value": 100, "raw_display": "100/50 (direct/indirect stage 1)"}]}}}
        result = self.run_model(
            f"[{json.dumps(fang)},{json.dumps(blade)}].map(ability=>OWDamageModel.classify(ability))"
        )
        self.assertTrue(all(item["supported"] for item in result))
        self.assertTrue(all(item["kind"] == "staged" for item in result))
        self.assertEqual(result[0]["controls"], ["stage"])
        self.assertEqual(
            [(stage["label"], stage["damage"]) for stage in result[1]["stages"]],
            [("Stage 1 (direct)", 100), ("Stage 1 (indirect)", 50)],
        )

    def test_repeatable_weapon_calculates_shots_without_per_shot_events(self):
        weapon = {"type": "Weapon", "slot": "primary fire", "stats": {"damage": {"value": 40, "components": []}}}
        result = self.run_model(
            f"OWDamageModel.calculateCombo({{weapon:{json.dumps(weapon)}, target:{{health:100}}}})"
        )
        self.assertEqual(result["weaponShots"], 3)
        model = self.run_model(f"OWDamageModel.classify({json.dumps(weapon)})")
        self.assertEqual(model["category"], "repeatable")
        self.assertIsNone(model["useCount"])

    def test_limited_ability_combo_reduces_remaining_weapon_shots(self):
        weapon = {"type": "Weapon", "stats": {"damage": {"value": 40, "components": []}}}
        ability = {"type": "Ability", "name": "Burst", "stats": {"damage": {"value": 50, "components": []}}}
        expression = (
            "OWDamageModel.calculateCombo({"
            f"weapon:{json.dumps(weapon)}, abilities:[{{ability:{json.dumps(ability)},label:'Burst'}}],"
            "target:{health:100}})"
        )
        result = self.run_model(expression)
        self.assertEqual(result["comboDamage"], 50)
        self.assertEqual(result["remainingAfterCombo"], 50)
        self.assertEqual(result["weaponShots"], 2)
        self.assertEqual(result["included"], ["Burst"])

    def test_two_charge_limited_ability_exposes_two_uses(self):
        ability = {"type": "Ability", "stats": {"charges": {"value": 2}, "damage": {"value": 30, "components": []}}}
        result = self.run_model(f"OWDamageModel.classify({json.dumps(ability)})")
        self.assertEqual(result["category"], "limited")
        self.assertEqual(result["useCount"], 2)

    def test_explosion_distance_scales_from_center_to_edge(self):
        ability = {
            "type": "Ability",
            "stats": {
                "damage": {"components": [{"label": "explosion, enemy", "min_value": 20, "max_value": 50}]},
                "radius": {"min_value": 1.5, "max_value": 5},
            },
        }
        expression = (
            f"[0,3.25,5].map(explosionDistance=>OWDamageModel.evaluate({{ability:{json.dumps(ability)},explosionDistance}}).damage)"
        )
        self.assertEqual(self.run_model(expression), [50, 35, 20])

    def test_repeatable_explosion_defaults_to_direct_hit_plus_max_explosion(self):
        weapon = {
            "type": "Weapon", "slot": "primary fire",
            "stats": {
                "damage": {"components": [
                    {"label": "direct hit", "value": 45},
                    {"label": "splash, enemy", "min_value": 10, "max_value": 80},
                ]},
                "radius": {"min_value": 0.5, "max_value": 2},
            },
        }
        default = self.run_model(f"OWDamageModel.evaluate({{ability:{json.dumps(weapon)}}})")
        splash = self.run_model(
            f"OWDamageModel.evaluate({{ability:{json.dumps(weapon)},explosionDistance:2}})"
        )
        shots = self.run_model(
            f"OWDamageModel.shotsToKill({{ability:{json.dumps(weapon)},target:{{health:250}}}})"
        )
        self.assertEqual(default["damage"], 125)
        self.assertEqual(default["damageParts"][0]["label"], "direct hit / max explosion")
        self.assertEqual(splash["damage"], 10)
        self.assertEqual(shots["shots"], 2)

    def test_dot_uses_tick_damage_when_available(self):
        ability = {
            "type": "Ability",
            "stats": {"damage": {"components": [{
                "label": "burn, enemy",
                "value": 20,
                "raw": "Deals 5 damage every 0.5 seconds; 20 over 2 seconds",
            }]}}
        }
        result = self.run_model(f"OWDamageModel.evaluate({{ability:{json.dumps(ability)}}})")
        self.assertEqual(result["kind"], "dot")
        self.assertEqual(len(result["damageParts"]), 4)
        self.assertTrue(all(part["label"] == "DoT tick" for part in result["damageParts"]))

    def test_dot_uses_explicit_total_with_duration(self):
        ability = {
            "type": "Ability",
            "stats": {
                "damage": {"components": [
                    {"label": "per second", "value": 90},
                    {"label": "total", "value": 315, "raw": "315 total"},
                ]},
                "duration": {"value": 3.5},
            },
        }
        result = self.run_model(f"OWDamageModel.evaluate({{ability:{json.dumps(ability)}}})")
        self.assertTrue(result["supported"])
        self.assertEqual(result["damage"], 315)
        self.assertEqual(result["dot"]["dotMode"], "total")

    def test_deployable_exposes_only_safe_damage_event(self):
        ability = {"name": "Deploy Turret", "type": "Ability", "stats": {"damage": {"value": 12, "components": []}}}
        result = self.run_model(f"OWDamageModel.classify({json.dumps(ability)})")
        self.assertTrue(result["supported"])
        self.assertEqual(result["kind"], "deployable")
        self.assertTrue(result["safePartOnly"])

    def test_deployable_without_safe_damage_has_specific_reason(self):
        ability = {"name": "Deploy Turret", "type": "Ability", "stats": {"damage": {"components": [{"label": "conditional stage", "value": 12}]}}}
        result = self.run_model(f"OWDamageModel.classify({json.dumps(ability)})")
        self.assertFalse(result["supported"])
        self.assertIn("per-hit, total, or damage-per-second", result["reason"])

    def test_shotgun_defaults_to_full_pellet_damage(self):
        weapon = {
            "type": "Weapon", "shot_type": ["Shotgun"],
            "stats": {"damage": {"components": [
                {"label": "per pellet", "value": 10}, {"label": "per shot", "value": 100},
            ]}},
        }
        result = self.run_model(
            f"OWDamageModel.shotsToKill({{ability:{json.dumps(weapon)},target:{{health:200}}}})"
        )
        self.assertEqual(result["shots"], 2)
        self.assertEqual(result["damageParts"][0]["label"], "full shotgun shot")

    def test_zarya_energy_scales_between_explicit_endpoints(self):
        weapon = {
            "name": "Particle Cannon", "type": "Weapon", "shot_type": ["Beam"],
            "stats": {"damage": {"components": [
                {"label": "at 0%", "value": 95}, {"label": "100% Energy", "value": 175},
            ]}},
        }
        expression = (
            f"[0,50,100].map(energy=>OWDamageModel.evaluate({{ability:{json.dumps(weapon)},energy}}).damage)"
        )
        self.assertEqual(self.run_model(expression), [95, 135, 175])


if __name__ == "__main__":
    unittest.main()
