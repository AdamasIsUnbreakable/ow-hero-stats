import unittest
from pathlib import Path


MAIN_JS = Path(__file__).parents[1] / "site" / "src" / "main.js"
STYLES_CSS = Path(__file__).parents[1] / "site" / "src" / "styles.css"
INDEX_HTML = Path(__file__).parents[1] / "site" / "index.html"
GAMEPLAY_NOTES_CLEANUP_JS = Path(__file__).parents[1] / "site" / "src" / "gameplay-notes-cleanup.js"


class StaticViewerTests(unittest.TestCase):
    def test_missing_ability_icon_uses_distinct_placeholder(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")

        self.assertIn('class="${className} ability-icon-fallback"', source)
        self.assertIn('class="missing-icon-glyph">?</span>', source)
        self.assertNotIn("heroInitials(ability.name)", source)

    def test_ability_hover_preview_and_dialog_use_distinct_paths(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")

        self.assertIn('row.classList.add("hovered")', source)
        self.assertIn("openAbilityDialog(abilityForRow(row), row)", source)
        self.assertNotIn("toggleExpandedAbilityRow(row)", source)
        self.assertIn(".ow-ability-row.hovered .ability-detail-panel", styles)
        self.assertNotIn(".ow-ability-row:hover .ability-detail-panel", styles)

    def test_ability_dialog_is_accessible_and_closable(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")

        self.assertIn('role="button" aria-haspopup="dialog"', source)
        self.assertIn('<dialog class="ability-dialog-backdrop" aria-labelledby=', source)
        self.assertIn('aria-label="Close ability details"', source)
        self.assertIn('event.key === "Enter" || event.key === " "', source)
        self.assertIn('dialog.addEventListener("cancel"', source)
        self.assertIn('dialog.addEventListener("keydown"', source)
        self.assertIn('event.key === "Escape"', source)
        self.assertIn("if (event.target === dialog)", source)
        self.assertIn("sourceRow?.isConnected", source)
        self.assertIn("sourceRow.focus()", source)
        self.assertIn('document.body.style.overflow = "hidden"', source)

    def test_damage_falloff_graph_refuses_to_guess_complex_damage(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        graph_source = source[
            source.index("function canRenderDamageFalloffGraph"):source.index("function positionOpenAbilityPanel")
        ]

        self.assertIn("function renderDamageFalloffGraph(ability)", graph_source)
        self.assertIn("damage.components?.length", graph_source)
        self.assertIn("Number.isFinite(damage.value)", graph_source)
        self.assertIn("reduced damage was not safely parsed", graph_source)
        self.assertIn("damage is not a simple parsed value", graph_source)

    def test_dialog_reuses_raw_aware_stat_renderers(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        dialog_source = source[
            source.index("function renderAbilityDialogContent"):source.index("function hasSafeDamageFalloffRange")
        ]

        self.assertIn("stats.map(renderDetailStat)", dialog_source)
        self.assertIn("renderWarningList(ability.parse_warnings)", dialog_source)
        self.assertIn("refreshAbilityDialog()", source)

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

    def test_gameplay_notes_cleanup_script_is_loaded(self) -> None:
        index = INDEX_HTML.read_text(encoding="utf-8")
        cleanup_source = GAMEPLAY_NOTES_CLEANUP_JS.read_text(encoding="utf-8")

        self.assertIn('./src/gameplay-notes-cleanup.js', index)
        self.assertIn("window.abilityNotes", cleanup_source)
        self.assertIn("function cleanGameplayNote", cleanup_source)
        self.assertIn("uniqueCleanGameplayNotes", cleanup_source)

    def test_health_meter_hides_missing_types_and_shows_functional_pool_math(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")
        health_source = source[
            source.index("function renderHealthCell"):source.index("function formatHealth(")
        ]

        self.assertIn("amount > 0", health_source)
        self.assertIn("function renderHealthStats", health_source)
        self.assertIn("Total functional health pool", health_source)
        self.assertIn("max(d − 7, d × 0.5)", health_source)
        self.assertIn("armor / 0.7", health_source)
        self.assertIn("when d ≤ 14", health_source)
        self.assertIn("repeat(auto-fit", styles)


if __name__ == "__main__":
    unittest.main()
