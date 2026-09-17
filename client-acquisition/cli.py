"""CLI for the private client-acquisition workflow."""

import argparse
import json
import os
import sys
from pathlib import Path

from lead_engine.csv_loader import load_leads
from orchestrator.models import Lead
from orchestrator.runner import AgentRunner, deterministic_demo_executor
from orchestrator.llm_executor import LLMExecutor
from providers.openai_compatible import OpenAICompatibleProvider

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_runner(provider_name: str) -> AgentRunner:
    if provider_name == "demo":
        return AgentRunner(deterministic_demo_executor)
    if provider_name == "llm":
        load_dotenv()
        provider = OpenAICompatibleProvider.from_env()
        return AgentRunner(LLMExecutor(ROOT, provider))
    raise ValueError(f"Unknown provider: {provider_name}")


def add_lead_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--id", default=None, help="lead id")
    parser.add_argument("--name", default=None, help="contact name")
    parser.add_argument("--company", required=True, help="company name")
    parser.add_argument("--email", default=None, help="contact email")
    parser.add_argument("--website", default=None, help="company website")
    parser.add_argument("--evidence", default="", help="verified evidence to pass to the agents")
    parser.add_argument("--source", default="manual", help="lead source")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Private Client Acquisition OS")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run-lead", help="run one lead")
    add_lead_args(run)
    run.add_argument("--provider", choices=["demo", "llm"], default="demo")

    batch = sub.add_parser("run-csv", help="run a CSV of leads")
    batch.add_argument("path", help="CSV path")
    batch.add_argument("--provider", choices=["demo", "llm"], default="demo")
    return parser


def lead_from_args(args) -> Lead:
    kwargs = {
        "company_name": args.company,
        "contact_name": args.name,
        "contact_email": args.email,
        "website": args.website,
        "source": args.source,
        "metadata": {"evidence": args.evidence} if args.evidence else {},
    }
    if args.id:
        kwargs["id"] = args.id
    return Lead(**kwargs)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        runner = build_runner(args.provider)
        if args.command == "run-lead":
            result = runner.run_lead(lead_from_args(args))
            print(json.dumps(result, indent=2, default=str))
            print("\nHUMAN APPROVAL REQUIRED: outreach has been drafted but not sent.", file=sys.stderr)
            return 0

        if args.command == "run-csv":
            leads = load_leads(Path(args.path))
            for lead in leads:
                result = runner.run_lead(lead)
                print(json.dumps(result, default=str))
                print(f"Processed {lead.company_name}: {result['status']}", file=sys.stderr)
            return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
