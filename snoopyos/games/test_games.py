#!/usr/bin/env python3
"""Testes seguros do perfil Games, sem tocar no cache real do usuário."""
from pathlib import Path
import importlib.util
import os
import tempfile
import time
import unittest
from unittest.mock import patch

MODULE = Path(__file__).with_name("games.py")
SPEC = importlib.util.spec_from_file_location("snoopyos_games", MODULE)
games = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(games)

class GamesTests(unittest.TestCase):
    def test_cpu_guest_time_is_not_counted_twice(self):
        # Linux already includes guest/guest_nice in user/nice respectively.
        before = "cpu 100 20 30 400 10 5 5 0 40 5\n"
        after = "cpu 140 25 30 455 10 5 5 0 80 10\n"
        with patch.object(games.Path, "read_text", side_effect=[before, after]):
            old_total, old_idle = games.read_cpu()
            total, idle = games.read_cpu()
        self.assertEqual((old_total, old_idle), (570, 410))
        self.assertEqual((total, idle), (670, 465))
        self.assertAlmostEqual(100 * (1 - (idle - old_idle) / (total - old_total)), 45)

    def test_cpu_counters_without_optional_fields(self):
        with patch.object(games.Path, "read_text", return_value="cpu 100 20 30 400\n"):
            self.assertEqual(games.read_cpu(), (550, 400))

    def test_cpu_unavailable_or_malformed(self):
        for content in ("", "cpu 1 2\n", "cpu invalid counters\n"):
            with self.subTest(content=content), patch.object(games.Path, "read_text", return_value=content):
                self.assertEqual(games.read_cpu(), (0, 0))
        with patch.object(games.Path, "read_text", side_effect=OSError("unavailable")):
            self.assertEqual(games.read_cpu(), (0, 0))

    def test_cleanup_only_older_regular_files(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "thumbnails"
            directory.mkdir()
            old = directory / "old.png"
            recent = directory / "recent.png"
            old.write_bytes(b"old")
            recent.write_bytes(b"new")
            now = time.time()
            os.utime(old, (now - 10 * 86400, now - 10 * 86400))
            count, size = games.safe_cleanup(7, roots=[directory], now=now)
            self.assertEqual((count, size), (1, 3))
            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())

    def test_symlink_never_deleted_or_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "thumbnails"
            directory.mkdir()
            target = Path(temp) / "savegame.txt"
            target.write_text("do not delete")
            (directory / "external").symlink_to(target)
            (directory / "nested").symlink_to(Path(temp), target_is_directory=True)
            count, size = games.safe_cleanup(7, roots=[directory], now=time.time() + 10*86400)
            self.assertEqual((count, size), (0, 0))
            self.assertEqual(target.read_text(), "do not delete")

    def test_invalid_age(self):
        for days in (0, -1, 366):
            with self.assertRaises(ValueError):
                games.safe_cleanup(days)

    def test_size_format(self):
        self.assertEqual(games.human_size(1024), "1.0 KiB")
        self.assertEqual(games.human_size(0), "0 B")

    def test_boost_restore_is_idempotent(self):
        boost = games.GameBoost()
        calls = []
        def fake(*args):
            calls.append(args)
            if not args:
                return "true"
            return ""
        boost._query = fake
        self.assertTrue(boost.start())
        self.assertTrue(boost.start())
        boost.stop()
        boost.stop()
        self.assertEqual(calls, [(), ("-s", "false"), ("-s", "true")])

if __name__ == "__main__":
    unittest.main()

