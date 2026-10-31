#!/usr/bin/env python3
"""Testes seguros do perfil Games, sem tocar no cache real do usuário."""
from pathlib import Path
import importlib.util
import os
import tempfile
import time
import unittest

MODULE = Path(__file__).with_name("games.py")
SPEC = importlib.util.spec_from_file_location("snoopyos_games", MODULE)
games = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(games)

class GamesTests(unittest.TestCase):
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
