import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("remaster", Path(__file__).parents[1] / "snoopyos/remasterizar-iso.py")
remaster = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remaster)


class IsoVersionTests(unittest.TestCase):
    def test_each_iso_reports_its_actual_release_workflow_build(self):
        self.assertEqual(remaster.support_version(False, {"GITHUB_RUN_NUMBER": "4"}), "0.1.4")
        self.assertEqual(remaster.support_version(True, {"GITHUB_RUN_NUMBER": "2"}), "0.2.2")

    def test_unlabelled_local_build_does_not_invent_an_installed_version(self):
        self.assertIsNone(remaster.support_version(False, {}))
        self.assertIsNone(remaster.support_version(True, {"GITHUB_RUN_NUMBER": "not-a-build"}))

    def test_explicit_version_must_belong_to_the_selected_edition(self):
        self.assertEqual(remaster.support_version(False, {"SNOOPYOS_SUPPORT_VERSION": "0.1.9"}), "0.1.9")
        with self.assertRaises(ValueError):
            remaster.support_version(True, {"SNOOPYOS_SUPPORT_VERSION": "0.1.9"})


if __name__ == "__main__":
    unittest.main()
