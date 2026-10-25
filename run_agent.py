#!/usr/bin/env python3
"""
Autonomous AI Outreach Engine - Main CLI Entrypoint
===================================================
Run the multi-agent job search, screening, resume compilation, and outreach engine.

Examples:
  python run_agent.py --dry-run
  python run_agent.py --target 5 --dispatch-mode draft
  python run_agent.py --mode remote-jobs --target 3
  python run_agent.py --status
  python run_agent.py --setup
"""

import sys
import argparse
from pathlib import Path

# Add project root to PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from engine.config import (
    load_config,
    OUTREACH_MODE,
    TARGET_QUALIFIED,
    MAX_SCANS,
    DISPATCH_MODE,
    DRY_RUN
)
from engine.agents.orchestrator import OutreachOrchestrator

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(
        description="Autonomous AI Outreach Engine — Open Source Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  all               Scan both remote job boards and funded startup feeds (Default)
  remote-jobs       Scan only remote job boards (RemoteOK, Remotive, Jobicy, HN)
  funded-startups   Scan only venture-backed startups and AI funding announcements

Dispatch Options:
  draft             Safely create Gmail drafts with PDF resume attached (Recommended)
  send              Send live personalized outreach emails via Gmail SMTP
  dry-run           Compile resumes and craft emails without any external dispatch
        """
    )
    parser.add_argument(
        "--mode",
        choices=["all", "remote-jobs", "funded-startups"],
        default=OUTREACH_MODE or "all",
        help="Outreach sourcing mode (default: %(default)s)"
    )
    parser.add_argument(
        "--target",
        type=int,
        default=TARGET_QUALIFIED or 6,
        help="Target number of qualified applications to process (default: %(default)s)"
    )
    parser.add_argument(
        "--max-scans",
        type=int,
        default=MAX_SCANS or 50,
        help="Safety cap on total job leads evaluated (default: %(default)s)"
    )
    parser.add_argument(
        "--dispatch-mode",
        choices=["draft", "send", "dry-run"],
        default=None,
        help="Override dispatch mode (draft / send / dry-run)"
    )
    parser.add_argument(
        "--dispatch",
        action="store_true",
        help="Enable dispatch execution according to DISPATCH_MODE in .env"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without creating drafts, sending emails, or writing to Notion"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check connectivity and status of configured API services"
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Launch the interactive onboarding setup wizard"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Launch setup wizard if requested
    if args.setup:
        from engine.setup_wizard import main as run_wizard
        run_wizard()
        return

    # Run status check if requested
    if args.status:
        from engine.setup_wizard import print_status_summary
        print_status_summary()
        return

    # Check if configured; if not, suggest running setup
    cfg = load_config()
    if not cfg.groq_api_key and not cfg.openrouter_api_key:
        console.print("[bold red]No LLM API keys configured![/bold red]")
        console.print("Run [bold cyan]python setup.py[/bold cyan] to set up your free API keys in under 2 minutes.")
        sys.exit(1)

    # Determine dry-run status
    is_dry_run = args.dry_run or DRY_RUN
    if args.dispatch:
        is_dry_run = False

    active_dispatch_mode = args.dispatch_mode or cfg.dispatch_mode
    if is_dry_run:
        active_dispatch_mode = "dry-run"

    # Execute Autonomous Multi-Agent Outreach
    orchestrator = OutreachOrchestrator()
    report = orchestrator.run(
        mode=args.mode,
        target_qualified=args.target,
        max_scans=args.max_scans,
        dispatch_mode=active_dispatch_mode,
        dry_run=is_dry_run
    )

    if report.errors:
        console.print(f"[yellow]Completed with {len(report.errors)} non-fatal warnings.[/yellow]")
    else:
        console.print("[bold green]Autonomous outreach cycle completed successfully![/bold green]")


if __name__ == "__main__":
    main()
