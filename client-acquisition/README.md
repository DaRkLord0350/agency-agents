# Private Client Acquisition OS

This directory is a private operator layer around the existing Agency Agents repository. It is for local use by the owner, not a new agent marketplace or SaaS product.

## What we are building

```text
Prospect list
  -> evidence collection
  -> company research
  -> qualification
  -> pain detection
  -> personalized audit angle
  -> outreach draft
  -> HUMAN APPROVAL
  -> manual/approved sending
  -> reply/discovery
  -> proposal
  -> won client
```

The existing specialist markdown files remain the workforce. This layer supplies state, contracts, execution, tracing, local lead intake and approval boundaries.

## Current status

- Phase 1 foundation: complete
- Phase 2 executable deterministic runner: complete
- Phase 3 real model adapter + CSV lead intake: added on this same branch
- Network side effects: still disabled by default

## Local setup

No Python packages are required for the core runner. Use Python 3.10+.

Copy `.env.example` to `.env` and set an OpenAI-compatible provider if you want real model execution. The adapter expects a `/chat/completions` endpoint.

Required values:

```text
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-key
LLM_MODEL=your-model
```

Do not commit `.env` or API keys.

## Run a single lead

Demo mode (no network):

```bash
python client-acquisition/cli.py run-lead --name "Asha" --company "Acme" --email "asha@acme.test"
```

Real model mode:

```bash
python client-acquisition/cli.py run-lead --name "Asha" --company "Acme" --website "https://example.com" --evidence "Shopify store; hiring operations manager; Instagram profile URL"
```

Then add `--provider llm`.

## Run a lead CSV

Use `client-acquisition/data/leads.example.csv` as the template. Important columns are:

`company_name,contact_name,contact_email,website,source,evidence`

Run:

```bash
python client-acquisition/cli.py run-csv client-acquisition/data/leads.example.csv --provider demo
```

The CSV runner prints one JSON result per lead and never sends outreach.

## Evidence-first rule

The model must not invent company facts. Every research claim should be tied to supplied evidence. For live research, a future adapter can feed verified search/page evidence into the same context without changing the orchestration layer.

## Client strategy

The first offer is intentionally narrow: ecommerce/D2C operations automation. We look for businesses showing operational complexity (multiple channels, large catalogs, manual reporting, support/order workload, spreadsheet-heavy processes, or similar public signals) and sell a concrete business outcome rather than "AI agents".

The acquisition system should help create a small number of high-quality, evidence-backed conversations. Human approval remains mandatory before outbound communication.
