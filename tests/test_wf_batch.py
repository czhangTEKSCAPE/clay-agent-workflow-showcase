import json
import unittest
from types import SimpleNamespace
from unittest import mock

from tests import _path  # noqa: F401
import wf_batch


def proc(stdout="", stderr=""):
    return SimpleNamespace(stdout=stdout, stderr=stderr)


def approval_required(workflow, action="workflows.run"):
    return json.dumps({"error": {"code": "approval_required", "details": {
        "actionApprovalRequestId": "req_1", "action": action, "input": {"workflowId": workflow}}}})


class StartRunTests(unittest.TestCase):
    def test_plain_success(self):
        with mock.patch("subprocess.run", return_value=proc(json.dumps({"runId": "wfr_1"}))):
            self.assertEqual(wf_batch.start_run("clay", "wf_a", {}), ("wfr_1", ""))

    def test_waits_for_human_approval_by_default(self):
        with mock.patch("subprocess.run", return_value=proc(approval_required("wf_a"))) as run:
            rid, note = wf_batch.start_run("clay", "wf_a", {})
        self.assertIsNone(rid)
        self.assertIn("--approve-runs", note)
        self.assertEqual(run.call_count, 1)  # never approved on its own

    def test_approves_only_when_flag_set(self):
        replies = [proc(approval_required("wf_a")), proc("started wfr_ABC123")]
        with mock.patch("subprocess.run", side_effect=replies) as run:
            rid, _ = wf_batch.start_run("clay", "wf_a", {}, approve_runs=True)
        self.assertEqual(rid, "wfr_ABC123")
        self.assertEqual(run.call_args_list[1].args[0][1:3], ["approvals", "approve"])

    def test_refuses_to_approve_a_different_workflow(self):
        with mock.patch("subprocess.run", return_value=proc(approval_required("wf_other"))) as run:
            rid, note = wf_batch.start_run("clay", "wf_a", {}, approve_runs=True)
        self.assertIsNone(rid)
        self.assertIn("refusing", note)
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
