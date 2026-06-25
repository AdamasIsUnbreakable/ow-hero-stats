import unittest

from overwatch_stats.parse_stats import (
    COMPLEX_DAMAGE_WARNING,
    clean_text,
    parse_ammo,
    parse_cooldown,
    parse_damage,
    parse_duration,
    parse_falloff_range,
    parse_fire_rate,
    parse_projectile_speed,
    parse_reload_time,
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

    def test_duration_seconds_without_unit_warns(self):
        stat = parse_duration("4")
        self.assertEqual(stat.value, 4)
        self.assertEqual(stat.confidence, "medium")
        self.assertTrue(stat.warnings)

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
        self.assertEqual(stat.min_value, 55)
        self.assertEqual(stat.max_value, 110)
        self.assertEqual(stat.confidence, "low")
        self.assertIn(COMPLEX_DAMAGE_WARNING, stat.warnings)

    def test_direct_plus_splash_keeps_value_empty(self):
        stat = parse_damage("50 direct + 25 splash")
        self.assertIsNone(stat.value)
        self.assertEqual(stat.confidence, "low")
        self.assertIn(COMPLEX_DAMAGE_WARNING, stat.warnings)

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

    def test_blank_value(self):
        stat = parse_ammo("")
        self.assertIsNone(stat.value)
        self.assertEqual(stat.confidence, "unparsed")

    def test_weird_string_remains_unparsed(self):
        stat = parse_fire_rate("depends on charge level")
        self.assertEqual(stat.confidence, "unparsed")
        self.assertTrue(stat.warnings)

    def test_projectile_speed_meters_per_second(self):
        stat = parse_projectile_speed("120 m/s")
        self.assertEqual(stat.value, 120)
        self.assertEqual(stat.unit, "meters_per_second")
        self.assertEqual(stat.confidence, "high")


if __name__ == "__main__":
    unittest.main()
