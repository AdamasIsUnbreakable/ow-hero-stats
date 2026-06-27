import unittest
from pathlib import Path


MAIN_JS = Path(__file__).parents[1] / "site" / "src" / "main.js"
STYLES_CSS = Path(__file__).parents[1] / "site" / "src" / "styles.css"


class StaticViewerTests(unittest.TestCase):
    def test_missing_ability_icon_uses_distinct_placeholder(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")

        self.assertIn('class="${className} ability-icon-fallback"', source)
        self.assertIn('class="missing-icon-glyph">?</span>', source)
        self.assertNotIn("heroInitials(ability.name)", source)

    def test_ability_tooltips_share_managed_hover_and_click_state(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        self.assertIn('row.classList.add("hovered")', source)
        self.assertIn("toggleExpandedAbilityRow(row)", source)
        self.assertIn("closeExpandedAbilityRows()", source)
        self.assertIn("if (hasExpandedAbilityRow())", source)
        self.assertIn(".ow-ability-row.hovered .ability-detail-panel", styles)
        self.assertNotIn(".ow-ability-row:hover .ability-detail-panel", styles)


if __name__ == "__main__":
    unittest.main()
