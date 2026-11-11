import unittest
from earthquake_alert import event_country, load_events

class EarthquakeAlertTests(unittest.TestCase):
    def test_country_flag_from_usgs_place(self):
        flag, country = event_country("12 km S of Tokyo, Japan")
        self.assertEqual(flag, "🇯🇵")
        self.assertEqual(country, "Japan")

    def test_unknown_country_uses_global_flag(self):
        flag, country = event_country("Remote seismic region")
        self.assertEqual(flag, "🌐")
        self.assertEqual(country, "Região não identificada")

    def test_filters_below_threshold_and_sorts_newest_first(self):
        payload = {"features": [
            {"properties": {"id": "old", "mag": 5.0, "place": "Chile", "time": 1000}},
            {"properties": {"id": "new", "mag": 7.8, "place": "Japan", "time": 3000}},
        ]}
        result = load_events(payload, 5.5)
        self.assertEqual([item["id"] for item in result], ["new"])
        self.assertEqual(result[0]["magnitude"], 7.8)

if __name__ == "__main__":
    unittest.main()
