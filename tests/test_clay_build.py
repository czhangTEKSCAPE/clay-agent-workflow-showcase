import json
import unittest
from types import SimpleNamespace
from unittest import mock

from tests import _path  # noqa: F401
import clay_build


def proc(payload):
    return SimpleNamespace(stdout=json.dumps(payload), stderr="")


class HelperTests(unittest.TestCase):
    def test_pin_and_ref(self):
        self.assertEqual(clay_build.pin("n1", "$.x"), {"type": "string", "sourceNodeId": "n1", "sourcePath": "$.x"})
        self.assertEqual(clay_build.ref("a.b"), {"type": "reference", "expression": "{{a.b}}"})

    def test_schema_defaults_required_to_all_properties(self):
        s = clay_build.schema({"a": {}, "b": {}})
        self.assertEqual(s["required"], ["a", "b"])
        self.assertEqual(clay_build.schema({"a": {}}, required=[])["required"], [])

    def test_coalesce_keeps_order(self):
        self.assertEqual(clay_build.coalesce(1, 2)["candidates"], [1, 2])


class CliRetryTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(clay_build, "CLAY", "clay")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_retries_transient_server_errors_then_succeeds(self):
        replies = [proc({"error": {"code": "server_error", "message": "504"}}), proc({"ok": True})]
        with mock.patch("subprocess.run", side_effect=replies) as run, mock.patch("time.sleep"):
            self.assertEqual(clay_build.cli("workflows", "get", "wf"), {"ok": True})
        self.assertEqual(run.call_count, 2)

    def test_does_not_retry_other_errors(self):
        with mock.patch("subprocess.run", return_value=proc({"error": {"code": "bad_request"}})) as run:
            with self.assertRaises(SystemExit):
                clay_build.cli("workflows", "get", "wf")
        self.assertEqual(run.call_count, 1)

    def test_gives_up_after_retries(self):
        err = proc({"error": {"code": "server_error", "message": "504"}})
        with mock.patch("subprocess.run", return_value=err) as run, mock.patch("time.sleep"):
            with self.assertRaises(SystemExit):
                clay_build.cli("workflows", "get", "wf", retries=2)
        self.assertEqual(run.call_count, 3)

    def test_missing_cli_exits_cleanly(self):
        with mock.patch.object(clay_build, "CLAY", None):
            with self.assertRaises(SystemExit):
                clay_build.cli("workflows", "get", "wf")


if __name__ == "__main__":
    unittest.main()
