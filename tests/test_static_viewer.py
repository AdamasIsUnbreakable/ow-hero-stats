import json
import subprocess
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

    def test_hover_preview_excludes_gameplay_notes(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        preview_source = source[
            source.index("function renderAbilityDetailPanel"):source.index("function renderDetailStat")
        ]
        dialog_source = source[
            source.index("function renderAbilityDialogContent"):source.index("function positionOpenAbilityPanel")
        ]

        self.assertNotIn("abilityNotes(ability)", preview_source)
        self.assertIn("abilityNotes(ability)", dialog_source)
        self.assertIn("renderAbilityNotes(notes, ability)", dialog_source)

    def test_dialog_open_clears_tooltip_state(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")

        self.assertIn("clearAbilityPreviewState();", source)
        self.assertIn('row.classList.remove("hovered", "keyboard-open")', source)

    def test_loading_state_and_copy_link_cleanup(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")
        viewer_source = "\n".join((source, html, styles))

        self.assertIn("showInitialLoadingState();", source)
        self.assertIn('aria-busy="true"', html)
        self.assertNotIn("Copy link", viewer_source)
        self.assertNotIn("copySelectedHeroLink", viewer_source)
        self.assertNotIn("copyLinkFeedbackTimer", viewer_source)
        self.assertNotIn("data-copy-link", viewer_source)
        self.assertNotIn("data-copy-link-feedback", viewer_source)

    def test_ability_icon_manifest_fallback_is_always_an_array(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        manifest_source = source[
            source.index("async function fetchAbilityIconManifest"):source.index("function bindEvents")
        ]

        self.assertNotIn("return {};", manifest_source)
        self.assertEqual(manifest_source.count("return [];"), 2)
        self.assertIn("return Array.isArray(entries) ? entries : [];", manifest_source)

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
            source.index("function renderDamageCalculatorGraph"):source.index("function updateShotsToKillResult")
        ]

        self.assertIn("function renderDamageCalculatorGraph(ability)", graph_source)
        self.assertIn("OWDamageModel.classify(ability)", graph_source)
        self.assertIn("Unavailable: ${escapeHtml(model.reason)}", graph_source)
        self.assertIn("reduced damage was not safely parsed", graph_source)
        self.assertNotIn("function hasSafeDamageFalloffRange", source)
        self.assertNotIn("function canRenderDamageFalloffGraph", source)
        self.assertNotIn("function renderDamageFalloffGraph", source)

    def test_dialog_reuses_raw_aware_stat_renderers(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        dialog_source = source[
            source.index("function renderAbilityDialogContent"):source.index("function positionOpenAbilityPanel")
        ]

        self.assertIn("renderDetailStat(stat, ability)", dialog_source)
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

    def test_health_meter_hides_missing_types_and_shows_shots_calculator(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        styles = STYLES_CSS.read_text(encoding="utf-8")
        health_source = source[
            source.index("function renderHealthCell"):source.index("function formatHealth(")
        ]

        self.assertIn("amount > 0", health_source)
        self.assertIn("function renderHealthStats", health_source)
        self.assertIn("Shots to kill calculator", health_source)
        self.assertIn("data-attacker-grid", health_source)
        self.assertIn("data-shots-weapon-list", health_source)
        self.assertIn("data-shots-limited-list", health_source)
        self.assertNotIn("Total functional health pool", health_source)
        self.assertNotIn("max(d − 7, d × 0.5)", health_source)
        self.assertIn("repeat(auto-fit", styles)

    def test_single_ruleset_resolves_base_without_a_mode_control(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")

        self.assertNotIn('id="ruleset-select"', html)
        self.assertNotIn("function populateRulesetSelector", source)
        self.assertNotIn("getRulesetFromUrl", source)
        self.assertIn("function resolveHeroRuleset", source)
        self.assertIn("detail.ruleset_overrides?.[ruleset]", source)
        self.assertIn("renderKeywordChip", source)
        self.assertIn("rolePassiveDescription", source)
        self.assertIn("formatHeadshot", source)

    def test_ruleset_ability_patches_match_safely(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        merge_source = source[
            source.index("function deepMergeRuleset"):source.index("function formatHeadshot")
        ]

        self.assertIn("function findAbilityForPatch", merge_source)
        self.assertIn("Number.isFinite(abilityPatch.ability_index)", merge_source)
        self.assertIn("ability.ability_index === abilityPatch.ability_index", merge_source)
        self.assertIn("candidates.length === 1 ? candidates[0] : null", merge_source)
        self.assertNotIn("target.abilities?.find((item) => item.name === abilityPatch.name)", merge_source)
        self.assertNotIn("updateRulesetUrl", source)
        self.assertNotIn('id="ruleset-select"', INDEX_HTML.read_text(encoding="utf-8"))

    def test_stale_mode_urls_are_removed_and_generated_links_omit_mode(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        linked_mentions = source[
            source.index("function renderLinkedMentions"):source.index("function bindDamageCalculator")
        ]

        self.assertIn("function removeStaleModeFromUrl", source)
        self.assertEqual(source.count('url.searchParams.delete("mode")'), 3)
        self.assertIn("removeStaleModeFromUrl();", source)
        self.assertNotIn("mode=", linked_mentions)
        self.assertIn('href="?hero=${encodeURIComponent(hero.slug)}"', linked_mentions)
        self.assertNotIn("renderRulesetCoverageNote", source)
        self.assertNotIn("renderCompareRulesetCoverage", source)

    def test_stale_6v6_bookmark_is_replaced_with_a_mode_free_url(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        cleanup_source = source[
            source.index("function removeStaleModeFromUrl"):source.index("function updateHeroUrl")
        ]
        script = f"""
          global.window = {{
            location: {{ href: "https://example.test/?hero=ashe&mode=6v6" }},
            history: {{
              state: {{ hero: "ashe" }},
              replaceState(state, title, href) {{ this.replaced = href; }}
            }}
          }};
          {cleanup_source}
          removeStaleModeFromUrl();
          console.log(JSON.stringify(window.history.replaced));
        """
        result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

        self.assertEqual(json.loads(result.stdout), "https://example.test/?hero=ashe")

    def test_shared_calculator_consumers_and_search_compare_controls_exist(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")

        self.assertIn("OWDamageModel.evaluate", source)
        self.assertIn("OWDamageModel.shotsToKill", source)
        self.assertIn("data-damage-headshot", source)
        self.assertIn("OWDamageModel.calculateCombo", source)
        self.assertIn("data-graph-selected", source)
        self.assertIn("renderLinkedMentions", source)
        self.assertIn('id="search-target"', html)
        self.assertIn('id="subrole-filter"', html)
        self.assertIn('id="compare-toggle"', html)

    def test_shots_selector_filters_non_damage_and_labels_unsupported_damage(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        calculator_source = source[
            source.index("function damagingAbilityEntries"):source.index("function renderGeneratedTag")
        ]

        self.assertIn("function renderRepeatableChoices", calculator_source)
        self.assertIn("function renderLimitedChoices", calculator_source)
        self.assertIn('["perks", "passive"]', calculator_source)
        self.assertIn("hasDamageSource(ability)", calculator_source)
        self.assertIn("Unsupported: ${escapeHtml(model.reason)}", calculator_source)
        self.assertIn("OWDamageModel.calculateCombo", source)

    def test_combo_ui_separates_repeatable_weapons_and_limited_events(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        calculator_source = source[
            source.index("function renderHealthStats"):source.index("function getHeroSearchMatches")
        ]

        self.assertIn("Repeatable weapons", calculator_source)
        self.assertIn("Limited abilities", calculator_source)
        self.assertIn('data-shots-weapon="${ability.ability_index}"', calculator_source)
        self.assertIn("data-limited-use", calculator_source)
        self.assertIn("Array.from({ length: model.useCount }", calculator_source)
        self.assertNotIn("data-weapon-use", calculator_source)

    def test_damage_controls_and_role_sorted_attacker_picker_exist(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        calculator_source = source[
            source.index("function renderAttackerHeroChoices"):source.index("function getHeroSearchMatches")
        ]

        self.assertIn('[["Tank", 0], ["Damage", 1], ["Support", 2], ["Unknown", 3]]', calculator_source)
        self.assertIn("Explosion distance from center", calculator_source)
        self.assertIn("data-damage-pellets", calculator_source)
        self.assertIn("data-damage-energy", calculator_source)
        self.assertIn("data-damage-headshot", calculator_source)

    def test_compare_rebuilds_on_history_navigation(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")

        self.assertIn("state.compareMode && state.compareBuilt", source)
        self.assertIn("if (rebuildComparison) renderComparison()", source)


if __name__ == "__main__":
    unittest.main()
