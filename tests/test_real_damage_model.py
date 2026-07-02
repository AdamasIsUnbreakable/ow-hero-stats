import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
MODEL = ROOT / "site" / "src" / "damage-model.js"
HEROES = ROOT / "tests" / "fixtures" / "heroes"


class RealDamageModelTests(unittest.TestCase):
    def ability(self, slug: str, name: str) -> dict:
        hero = json.loads((HEROES / f"{slug}.json").read_text(encoding="utf-8"))
        ability = next(item for item in hero["abilities"] if item["name"] == name)
        ability["hero_slug"] = slug
        return ability

    def hero(self, slug: str) -> dict:
        return json.loads((HEROES / f"{slug}.json").read_text(encoding="utf-8"))

    def run_model(self, expression: str):
        script = f"require({json.dumps(str(MODEL))}); console.log(JSON.stringify({expression}));"
        result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
        return json.loads(result.stdout)

    def test_real_junkrat_frag_launcher_defaults_to_direct_hit(self):
        ability = self.ability("junkrat", "Frag Launcher")
        default = self.run_model(f"OWDamageModel.evaluate({{ability:{json.dumps(ability)}}})")
        splash = self.run_model(
            f"OWDamageModel.evaluate({{ability:{json.dumps(ability)},explosionDistance:2}})"
        )
        shots = self.run_model(
            f"OWDamageModel.shotsToKill({{ability:{json.dumps(ability)},target:{{health:250}}}})"
        )
        self.assertEqual(default["damage"], 125)
        self.assertEqual(splash["damage"], 10)
        self.assertEqual(shots["shots"], 2)

    def test_real_reaper_hellfire_uses_full_shot_damage(self):
        ability = self.ability("reaper", "Hellfire Shotguns")
        target = self.hero("reaper")["health"]
        result = self.run_model(
            f"OWDamageModel.shotsToKill({{ability:{json.dumps(ability)},target:{json.dumps(target)}}})"
        )
        self.assertEqual(result["damage"], 115)
        self.assertEqual(result["shots"], 3)
        self.assertTrue(result["allPelletsAssumed"])

    def test_real_sojourn_disruptor_uses_exported_total(self):
        ability = self.ability("sojourn", "Disruptor Shot")
        result = self.run_model(f"OWDamageModel.evaluate({{ability:{json.dumps(ability)}}})")
        self.assertTrue(result["supported"])
        self.assertEqual(result["kind"], "dot")
        self.assertEqual(result["dot"]["dotMode"], "total")
        self.assertEqual(result["damage"], 315)

    def test_real_supported_deployables_expose_only_safe_parts(self):
        trap = self.ability("junkrat", "Steel Trap")
        turret = self.ability("torbj-rn", "Deploy Turret")
        result = self.run_model(
            f"[{json.dumps(trap)},{json.dumps(turret)}].map(ability=>OWDamageModel.classify(ability))"
        )
        self.assertEqual([(item["kind"], item["maximum"]) for item in result], [("deployable", 100), ("deployable", 12)])
        self.assertTrue(all(item["safePartOnly"] for item in result))

        mine = self.ability("junkrat", "Concussion Mine")
        mine_result = self.run_model(f"OWDamageModel.classify({json.dumps(mine)})")
        self.assertTrue(mine_result["supported"])
        self.assertEqual((mine_result["kind"], mine_result["maximum"], mine_result["useCount"]), ("explosion", 120, 2))

    def test_real_molten_core_stays_unsupported_with_specific_reason(self):
        ability = self.ability("torbj-rn", "Molten Core")
        result = self.run_model(f"OWDamageModel.classify({json.dumps(ability)})")
        self.assertFalse(result["supported"])
        self.assertIn("pool DPS", result["reason"])
        self.assertIn("armor bonus", result["reason"])

    def test_real_zarya_primary_and_alt_fire_scale_with_energy(self):
        primary = self.ability("zarya", "Particle Cannon")
        alternate = self.ability("zarya", "Particle Cannon Alt Fire")
        primary_result = self.run_model(
            f"[0,50,100].map(energy=>OWDamageModel.evaluate({{ability:{json.dumps(primary)},energy}}).damage)"
        )
        alternate_result = self.run_model(
            f"[0,50,100].map(energy=>OWDamageModel.evaluate({{ability:{json.dumps(alternate)},energy}}).damage)"
        )
        self.assertEqual(primary_result, [95, 135, 175])
        self.assertEqual(alternate_result, [55, 82.5, 110])

    def test_real_vendetta_stages_and_simple_events_are_supported(self):
        fang = self.ability("vendetta", "Palatine Fang")
        blade = self.ability("vendetta", "Sundering Blade")
        edge = self.ability("vendetta", "Projected Edge")
        result = [
            self.run_model(f"OWDamageModel.classify({json.dumps(ability)})")
            for ability in (fang, blade, edge)
        ]
        self.assertEqual([item["kind"] for item in result], ["staged", "staged", "direct"])
        self.assertTrue(all(item["supported"] for item in result))
        self.assertEqual([stage["damage"] for stage in result[0]["stages"]], [45, 120])
        self.assertEqual(
            [(stage["label"], stage["damage"]) for stage in result[1]["stages"]],
            [
                ("Stage 1 (direct)", 100),
                ("Stage 1 (indirect)", 50),
                ("Stage 2 (direct)", 200),
                ("Stage 2 (indirect)", 100),
                ("Stage 3 (direct)", 400),
                ("Stage 3 (indirect)", 200),
            ],
        )
        fang_damage = self.run_model(
            f"[0,1].map(stage=>OWDamageModel.evaluate({{ability:{json.dumps(fang)},stage}}).damage)"
        )
        blade_damage = self.run_model(
            f"[0,1,2,3,4,5].map(stage=>OWDamageModel.evaluate({{ability:{json.dumps(blade)},stage}}).damage)"
        )
        self.assertEqual(fang_damage, [45, 120])
        self.assertEqual(blade_damage, [100, 50, 200, 100, 400, 200])


if __name__ == "__main__":
    unittest.main()
