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

    def test_player_facing_source_fields_are_rendered(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")

        self.assertIn("abilityShotTypes(ability)", source)
        self.assertIn("abilityNotes(ability)", source)
        self.assertIn("Shot type", source)
        self.assertIn("Gameplay notes", source)
        self.assertIn("/::|;;|[;,]/", source)

    def test_ability_details_are_reserved_for_gameplay_notes(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        description_source = source[
            source.index("function abilityDescription"):source.index("function abilityKeywords")
        ]
        notes_source = source[
            source.index("function abilityNotes"):source.index("function uniqueTextItems")
        ]

        self.assertNotIn('"ability_details"', description_source)
        self.assertNotIn('"ability details"', description_source)
        self.assertIn('"ability_details"', notes_source)
        self.assertIn('"ability details"', notes_source)
        self.assertIn(r"/\s*\*\s+|;;|::/", notes_source)


if __name__ == "__main__":
    unittest.main()
