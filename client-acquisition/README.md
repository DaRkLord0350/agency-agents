# Client Acquisition OS

A lightweight orchestration layer built around the existing Agency Agents roster.

## Phase 2 — Executable runner

Phase 2 adds a provider-agnostic execution layer. The runner passes structured context from one specialist to the next, records a traceable `AgentRun`, retries transient failures within a bounded limit, and stops at a human approval gate before outreach is sent.

### Run the safe local demo

From the repository root:

```bash
python client-acquisition/cli.py run-lead --name "Asha" --company "Acme" --email "asha@acme.test"
```

The local demo executor is deterministic and performs **no network calls**. It produces sample research, qualification, pain-detection and outreach-draft outputs so the orchestration can be tested before connecting a real model provider.

### Runtime flow

`Lead → Research → Qualification → Pain Detection → Outreach Draft → HUMAN APPROVAL`

The runner generates a shared `trace_id`, keeps agent outputs structured, and never sends the outreach draft automatically.

## Phase 1

Phase 1 establishes the deterministic foundation for a lead-to-client workflow without scraping, sending messages, or performing external side effects.

### Lifecycle

`NEW → RESEARCHING → QUALIFIED → READY_FOR_OUTREACH → OUTREACH_PENDING_APPROVAL → CONTACTED → REPLIED → INTERESTED → MEETING_BOOKED → PROPOSAL_SENT → WON/LOST`

### Design principles

- Reuse existing Agency Agents instead of duplicating specialist prompts.
- Pass structured state between agents rather than raw conversation transcripts.
- Keep orchestration deterministic; agents produce decisions, but the state machine enforces valid transitions.
- External side effects require an explicit approval gate.
- Every agent invocation has a traceable run record.
- Failures degrade to a structured error state rather than silently disappearing.

## Agent mapping

| Workflow role | Agency Agent |
|---|---|
| Lead generation | `sales/sales-offer-lead-gen-strategist.md` |
| Outbound strategy | `sales/sales-outbound-strategist.md` |
| Discovery / qualification | `sales/sales-discovery-coach.md` |
| Deal strategy | `sales/sales-deal-strategist.md` |
| Technical scoping | `sales/sales-engineer.md` |
| Pipeline analysis | `sales/sales-pipeline-analyst.md` |
| Proposal | `sales/sales-proposal-strategist.md` |
| Multi-agent orchestration | `engineering/engineering-multi-agent-systems-architect.md` |
| Delivery architecture | `engineering/engineering-software-architect.md` |
| Backend delivery | `engineering/engineering-backend-architect.md` |

## Structure

```text
client-acquisition/
├── README.md
├── config/
│   └── agents.json
├── schemas/
│   ├── lead.schema.json
│   ├── research.schema.json
│   ├── outreach.schema.json
│   └── agent-run.schema.json
├── orchestrator/
│   ├── __init__.py
│   ├── models.py
│   ├── registry.py
│   ├── runner.py
│   ├── state_machine.py
│   └── workflow.py
├── cli.py
└── tests/
    ├── test_foundation.py
    └── test_runner.py
```

## Scope boundary

Phase 2 deliberately does **not** implement LinkedIn scraping, email sending, calendar booking, mass outreach, autonomous sales, or a dashboard. Those integrations should sit behind adapters after the state/contracts and execution layer are validated.
