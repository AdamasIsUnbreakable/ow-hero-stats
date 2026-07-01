import unittest

from overwatch_stats.parse_stats import (
    COMPLEX_DAMAGE_WARNING,
    COMPONENT_DAMAGE_WARNING,
    clean_text,
    parse_ammo,
    parse_cast_time,
    parse_cooldown,
    parse_damage,
    parse_duration,
    parse_falloff_range,
    parse_fire_rate,
    parse_headshot,
    parse_headshot_multiplier,
    parse_healing,
    parse_projectile_radius,
    parse_projectile_speed,
    parse_radius,
    parse_range_distance,
    parse_reload_time,
    parse_spread,
    parse_points,
)


class ParseStatsTests(unittest.TestCase):
    def test_clean_text_normalizes_html_and_dashes(self):
        self.assertEqual(clean_text("25<br>40 â€“ meters"), "25 40 - meters")

    def test_simple_seconds(self):
        stat = parse_cooldown("1.8 seconds")
        self.assertEqual(stat.value, 1.8)
        self.assertEqual(stat.unit, "seconds")
        self.assertEqual(stat.confidence, "high")

    def test_reload_time_seconds(self):
        stat = parse_reload_time("1.5 sec.")
        self.assertEqual(stat.value, 1.5)
        self.assertEqual(stat.unit, "seconds")

    def test_cast_time_splits_startup_and_recovery(self):
        stat = parse_cast_time("0.24 + 0.75 seconds")

        self.assertEqual(stat.confidence, "high")
        self.assertEqual([component.label for component in stat.components], ["startup", "recovery"])
        self.assertEqual([component.value for component in stat.components], [0.24, 0.75])

    def test_headshot_fields_are_structured(self):
        self.assertIs(parse_headshot("yes").value, True)
        self.assertIs(parse_headshot("no").value, False)
        self.assertEqual(parse_headshot_multiplier("2").value, 2)

        conditional = parse_headshot_multiplier("1.5, damage only")
        self.assertEqual(conditional.value, 1.5)
        self.assertEqual(conditional.confidence, "medium")
        self.assertEqual(conditional.components[0].notes, ["damage only"])

    def test_radius_and_range_support_ranges_and_infinity(self):
        radius = parse_radius("1.5 - 4 meters")
        self.assertEqual((radius.min_value, radius.max_value), (1.5, 4))
        self.assertEqual(radius.unit, "meters")

        distance = parse_range_distance("40 meters")
        self.assertEqual(distance.value, 40)
        self.assertEqual(distance.unit, "meters")

        self.assertEqual(parse_range_distance("∞").value, "infinite")

    def test_duration_seconds_without_unit_warns(self):
        stat = parse_duration("4")
        self.assertEqual(stat.value, 4)
        self.assertEqual(stat.confidence, "medium")
        self.assertTrue(stat.warnings)

    def test_duration_with_multiple_values_keeps_value_empty(self):
        stat = parse_duration("1.5 seconds (start) 5 seconds (burn)")
        self.assertIsNone(stat.value)
        self.assertEqual(stat.unit, "seconds")
        self.assertEqual(stat.confidence, "medium")
        self.assertIn("duration parsed into components; no single seconds value was assigned.", stat.warnings)
        self.assertEqual(stat.components[0].label, "start")
        self.assertEqual(stat.components[0].value, 1.5)
        self.assertEqual(stat.components[1].label, "burn")
        self.assertEqual(stat.components[1].value, 5)

    def test_duration_until_cancelled_parses_textual_duration(self):
        stat = parse_duration("Until cancelled")
        self.assertEqual(stat.value, "until_cancelled")
        self.assertEqual(stat.unit, "duration")
        self.assertEqual(stat.confidence, "medium")

    def test_duration_infinity_symbol(self):
        stat = parse_duration("∞")
        self.assertEqual(stat.value, "infinite")
        self.assertEqual(stat.unit, "duration")
        self.assertEqual(stat.confidence, "high")

    def test_falloff_range(self):
        stat = parse_falloff_range("25 - 40 meters")
        self.assertEqual(stat.min_value, 25)
        self.assertEqual(stat.max_value, 40)
        self.assertEqual(stat.unit, "meters")

    def test_damage_range_keeps_min_max(self):
        stat = parse_damage("22 â€“ 6.67")
        self.assertEqual(stat.min_value, 6.67)
        self.assertEqual(stat.max_value, 22)

    def test_damage_with_splash_warns(self):
        stat = parse_damage("110 â€“ 55 splash")
        self.assertIsNone(stat.value)
        self.assertIsNone(stat.min_value)
        self.assertIsNone(stat.max_value)
        self.assertEqual(stat.confidence, "low")
        self.assertIn(COMPLEX_DAMAGE_WARNING, stat.warnings)

    def test_direct_plus_splash_keeps_value_empty(self):
        stat = parse_damage("50 direct + 25 splash")
        self.assertIsNone(stat.value)
        self.assertIn(stat.confidence, {"medium", "low"})
        self.assertNotEqual(stat.confidence, "high")
        self.assertIn(COMPONENT_DAMAGE_WARNING, stat.warnings)

    def test_direct_plus_splash_parses_components(self):
        stat = parse_damage("50 direct + 25 splash")

        self.assertEqual(stat.raw, "50 direct + 25 splash")
        self.assertIsNone(stat.value)
        self.assertEqual(stat.unit, "damage")
        self.assertEqual(len(stat.components), 2)

        direct, splash = stat.components
        self.assertEqual(direct.label, "direct")
        self.assertEqual(direct.value, 50)
        self.assertIsNone(direct.min_value)
        self.assertIsNone(direct.max_value)
        self.assertEqual(direct.unit, "damage")
        self.assertEqual(direct.raw, "50 direct")

        self.assertEqual(splash.label, "splash")
        self.assertEqual(splash.value, 25)
        self.assertIsNone(splash.min_value)
        self.assertIsNone(splash.max_value)
        self.assertEqual(splash.unit, "damage")
        self.assertEqual(splash.raw, "25 splash")

    def test_slash_separated_damage_keeps_value_empty(self):
        stat = parse_damage("10/20/30")
        self.assertIsNone(stat.value)
        self.assertEqual(stat.confidence, "low")
        self.assertIn(COMPLEX_DAMAGE_WARNING, stat.warnings)

    def test_comma_separated_damage_keeps_value_empty(self):
        stat = parse_damage("30, 15")
        self.assertIsNone(stat.value)
        self.assertEqual(stat.confidence, "low")
        self.assertIn(COMPLEX_DAMAGE_WARNING, stat.warnings)

    def test_semicolon_damage_parses_best_guess_components(self):
        stat = parse_damage("50 - 20 (explosion, enemy); 100 over 5 seconds (burn, enemy)")

        self.assertIsNone(stat.value)
        self.assertEqual(stat.unit, "damage")
        self.assertEqual(stat.confidence, "medium")
        self.assertIn(COMPONENT_DAMAGE_WARNING, stat.warnings)
        self.assertEqual(len(stat.components), 2)
        self.assertEqual(stat.components[0].label, "explosion, enemy")
        self.assertEqual(stat.components[0].min_value, 20)
        self.assertEqual(stat.components[0].max_value, 50)
        self.assertEqual(stat.components[1].label, "burn, enemy")
        self.assertEqual(stat.components[1].value, 100)
        self.assertIn("over 5 seconds", stat.components[1].notes)

    def test_over_time_damage_parses_single_low_confidence_component(self):
        stat = parse_damage("75 over 0.59 seconds")

        self.assertIsNone(stat.value)
        self.assertEqual(stat.confidence, "low")
        self.assertEqual(len(stat.components), 1)
        self.assertEqual(stat.components[0].label, "over time")
        self.assertEqual(stat.components[0].value, 75)
        self.assertEqual(stat.components[0].unit, "damage")

    def test_complex_healing_components_use_healing_unit(self):
        stat = parse_healing("25 (instantly); 100 over 2 seconds (over time)")

        self.assertIsNone(stat.value)
        self.assertEqual(stat.unit, "healing")
        self.assertEqual(len(stat.components), 2)
        self.assertEqual(stat.components[0].unit, "healing")
        self.assertEqual(stat.components[1].unit, "healing")

    def test_blank_value(self):
        stat = parse_ammo("")
        self.assertIsNone(stat.value)
        self.assertEqual(stat.confidence, "unparsed")

    def test_explicit_not_applicable_values_are_empty_without_warnings(self):
        for value in ("None", "N/A", "n.a.", "not applicable", "-", "--", "—", "{{N/A}}", ""):
            with self.subTest(value=value):
                stat = parse_points(value)
                self.assertEqual(stat.confidence, "unparsed")
                self.assertIsNone(stat.value)
                self.assertEqual(stat.warnings, [])

    def test_infinite_ammo_symbol(self):
        stat = parse_ammo("∞ (Blaster)")
        self.assertEqual(stat.value, "infinite")
        self.assertEqual(stat.unit, "rounds")
        self.assertEqual(stat.confidence, "high")

    def test_weird_string_remains_unparsed(self):
        stat = parse_fire_rate("depends on charge level")
        self.assertEqual(stat.confidence, "unparsed")
        self.assertTrue(stat.warnings)

    def test_projectile_speed_meters_per_second(self):
        stat = parse_projectile_speed("120 m/s")
        self.assertEqual(stat.value, 120)
        self.assertEqual(stat.unit, "meters_per_second")
        self.assertEqual(stat.confidence, "high")

    def test_fire_rate_percentage_modifier_is_not_shots_per_second(self):
        stat = parse_fire_rate("+5 % (per stack)")

        self.assertEqual(stat.value, 5)
        self.assertEqual(stat.unit, "percent")
        self.assertEqual(stat.confidence, "medium")
        self.assertIn("percentage modifier", stat.warnings[0])

    def test_spread_with_multiple_values_keeps_value_empty(self):
        stat = parse_spread("1.2 degrees 3.4 degrees")
        self.assertIsNone(stat.value)
        self.assertEqual(stat.unit, "degrees")
        self.assertEqual(stat.confidence, "medium")
        self.assertIn("spread parsed into components; no single degrees value was assigned.", stat.warnings)
        self.assertEqual(len(stat.components), 2)

    def test_spread_with_single_value_and_comma_note(self):
        stat = parse_spread("1.5 degrees (max, horizontal only)")
        self.assertEqual(stat.value, 1.5)
        self.assertEqual(stat.unit, "degrees")
        self.assertEqual(stat.confidence, "high")

    def test_projectile_radius_none_with_note(self):
        stat = parse_projectile_radius("None (vs wall or barrier)")
        self.assertEqual(stat.value, "none")
        self.assertEqual(stat.unit, "meters")
        self.assertEqual(stat.confidence, "medium")

    def test_projectile_radius_labeled_slash_components(self):
        stat = parse_projectile_radius("2 m inner / 5 m outer")

        self.assertIsNone(stat.value)
        self.assertEqual(stat.confidence, "medium")
        self.assertIn("projectile radius parsed into components; no single meters value was assigned.", stat.warnings)
        self.assertEqual(len(stat.components), 2)
        self.assertEqual(stat.components[0].label, "inner")
        self.assertEqual(stat.components[0].value, 2)
        self.assertEqual(stat.components[1].label, "outer")
        self.assertEqual(stat.components[1].value, 5)

    def test_full_health_healing(self):
        stat = parse_healing("Revives ally at full health")
        self.assertEqual(stat.value, "full_health")
        self.assertEqual(stat.unit, "health")
        self.assertEqual(stat.confidence, "medium")


if __name__ == "__main__":
    unittest.main()
