import unittest
from pathlib import Path


MAIN_JS = Path(__file__).parents[1] / "site" / "src" / "main.js"


class StaticViewerTests(unittest.TestCase):
    def test_missing_ability_icon_uses_distinct_placeholder(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")

        self.assertIn('class="${className} ability-icon-fallback"', source)
        self.assertIn('class="missing-icon-glyph">?</span>', source)
        self.assertNotIn("heroInitials(ability.name)", source)


if __name__ == "__main__":
    unittest.main()
