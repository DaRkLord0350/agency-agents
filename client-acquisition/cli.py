"""Command-line entry point for the phase-2 client-acquisition demo."""

import argparse
import json
import sys
from dataclasses import asdict

from orchestrator.models import Lead
from orchestrator.runner import AgentRunner, deterministic_demo_executor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Client Acquisition OS")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run-lead", help="run a lead through the safe local workflow")
    run.add_argument("--id", default=None, help="lead id")
    run.add_argument("--name", required=True, help="contact name")
    run.add_argument("--company", required=True, help="company name")
    run.add_argument("--email", default=None, help="contact email")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run-lead":
        lead = Lead(
            id=args.id or "demo-lead",
            name=args.name,
            company=args.company,
            email=args.email,
        )
        runner = AgentRunner(deterministic_demo_executor)
        result = runner.run_lead(lead)
        print(json.dumps(result, indent=2, default=str))
        print("\nHUMAN APPROVAL REQUIRED: outreach has been drafted but not sent.", file=sys.stderr)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
