#!/usr/bin/env python3
"""
Autonomous AI Outreach Engine - Notion CRM Pending Dispatcher
=============================================================
Fetches pending applications from your Notion CRM database, uses AI + Web Search
to find missing emails (if needed), compiles tailored resumes, and dispatches via Gmail.

Usage:
  python dispatch_pending.py                    # Safely creates Gmail drafts for pending applications
  python dispatch_pending.py --send             # Sends live emails via Gmail SMTP
  python dispatch_pending.py --enrich-missing   # Runs AI web search to find emails for rows missing contact email
  python dispatch_pending.py --dry-run          # Verifies pending applications without external dispatch
"""

import sys
import argparse
from pathlib import Path

# Add project root to PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from engine.config import load_config, DISPATCH_MODE, CANDIDATE_NAME
from engine.state import JobLead, ContactInfo, FitEvaluation, ApplicationPackage
from engine.tools.notion_client import fetch_pending_notion_applications, update_notion_page
from engine.tools.email_client import create_gmail_draft, send_gmail_smtp
from engine.tools.resume_compiler import compile_tailored_resume
from engine.tools.email_verifier import verify_and_clean_email
from engine.agents.lead_enricher import EnrichmentAgent

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(description="Dispatch pending applications from Notion CRM")
    parser.add_argument("--send", action="store_true", help="Send live emails via SMTP instead of creating drafts")
    parser.add_argument("--enrich-missing", action="store_true", help="Run AI web search to discover missing emails")
    parser.add_argument("--dry-run", action="store_true", help="Simulate dispatch without sending or modifying Notion")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = load_config()

    console.print(Panel.fit(
        f"[bold cyan]AI Outreach Engine — Notion CRM Dispatcher[/bold cyan]\n"
        f"[yellow]Candidate:[/yellow] {cfg.candidate_name}\n"
        f"[yellow]Dispatch Mode:[/yellow] {'LIVE SEND' if args.send else ('DRY-RUN' if args.dry_run else 'DRAFT CREATION')}\n"
        f"[yellow]Auto-Enrich Missing Emails:[/yellow] {'Enabled' if args.enrich_missing else 'Disabled'}",
        border_style="cyan"
    ))

    if not cfg.notion_api_key or not cfg.notion_database_id:
        console.print("[bold red]Notion CRM credentials not configured in .env![/bold red]")
        console.print("Please run [cyan]python setup.py[/cyan] to connect your Notion database.")
        sys.exit(1)

    with console.status("[bold green]Querying Notion CRM for pending records...[/bold green]"):
        pending_rows = fetch_pending_notion_applications()

    if not pending_rows:
        console.print("[bold green]✓ No pending applications found in Notion CRM. All caught up![/bold green]")
        return

    console.print(f"Found [bold cyan]{len(pending_rows)}[/bold cyan] pending application(s) in Notion.\n")

    enricher = EnrichmentAgent() if args.enrich_missing else None
    table = Table(title="Pending Applications Dispatch", show_header=True, header_style="bold magenta")
    table.add_column("Company", style="bold")
    table.add_column("Role")
    table.add_column("Email", style="cyan")
    table.add_column("Action Taken", style="green")

    for item in pending_rows:
        company = item["company"]
        role = item["role"]
        email = item["email"]
        page_id = item["page_id"]
        email_text = item["email_text"]
        
        # 1. Enrich missing email if requested
        if not email and args.enrich_missing and enricher:
            console.print(f"Searching web intelligence for [bold]{company}[/bold] contact email...")
            lead = JobLead(company=company, role=role, url=item.get("job_url", ""))
            contact = enricher.enrich(lead)
            if contact.email:
                is_valid, clean_mail, _ = verify_and_clean_email(contact.email)
                if is_valid:
                    email = clean_mail
                    update_notion_page(page_id, {
                        "Contact Email": {"email": clean_mail},
                        "Target Contact": {"rich_text": [{"text": {"content": f"{contact.name} ({contact.title})"[:2000]}}]}
                    })
                    console.print(f"  [green]✓ Discovered & updated email for {company}: {clean_mail}[/green]")

        # 2. Check if email is ready
        if not email:
            table.add_row(company, role[:20], "[dim]Missing Email[/dim]", "[yellow]Skipped (No Email)[/yellow]")
            continue

        # 3. Parse Subject and Body from email_text
        subject = f"Software Engineering @ {company} - {cfg.candidate_name}"
        body = email_text
        if "Subject:" in email_text:
            parts = email_text.split("\n\n", 1)
            first_line = parts[0].replace("Subject:", "").strip()
            if first_line:
                subject = first_line
            if len(parts) > 1:
                body = parts[1]

        # 4. Generate/compile tailored resume PDF
        pdf_path = compile_tailored_resume(
            company_clean=company,
            role_title=role,
            tailored_bullets=[f"Targeted software engineering impact for {company}"]
        )

        # 5. Dispatch
        if args.dry_run:
            table.add_row(company, role[:20], email, "[cyan]Dry Run (Verified)[/cyan]")
            continue

        if args.send:
            ok, msg = send_gmail_smtp(
                to_email=email,
                subject=subject,
                body=body,
                attachment_path=pdf_path
            )
            if ok:
                update_notion_page(page_id, {"Dispatch Status": {"select": {"name": "Email Sent Live"}}})
                table.add_row(company, role[:20], email, "[green]Sent Live via SMTP[/green]")
            else:
                table.add_row(company, role[:20], email, f"[red]SMTP Failed: {msg[:25]}[/red]")
        else:
            ok, msg = create_gmail_draft(
                to_email=email,
                subject=subject,
                body=body,
                attachment_path=pdf_path
            )
            if ok:
                update_notion_page(page_id, {"Dispatch Status": {"select": {"name": "Draft Created in Gmail"}}})
                table.add_row(company, role[:20], email, "[green]Draft Created in Gmail[/green]")
            else:
                table.add_row(company, role[:20], email, f"[red]Draft Failed: {msg[:25]}[/red]")

    console.print("\n")
    console.print(table)
    console.print("\n[bold green]Dispatch operation complete![/bold green]")


if __name__ == "__main__":
    main()
