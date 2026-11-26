import datetime as dt
import unittest

import fetch_deals


class DealFetcherTests(unittest.TestCase):
    def test_offer_line_includes_shortened_description(self):
        offer = {
            "product": "Hackfleisch",
            "brand": "Gut & Günstig",
            "description": "oder gemischt " + "sehr " * 30,
            "price": 4.99,
        }

        line = fetch_deals.offer_line(offer)

        self.assertIn("oder gemischt", line)
        self.assertIn("…", line)
        self.assertLessEqual(len(line.split(" | ")[1]), fetch_deals.MAX_DESCRIPTION_LENGTH)

    def test_normalize_edeka_uses_official_offer_shape(self):
        raw = {
            "title": "Rinder-Hackfleisch",
            "descriptions": ["oder gemischt, 500g Packung"],
            "price": {"rawValue": 4.99},
            "validFrom": "2026-11-23",
            "validTill": "2026-11-28",
        }

        offer = fetch_deals.normalize_edeka(raw, dt.date(2026, 11, 26))

        self.assertEqual(offer["store"], "EDEKA")
        self.assertEqual(offer["description"], "oder gemischt, 500g Packung")
        self.assertEqual(offer["pack"], "500 g")


if __name__ == "__main__":
    unittest.main()
