from __future__ import annotations

import unittest

from overwatch_stats.images import (
    ImageInfo,
    build_manifest_entry,
    filter_portrait_titles,
    hero_name_from_file_title,
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


if __name__ == "__main__":
    unittest.main()
