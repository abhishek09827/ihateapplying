import unittest
from engine.tools.location_matcher import (
    get_india_remote_priority,
    is_india_remote_eligible,
    get_india_remote_score_bonus
)

class TestLocationMatcher(unittest.TestCase):
    def test_explicit_india_location(self):
        rank, reason = get_india_remote_priority("Remote - India")
        self.assertEqual(rank, 3)
        self.assertIn("India", reason)
        self.assertEqual(get_india_remote_score_bonus("Remote - India"), 15)

        rank_city, _ = get_india_remote_priority("Bengaluru, India (Remote)")
        self.assertEqual(rank_city, 3)

        rank_hyd, _ = get_india_remote_priority("Hyderabad")
        self.assertEqual(rank_hyd, 3)

    def test_apac_location(self):
        rank, _ = get_india_remote_priority("APAC Remote")
        self.assertEqual(rank, 3)

    def test_worldwide_global_location(self):
        rank, _ = get_india_remote_priority("Worldwide")
        self.assertEqual(rank, 2)
        self.assertEqual(get_india_remote_score_bonus("Worldwide"), 10)

        rank_any, _ = get_india_remote_priority("Anywhere in the world")
        self.assertEqual(rank_any, 2)

    def test_generic_remote(self):
        rank, _ = get_india_remote_priority("Remote")
        self.assertEqual(rank, 1)
        self.assertEqual(get_india_remote_score_bonus("Remote"), 0)

    def test_restricted_geo_rejection(self):
        rank_us, reason_us = get_india_remote_priority("USA Only")
        self.assertEqual(rank_us, 0)
        eligible_us, _ = is_india_remote_eligible("USA Only")
        self.assertFalse(eligible_us)
        self.assertEqual(get_india_remote_score_bonus("USA Only"), -50)

        # Single country without remote
        rank_de, _ = get_india_remote_priority("Germany")
        self.assertEqual(rank_de, 0)

    def test_us_citizenship_restriction_in_description(self):
        desc = "Exciting AI role. Candidate must be a US Citizen and hold an active security clearance."
        rank, _ = get_india_remote_priority("Remote", desc)
        self.assertEqual(rank, 0)
        eligible, _ = is_india_remote_eligible("Remote", desc)
        self.assertFalse(eligible)

    def test_india_mentioned_in_description(self):
        desc = "We are an async engineering team hiring engineers across US, EU, and India."
        rank, _ = get_india_remote_priority("Remote", desc)
        self.assertEqual(rank, 3)
        eligible, _ = is_india_remote_eligible("Remote", desc)
        self.assertTrue(eligible)

if __name__ == "__main__":
    unittest.main()
