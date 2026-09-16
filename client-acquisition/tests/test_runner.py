import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator.models import Lead, LeadStatus
from orchestrator.runner import AgentRunner, deterministic_demo_executor


def test_run_lead_reaches_approval_gate():
    lead = Lead(id="l1", name="Asha", company="Acme", email="asha@acme.test")
    runner = AgentRunner(deterministic_demo_executor)

    result = runner.run_lead(lead)

    assert lead.status == LeadStatus.OUTREACH_PENDING_APPROVAL
    assert result["approval_required"] is True
    assert [r["agent"] for r in result["runs"]] == [
        "company_researcher",
        "qualification",
        "pain_detector",
        "outbound_strategy",
    ]
    assert result["runs"][-1]["output"]["send"] is False


def test_runner_retries_transient_failure():
    attempts = {"count": 0}

    def flaky(agent, context):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary failure")
        return {"ok": True}

    lead = Lead(id="l2", name="Asha", company="Acme")
    runner = AgentRunner(flaky, max_retries=1)
    run = runner.execute(lead, "test_agent", {"trace_id": "t1"})

    assert run.output == {"ok": True}
    assert attempts["count"] == 2
