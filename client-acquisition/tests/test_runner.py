import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator.models import Lead, LeadStatus
from orchestrator.runner import AgentRunner, deterministic_demo_executor


class RunnerTests(unittest.TestCase):
    def test_run_lead_reaches_approval_gate(self):
        lead = Lead(id="l1", name="Asha", company="Acme", email="asha@acme.test")
        runner = AgentRunner(deterministic_demo_executor)

        result = runner.run_lead(lead)

        self.assertEqual(lead.status, LeadStatus.OUTREACH_PENDING_APPROVAL)
        self.assertTrue(result["approval_required"])
        self.assertEqual(
            [r["agent"] for r in result["runs"]],
            ["company_researcher", "qualification", "pain_detector", "outbound_strategy"],
        )
        self.assertFalse(result["runs"][-1]["output"]["send"])

    def test_runner_retries_transient_failure(self):
        attempts = {"count": 0}

        def flaky(agent, context):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("temporary failure")
            return {"ok": True}

        lead = Lead(id="l2", name="Asha", company="Acme")
        runner = AgentRunner(flaky, max_retries=1)
        run = runner.execute(lead, "test_agent", {"trace_id": "t1"})

        self.assertEqual(run.output, {"ok": True})
        self.assertEqual(attempts["count"], 2)


if __name__ == "__main__":
    unittest.main()
