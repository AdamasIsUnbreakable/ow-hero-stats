from __future__ import annotations

import unittest

from overwatch_stats.images import (
    ImageInfo,
    ability_icon_key_from_file_title,
    ability_match_key,
    build_ability_manifest_entry,
    build_manifest_entry,
    filter_portrait_titles,
    hero_name_from_file_title,
    match_ability_icon_titles,
    portrait_slug_from_file_title,
)


class ImageTests(unittest.TestCase):
    def test_filter_keeps_hero_portraits_and_skips_icons(self) -> None:
        titles = [
            "File:Ashe Hero.png",
            "File:Icon-Ashe.png",
            "File:Soldier 76 Hero.webp",
            "File:Ashe Skin.png",
        ]

        self.assertEqual(filter_portrait_titles(titles), ["File:Ashe Hero.png", "File:Soldier 76 Hero.webp"])

    def test_hero_name_from_file_title(self) -> None:
        self.assertEqual(hero_name_from_file_title("File:Ashe Hero.png"), "Ashe")
        self.assertIsNone(hero_name_from_file_title("File:Icon-Ashe.png"))

    def test_portrait_slug_from_file_title(self) -> None:
        self.assertEqual(portrait_slug_from_file_title("File:Ashe Hero.png"), "ashe")
        self.assertEqual(portrait_slug_from_file_title("File:Soldier 76 Hero.png"), "soldier-76")
        self.assertEqual(portrait_slug_from_file_title("File:D.Va Hero.png"), "d-va")

    def test_manifest_entry_uses_public_asset_path(self) -> None:
        entry = build_manifest_entry(
            "File:Ashe Hero.png",
            ImageInfo(
                source_url="https://static.wikia.nocookie.net/example/ashe.png",
                width=300,
                height=300,
                mime="image/png",
                size=12345,
            ),
        )

        self.assertEqual(entry["hero_slug"], "ashe")
        self.assertEqual(entry["hero_name"], "Ashe")
        self.assertEqual(entry["file_title"], "File:Ashe Hero.png")
        self.assertEqual(entry["local_path"], "assets/heroes/ashe.png")
        self.assertEqual(entry["width"], 300)
        self.assertEqual(entry["height"], 300)
        self.assertEqual(entry["mime"], "image/png")
        self.assertEqual(entry["size"], 12345)

    def test_ability_icon_key_normalizes_fandom_file_titles(self) -> None:
        self.assertEqual(ability_icon_key_from_file_title("File:Remote Detonator.png"), "remotedetonator")
        self.assertEqual(ability_icon_key_from_file_title("File:Icon-ability.helixrockets.png"), "helixrockets")
        self.assertEqual(ability_icon_key_from_file_title("File:Perk VipersSting.png"), "viperssting")
        self.assertEqual(ability_match_key("Viper's Sting"), "viperssting")

    def test_match_ability_icon_titles_only_selects_needed_abilities(self) -> None:
        matches = match_ability_icon_titles(
            {
                "ashe": [
                    {"hero_slug": "ashe", "hero_name": "Ashe", "ability_name": "Remote Detonator"},
                    {"hero_slug": "ashe", "hero_name": "Ashe", "ability_name": "Viper's Sting"},
                    {"hero_slug": "ashe", "hero_name": "Ashe", "ability_name": "Dynamite"},
                ]
            },
            {"ashe": ["File:Remote Detonator.png", "File:Perk VipersSting.png", "File:Unrelated.png"]},
        )

        self.assertEqual([match["ability_name"] for match in matches], ["Remote Detonator", "Viper's Sting"])

    def test_match_numbered_hero_ability_icons_by_slot_order(self) -> None:
        matches = match_ability_icon_titles(
            {
                "ana": [
                    {"hero_slug": "ana", "hero_name": "Ana", "ability_name": "Sleep Dart", "slot": "ability 1"},
                    {"hero_slug": "ana", "hero_name": "Ana", "ability_name": "Biotic Grenade", "slot": "ability 2"},
                    {
                        "hero_slug": "ana",
                        "hero_name": "Ana",
                        "ability_name": "Biotic Rifle",
                        "slot": "primary fire",
                    },
                    {"hero_slug": "ana", "hero_name": "Ana", "ability_name": "Zoom (ADS)", "slot": "secondary fire"},
                    {"hero_slug": "ana", "hero_name": "Ana", "ability_name": "Nano Boost", "slot": "ultimate"},
                    {"hero_slug": "ana", "hero_name": "Ana", "ability_name": "Groggy", "type": "Minor Perk"},
                ]
            },
            {
                "ana": [
                    "File:Ability-ana1.png",
                    "File:Ability-ana2.png",
                    "File:Ability-ana3.png",
                    "File:Ability-ana4.png",
                    "File:Zoom Ana Secondary.png",
                    "File:Perk Groggy.png",
                ]
            },
        )

        self.assertEqual(
            [(match["ability_name"], match["file_title"]) for match in matches],
            [
                ("Groggy", "File:Perk Groggy.png"),
                ("Zoom (ADS)", "File:Zoom Ana Secondary.png"),
                ("Biotic Rifle", "File:Ability-ana1.png"),
                ("Sleep Dart", "File:Ability-ana2.png"),
                ("Biotic Grenade", "File:Ability-ana3.png"),
                ("Nano Boost", "File:Ability-ana4.png"),
            ],
        )

    def test_ability_manifest_entry_uses_public_asset_path(self) -> None:
        entry = build_ability_manifest_entry(
            "File:Remote Detonator.png",
            ImageInfo(
                source_url="https://static.wikia.nocookie.net/example/remote.png",
                width=128,
                height=128,
                mime="image/png",
                size=4321,
            ),
            {"hero_slug": "ashe", "hero_name": "Ashe", "ability_name": "Remote Detonator"},
        )

        self.assertEqual(entry["hero_slug"], "ashe")
        self.assertEqual(entry["ability_name"], "Remote Detonator")
        self.assertEqual(entry["ability_slug"], "remote-detonator")
        self.assertEqual(entry["local_path"], "assets/abilities/ashe/remote-detonator.png")


if __name__ == "__main__":
    unittest.main()
