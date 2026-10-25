import json
import time
import logging
from typing import List, Set, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from engine.state import JobLead, ApplicationPackage, PipelineReport
from engine.config import (
    CACHE_FILE,
    DISPATCH_MODE,
    OFFSET_FILE,
    MIN_MATCH_SCORE,
    CANDIDATE_NAME,
    CANDIDATE_TITLE,
    OUTREACH_MODE,
    TARGET_QUALIFIED,
    MAX_SCANS
)
from engine.tools.notion_client import get_existing_notion_companies
from engine.tools.alerter import send_error_alert
from engine.agents.job_scout import JobScoutAgent
from engine.agents.startup_scout import FundedStartupAgent
from engine.agents.screener import ScreenerAgent
from engine.agents.lead_enricher import EnrichmentAgent
from engine.agents.crafter import ApplicationCrafterAgent
from engine.agents.dispatcher import DispatchAgent

console = Console()
logger = logging.getLogger("OutreachOrchestrator")

class OutreachOrchestrator:
    """
    Supervisor Agent coordinating the full autonomous lifecycle:
    Discovery -> Screening -> Enrichment -> Tailoring & PDF -> Dispatch -> Notion CRM.
    Gathers a 20x Candidate Funnel, filters strictly for role & seniority fit,
    sorts newest postings first, and permanently records all evaluated companies.
    """

    def __init__(self):
        self.job_scout = JobScoutAgent()
        self.startup_scout = FundedStartupAgent()
        self.screener = ScreenerAgent()
        self.enricher = EnrichmentAgent()
        self.crafter = ApplicationCrafterAgent()
        self.dispatcher = DispatchAgent()
        self.seen_companies: Set[str] = set()

    def _persist_cache(self):
        """Immediately writes all seen/evaluated companies to disk so state is never lost."""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(sorted(list(self.seen_companies)), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist cache file: {e}")

    def run(
        self,
        mode: str = "all",
        target_qualified: int = 6,
        max_scans: int = 50,
        dispatch_mode: Optional[str] = None,
        dry_run: bool = False
    ) -> PipelineReport:
        """
        Executes the autonomous agent outreach cycle with a 20x candidate funnel.
        1. Gathers fresh candidate leads matching candidate profile.
        2. Sorts candidates by timestamp descending (newest first).
        3. Sequentially screens, enriches, crafts Typst PDF resumes, and dispatches.
        4. Permanently caches every evaluated company to eliminate duplicate re-evaluations.
        """
        report = PipelineReport()
        active_dispatch_mode = dispatch_mode or DISPATCH_MODE
        packages: List[ApplicationPackage] = []

        pool_target = max(30, target_qualified * 20)

        console.print(Panel.fit(
            f"[bold cyan]AI Outreach Engine — Autonomous Multi-Agent System[/bold cyan]\n"
            f"[yellow]Candidate:[/yellow] {CANDIDATE_NAME} ({CANDIDATE_TITLE})\n"
            f"[yellow]Mode:[/yellow] {mode} | [yellow]Target Qualified Applications:[/yellow] {target_qualified}\n"
            f"[yellow]20x Funnel Sourcing Goal:[/yellow] {pool_target} fresh candidate leads | [yellow]Safety Cap:[/yellow] Max {max_scans} scans\n"
            f"[yellow]Dispatch Mode:[/yellow] {'DRY-RUN' if dry_run else active_dispatch_mode}",
            border_style="cyan"
        ))

        # Step 1: Deduplication Ledger Initialization (Notion + Local Ledger)
        try:
            with console.status("[bold green]Loading already-contacted companies from Notion and ledger...[/bold green]"):
                notion_companies = get_existing_notion_companies()
                self.seen_companies = {c.strip().lower() for c in notion_companies if c}
                if CACHE_FILE.exists():
                    try:
                        with open(CACHE_FILE, "r", encoding="utf-8") as f:
                            cached = json.load(f)
                            self.seen_companies.update(c.strip().lower() for c in cached if c)
                    except Exception:
                        pass
                self._persist_cache()
                console.print(f"Loaded [bold]{len(self.seen_companies)}[/bold] total seen/contacted companies in ledger.")
        except Exception as e:
            err_msg = f"Failed to initialize Notion deduplication cache: {e}"
            logger.error(err_msg)
            send_error_alert("Notion Cache Failure", err_msg)

        # Step 2: 20x Candidate Funnel Sourcing
        candidate_pool: List[JobLead] = []
        pool_seen: Set[str] = set()
        discovery_round = 0
        max_discovery_rounds = 5

        console.rule(f"[bold green]Phase 1: Sourcing Candidate Pool ({pool_target} profile-aligned leads)[/bold green]")

        try:
            while len(candidate_pool) < pool_target and discovery_round < max_discovery_rounds:
                round_num = discovery_round + 1
                needed = pool_target - len(candidate_pool)
                batch_limit = max(20, needed)
                new_in_round = 0

                console.print(f"[cyan]Discovery Round {round_num}:[/cyan] Current pool: {len(candidate_pool)}/{pool_target} leads...")

                if mode in ("all", "remote-jobs"):
                    with console.status(f"[cyan]Sourcing remote engineering jobs (Round {round_num})...[/cyan]"):
                        j_leads = self.job_scout.run(
                            limit=batch_limit // 2 if mode == "all" else batch_limit,
                            seen_companies=self.seen_companies.union(pool_seen),
                            page_offset=discovery_round
                        )
                        for lead in j_leads:
                            ck = lead.company.strip().lower()
                            if ck not in self.seen_companies and ck not in pool_seen:
                                candidate_pool.append(lead)
                                pool_seen.add(ck)
                                new_in_round += 1
                                report.remote_jobs_count += 1

                if mode in ("all", "funded-startups"):
                    with console.status(f"[magenta]Sourcing newly funded startups (Round {round_num})...[/magenta]"):
                        s_leads = self.startup_scout.run(
                            limit=batch_limit // 2 if mode == "all" else batch_limit,
                            seen_companies=self.seen_companies.union(pool_seen),
                            page_offset=discovery_round
                        )
                        for lead in s_leads:
                            ck = lead.company.strip().lower()
                            if ck not in self.seen_companies and ck not in pool_seen:
                                candidate_pool.append(lead)
                                pool_seen.add(ck)
                                new_in_round += 1
                                report.funded_startups_count += 1

                console.print(f"Round {round_num} Result: Added {new_in_round} fresh leads. Total gathered: {len(candidate_pool)}/{pool_target}.")

                if new_in_round == 0:
                    console.print("[yellow]All available fresh remote jobs & funded startup sources reached for this run.[/yellow]")
                    break

                discovery_round += 1

        except Exception as e:
            logger.error(f"Error during discovery phase: {e}")

        # Step 3: Chronological Sorting (NEWEST / LATEST POSTED FIRST)
        candidate_pool.sort(key=lambda x: x.timestamp, reverse=True)
        console.print(Panel(
            f"[bold green]Funnel Sourcing Complete![/bold green]\n"
            f"Collected [bold]{len(candidate_pool)}[/bold] fresh candidates matching profile.\n"
            f"Prioritized chronologically: [bold cyan]Latest postings evaluated first[/bold cyan].",
            title="Candidate Funnel Status",
            border_style="green"
        ))

        # Step 4: Agentic System Execution (Screener -> Enricher -> Crafter -> Dispatcher)
        console.rule(f"[bold green]Phase 2: Agentic Pipeline Processing (Target: {target_qualified} actionable applications with email)[/bold green]")
        total_evaluated = 0

        try:
            for lead in candidate_pool:
                if report.contactable_count >= target_qualified:
                    console.print(f"\n[bold green]🎯 Target goal reached: {report.contactable_count} actionable applications with email processed![/bold green]")
                    break

                if total_evaluated >= max_scans:
                    console.print(f"\n[yellow]API safety cap reached ({max_scans} evaluations). Stopping to protect free tier limits.[/yellow]")
                    break

                total_evaluated += 1
                ck = lead.company.strip().lower()

                console.print(f"\n[bold cyan]Evaluating [{total_evaluated}/{len(candidate_pool)}]:[/bold cyan] {lead.company} ({lead.role}) — {lead.source_channel}")

                # Agent 2: Screener
                fit = self.screener.screen(lead)
                console.print(f"  [Screener] Match Score: [bold]{fit.match_score}/100[/bold] | Qualified: {'[green]YES[/green]' if fit.qualified else '[red]NO[/red]'}")
                console.print(f"  [Screener] Angle: [yellow]{fit.selected_angle}[/yellow] | Reasoning: {fit.fit_reasoning}")

                # Record company to deduplication ledger immediately
                self.seen_companies.add(ck)
                self._persist_cache()

                if not fit.qualified:
                    report.screened_out_count += 1
                    continue

                report.qualified_count += 1

                # Agent 3: Lead Enricher
                with console.status("  [bold green][LeadEnricher] Searching contact intelligence...[/bold green]"):
                    contact = self.enricher.enrich(lead)

                has_email = bool(contact.email and contact.email.strip())
                email_display = f"[green]{contact.email}[/green]" if has_email else "[yellow]No Direct Email Found (Will save to CRM & continue search)[/yellow]"
                console.print(f"  [Enricher] Recipient: [bold]{contact.name}[/bold] ({contact.title}) | Email: {email_display}")
                console.print(f"  [Enricher] Source: {contact.enrichment_source}")

                # Agent 4: Application Crafter
                with console.status("  [bold magenta][Crafter] Generating tailored pitch & compiling Typst PDF resume...[/bold magenta]"):
                    pkg = self.crafter.craft(lead, contact, fit)

                console.print(f"  [Crafter] Subject: [bold]{pkg.cold_email_subject}[/bold]")
                console.print(f"  [Crafter] Typst PDF Resume: [green]{pkg.pdf_resume_path}[/green]")

                # Agent 5: Dispatcher
                if dry_run:
                    if has_email:
                        pkg.dispatch_status = "Dry Run (Verified Email)"
                        console.print("  [Dispatcher] [yellow]DRY-RUN mode active: Verified email present, skipping external dispatch.[/yellow]")
                    else:
                        pkg.dispatch_status = "Dry Run (Missing Email)"
                        console.print("  [Dispatcher] [yellow]DRY-RUN mode active: No direct email found.[/yellow]")
                else:
                    with console.status("  [bold blue][Dispatcher] Executing dispatch and Notion CRM sync...[/bold blue]"):
                        pkg = self.dispatcher.dispatch(pkg, override_mode=active_dispatch_mode)
                    console.print(f"  [Dispatcher] Status: [bold green]{pkg.dispatch_status}[/bold green]")
                    if pkg.notion_page_id:
                        report.notion_synced_count += 1

                packages.append(pkg)
                report.dispatched_count += 1

                if has_email:
                    report.contactable_count += 1
                    console.print(f"  [bold green]✓ Actionable application {report.contactable_count}/{target_qualified} completed.[/bold green]")
                else:
                    report.missing_email_count += 1
                    console.print(f"  [dim yellow]ℹ Saved qualified lead to CRM/ledger (no email). Continuing scan towards target goal ({report.contactable_count}/{target_qualified})...[/dim yellow]")

                time.sleep(1)

        except Exception as e:
            err_msg = f"Critical pipeline failure: {e}"
            logger.error(err_msg, exc_info=True)
            report.errors.append(str(e))
            send_error_alert("Pipeline Runtime Error", err_msg)

        # Final Summary Table
        console.print("\n")
        console.rule("[bold cyan]Execution Summary[/bold cyan]")
        table = Table(title="Outreach Pipeline Results", show_header=True, header_style="bold magenta")
        table.add_column("Company", style="bold")
        table.add_column("Role")
        table.add_column("Score")
        table.add_column("Recipient")
        table.add_column("Email")
        table.add_column("Dispatch Status")

        for p in packages:
            table.add_row(
                p.company_clean_name,
                p.lead.role[:25],
                str(p.fit.match_score),
                p.contact.name[:20],
                p.contact.email or "[dim]None[/dim]",
                p.dispatch_status[:35]
            )

        console.print(table)
        console.print(f"\nTotal Fresh Leads Sourced: [bold]{len(candidate_pool)}[/bold]")
        console.print(f"Applications Qualified: [bold green]{report.qualified_count}[/bold green] | Screened Out: [bold yellow]{report.screened_out_count}[/bold yellow]")
        console.print(f"Actionable (With Email): [bold green]{report.contactable_count}[/bold green] | Missing Email: [bold yellow]{report.missing_email_count}[/bold yellow]")
        console.print(f"Applications Dispatched/Logged: [bold green]{report.dispatched_count}[/bold green] | Notion Synced: [bold green]{report.notion_synced_count}[/bold green]")

        return report
