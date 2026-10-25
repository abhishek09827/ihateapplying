import unittest
from engine.tools.date_utils import parse_date_to_timestamp

class TestDateUtils(unittest.TestCase):
    def test_parse_iso_date(self):
        iso_str = "2026-03-15T12:00:00Z"
        ts = parse_date_to_timestamp(iso_str)
        self.assertGreater(ts, 0)

    def test_parse_rfc_date(self):
        rfc_str = "Wed, 15 Mar 2026 12:00:00 GMT"
        ts = parse_date_to_timestamp(rfc_str)
        self.assertGreater(ts, 0)

    def test_parse_epoch(self):
        epoch = 1773576000.0
        ts = parse_date_to_timestamp(epoch)
        self.assertEqual(ts, 1773576000.0)

    def test_parse_empty(self):
        self.assertEqual(parse_date_to_timestamp(""), 0.0)
        self.assertEqual(parse_date_to_timestamp(None), 0.0)

if __name__ == "__main__":
    unittest.main()
