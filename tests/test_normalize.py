import unittest

from overwatch_stats.normalize import normalize_hero, normalize_selected


class NormalizeTests(unittest.TestCase):
    def test_normalize_mocked_cargo_response(self):
        hero = normalize_hero(
            {
                "Name": "Ashe",
                "Role": "Damage",
                "SubRole": "Hitscan",
                "Health": "200",
                "Armor": "",
                "Shield": None,
            },
            [
                {
                    "hero_name": "Ashe",
                    "ability_name": "The Viper",
                    "ability_key": "Primary",
                    "ability_type": "Weapon",
                    "shot_type": "Hitscan",
                    "damage": "40",
                    "reload_time": "0.25 seconds per round",
                    "ammo": "12",
                    "cooldown": "",
                    "fire_rate": "4 shots per second",
                    "duration": None,
                    "damage_falloff_range": "20 - 40 meters",
                }
            ],
        )
        self.assertEqual(hero.name, "Ashe")
        self.assertEqual(hero.health["health"], 200)
        self.assertEqual(hero.abilities[0].parsed["damage"].value, 40)
        self.assertEqual(hero.abilities[0].parsed["damage_falloff_range"].max_value, 40)
        self.assertEqual(hero.abilities[0].raw["reload_time"], "0.25 seconds per round")

    def test_normalize_cargo_response_with_spaced_field_names(self):
        hero = normalize_hero(
            {"Name": "Ashe", "Role": "Damage", "SubRole": "Sharpshooter", "Health": "250"},
            [
                {
                    "hero name": "Ashe",
                    "ability name": "Take Aim (ADS)",
                    "ability key": "secondary fire",
                    "ability type": "Weapon;;ADS",
                    "shot type": "Hitscan",
                    "damage falloff range": "35 - 55 meters",
                    "fire rate": "1.52 shots/s",
                    "reload time": "0.5 seconds",
                }
            ],
        )
        ability = hero.abilities[0]
        self.assertEqual(ability.name, "Take Aim (ADS)")
        self.assertEqual(ability.slot, "secondary fire")
        self.assertEqual(ability.type, "Weapon;;ADS")
        self.assertEqual(ability.parsed["damage_falloff_range"].min_value, 35)
        self.assertEqual(ability.parsed["fire_rate"].value, 1.52)
        self.assertEqual(ability.parsed["reload_time"].value, 0.5)

    def test_normalize_selected_filters_non_hero_character_rows(self):
        heroes = normalize_selected(
            [
                {"Name": "Ana", "Role": "Support", "Health": "250"},
                {"Name": "AimGod", "Role": "Support"},
            ],
            [
                {"hero name": "Ana", "ability name": "Biotic Rifle", "damage": "75"},
                {"hero name": "AimGod", "ability name": "Ignored", "damage": "1"},
            ],
            ["Ana"],
        )
        self.assertEqual([hero.name for hero in heroes], ["Ana"])
        self.assertEqual(heroes[0].abilities[0].name, "Biotic Rifle")

    def test_shion_role_override(self):
        hero = normalize_hero({"Name": "Shion"}, [])

        self.assertEqual(hero.name, "Shion")
        self.assertEqual(hero.role, "Damage")


if __name__ == "__main__":
    unittest.main()
