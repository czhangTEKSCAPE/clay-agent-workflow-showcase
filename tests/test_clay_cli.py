import os
import tempfile
import unittest
from unittest import mock

from tests import _path  # noqa: F401
import clay_cli


class FindClayTests(unittest.TestCase):
    def test_prefers_path(self):
        with mock.patch("shutil.which", return_value="/usr/bin/clay"):
            self.assertEqual(clay_cli.find_clay(), "/usr/bin/clay")

    def test_falls_back_to_plugin_cache_newest(self):
        with tempfile.TemporaryDirectory() as d:
            old, new = (os.path.join(d, v, "bin", "clay") for v in ("1.0", "2.0"))
            for i, path in enumerate((old, new)):
                os.makedirs(os.path.dirname(path))
                open(path, "w").close()
                os.utime(path, (1000 + i, 1000 + i))
            with mock.patch.object(clay_cli, "PLUGIN_GLOB", os.path.join(d, "*", "bin", "clay")), \
                 mock.patch("shutil.which", return_value=None), \
                 mock.patch("os.path.exists", return_value=False):
                self.assertEqual(clay_cli.find_clay(), new)

    def test_none_when_missing(self):
        with mock.patch("shutil.which", return_value=None), \
             mock.patch("os.path.exists", return_value=False), \
             mock.patch("glob.glob", return_value=[]):
            self.assertIsNone(clay_cli.find_clay())
            with self.assertRaises(SystemExit):
                clay_cli.require_clay()


if __name__ == "__main__":
    unittest.main()
