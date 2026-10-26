import json
import unittest
from types import SimpleNamespace
from unittest import mock

from tests import _path  # noqa: F401
import batch_run


def proc(stdout="", stderr=""):
    return SimpleNamespace(stdout=stdout, stderr=stderr)


class BatchRunTests(unittest.TestCase):
    def test_launch_returns_run_id(self):
        with mock.patch("subprocess.run", return_value=proc(json.dumps({"runId": "wfr_1"}))):
            self.assertEqual(batch_run.launch("clay", "wf_x", {"url": "u"}), "wfr_1")

    def test_launch_tolerates_garbage_output(self):
        with mock.patch("subprocess.run", return_value=proc("not json")):
            self.assertIsNone(batch_run.launch("clay", "wf_x", {"url": "u"}))

    def test_summarize_adds_credits_and_truncates_error(self):
        out = batch_run.summarize({"status": "failed", "error": "x" * 400,
                                   "dataCreditsUsed": 1.25, "actionCreditsUsed": 2.5,
                                   "progress": {"completed": 7}})
        self.assertEqual(out["credits"], 3.8)
        self.assertEqual(len(out["error"]), 150)
        self.assertEqual(out["steps"], 7)

    def test_poll_marks_finished_runs_and_skips_runs_without_id(self):
        runs = {"a": {"runId": "r1"}, "b": {"runId": None}}
        done = proc(json.dumps({"status": "completed", "dataCreditsUsed": 2}))
        with mock.patch("subprocess.run", return_value=done) as run, mock.patch("time.sleep"):
            batch_run.poll("clay", "wf_x", runs, timeout_s=5, interval_s=0)
        self.assertEqual(runs["a"]["status"], "completed")
        self.assertNotIn("status", runs["b"])
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
