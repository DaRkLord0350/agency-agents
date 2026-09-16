import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from client_acquisition.orchestrator.models import Lead, LeadStatus
from client_acquisition.orchestrator.registry import AGENT_REGISTRY, get_agent_path
from client_acquisition.orchestrator.state_machine import InvalidTransition, can_transition, transition


def test_new_lead_can_enter_research():
    lead = Lead(company_name="Example Co")
    transition(lead, LeadStatus.RESEARCHING)
    assert lead.status is LeadStatus.RESEARCHING


def test_invalid_transition_is_rejected():
    lead = Lead(company_name="Example Co")
    with pytest.raises(InvalidTransition):
        transition(lead, LeadStatus.WON)


def test_terminal_states_have_no_outgoing_transition():
    assert not can_transition(LeadStatus.WON, LeadStatus.LOST)
    assert not can_transition(LeadStatus.LOST, LeadStatus.NEW)


def test_registry_points_to_existing_agents():
    assert len(AGENT_REGISTRY) >= 8
    for capability in AGENT_REGISTRY:
        assert get_agent_path(capability).is_file()
