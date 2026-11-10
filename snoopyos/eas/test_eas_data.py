"""Testes offline da Central EAS e Clima."""
from configparser import ConfigParser
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eas_data


class EasDataTests(unittest.TestCase):
    def test_defaults_and_city_validation(self):
        self.assertEqual(eas_data.DEFAULT_CITIES["BR"].name, "Nova Iguaçu")
        self.assertEqual(eas_data.DEFAULT_CITIES["US"].country, "US")
        with self.assertRaises(ValueError):
            eas_data.City("", "", "BR", 0, 0)
        with self.assertRaises(ValueError):
            eas_data.City("Teste", "", "XX", 0, 0)
        with self.assertRaises(ValueError):
            eas_data.City("Teste", "", "BR", 91, 0)

    def test_city_search_filters_country_and_places(self):
        response = {"results": [
            {"name": "Nova Iguaçu", "admin1": "Rio de Janeiro", "country_code": "BR",
             "feature_code": "PPLA2", "latitude": -22.75, "longitude": -43.45},
            {"name": "Iguaçu", "admin1": "Paraná", "country_code": "BR",
             "feature_code": "STM", "latitude": -25.5, "longitude": -54.5},
            {"name": "Iguazu", "admin1": "Misiones", "country_code": "AR",
             "feature_code": "PPL", "latitude": -25.6, "longitude": -54.6},
        ]}
        with patch("eas_data.request_json", return_value=response):
            cities = eas_data.search_cities("Iguaçu", "BR")
        self.assertEqual([city.label for city in cities], ["Nova Iguaçu, Rio de Janeiro"])

    def test_polygon_and_hole_membership(self):
        outer = [[-44, -24], [-42, -24], [-42, -22], [-44, -22], [-44, -24]]
        hole = [[-43.6, -23.1], [-43.4, -23.1], [-43.4, -22.9], [-43.6, -22.9], [-43.6, -23.1]]
        city = eas_data.City("Teste", "RJ", "BR", -22.75, -43.45)
        self.assertTrue(eas_data.ring_contains(outer, -43.45, -22.75))
        self.assertTrue(eas_data.covers_city({"type": "Polygon", "coordinates": [outer]}, city))
        hidden = eas_data.City("Furo", "RJ", "BR", -23.0, -43.5)
        self.assertFalse(eas_data.covers_city(
            {"type": "Polygon", "coordinates": [outer, hole]}, hidden))
        with self.assertRaises(ValueError):
            eas_data.covers_city({"type": "Point", "coordinates": [-43, -22]}, city)

    def test_forecast_formats_three_days(self):
        response = {
            "current": {"time": "2026-11-10T14:30", "temperature_2m": 27.4,
                        "apparent_temperature": 29.1, "relative_humidity_2m": 70,
                        "wind_speed_10m": 12.2, "weather_code": 2, "is_day": 1},
            "daily": {"time": ["2026-11-10", "2026-11-11", "2026-11-12"],
                      "weather_code": [2, 61, 95],
                      "temperature_2m_max": [30, 28, 27],
                      "temperature_2m_min": [21, 20, 19],
                      "precipitation_probability_max": [20, 70, 80]},
        }
        with patch("eas_data.request_json", return_value=response):
            current, conditions, timestamp, days = eas_data.forecast(
                eas_data.DEFAULT_CITIES["BR"])
        self.assertIn("27 °C", current)
        self.assertIn("Umidade 70%", conditions)
        self.assertIn("10/11 às 14:30", timestamp)
        self.assertEqual(len(days), 3)
        self.assertIn("Tempestade", days[2])

    def test_inmet_alerts_filter_time_and_geometry(self):
        city = eas_data.DEFAULT_CITIES["BR"]
        now = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        ring = [[-44, -24], [-42, -24], [-42, -22], [-44, -22], [-44, -24]]
        active = {"encerrado": False,
                  "inicio": (now - timedelta(hours=1)).isoformat(),
                  "fim": (now + timedelta(hours=1)).isoformat(),
                  "poligono": json.dumps({"type": "Polygon", "coordinates": [ring]}),
                  "descricao": "Chuva intensa", "severidade": "Perigo"}
        ended = dict(active, encerrado=True)
        with patch("eas_data.request_json", return_value={"hoje": [active, ended]}):
            alerts = eas_data.inmet_alerts(city)
        self.assertEqual(len(alerts), 1)
        self.assertIn("Chuva intensa · Perigo", alerts[0])

    def test_nws_alerts_keep_only_actual_events(self):
        future = (datetime.now(ZoneInfo("UTC")) + timedelta(hours=1)).isoformat()
        response = {"features": [
            {"properties": {"status": "Actual", "event": "Flood Warning",
                            "severity": "Severe", "ends": future, "expires": future}},
            {"properties": {"status": "Test", "event": "Test Message",
                            "severity": "Unknown", "ends": future, "expires": future}},
        ]}
        with patch("eas_data.request_json", return_value=response):
            alerts = eas_data.nws_alerts(eas_data.DEFAULT_CITIES["US"])
        self.assertEqual(len(alerts), 1)
        self.assertIn("Flood Warning · Severe", alerts[0])

    def test_request_json_rejects_invalid_and_oversized_payloads(self):
        class Response:
            def __init__(self, payload):
                self.payload = payload
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self, _limit):
                return self.payload

        with patch("eas_data.urlopen", return_value=Response(b"[]")):
            with self.assertRaises(ValueError):
                eas_data.request_json("https://example.invalid/")
        oversized = b"x" * (8 * 1024 * 1024 + 1)
        with patch("eas_data.urlopen", return_value=Response(oversized)):
            with self.assertRaises(ValueError):
                eas_data.request_json("https://example.invalid/")

    def test_desktop_entry_targets_installed_script(self):
        parser = ConfigParser(interpolation=None)
        parser.read(Path(__file__).with_name("org.snoopyos.EAS.desktop"), encoding="utf-8")
        entry = parser["Desktop Entry"]
        self.assertEqual(entry["Type"], "Application")
        self.assertEqual(entry["Exec"], "/usr/bin/python3 /usr/share/snoopyos/eas/eas.py")
        self.assertEqual(entry["Terminal"], "false")


if __name__ == "__main__":
    unittest.main()
