"""
Autonomous AI Outreach Engine - Interactive Setup Wizard
Guides new users through configuring Candidate Profile, LLM API keys, Notion CRM, and Gmail credentials.
"""

import os
import sys
import json
import smtplib
from pathlib import Path
from typing import Dict, Any, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import print as rprint
import requests

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
PROFILE_PATH = CONFIG_DIR / "profile.json"
PROFILE_EXAMPLE_PATH = CONFIG_DIR / "profile.example.json"
ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = CONFIG_DIR / "env.example"

BANNER = r"""[bold cyan]
   ___    ____   ____         __                       __       ______            _          
  /   |  /  _/  / __ \__  __/ /_________  ____ ______/ /_     / ____/___  ____ _(_)___  ___ 
 / /| |  / /   / / / / / / / __/ ___/ _ \/ __ `/ ___/ __ \   / __/ / __ \/ __ `/ / __ \/ _ \\
/ ___ |_/ /   / /_/ / /_/ / /_/ /  /  __/ /_/ / /__/ / / /  / /___/ / / / /_/ / / / / /  __/
/_/  |_/___/   \____/\__,_/\__/_/   \___/\__,_/\___/_/ /_/  /_____/_/ /_/\__, /_/_/ /_/\___/ 
                                                                        /____/               
[/bold cyan]
[bold white]Autonomous AI Job Search & Outreach Engine (100% Free-Tier Compatible)[/bold white]
"""

def check_system_deps() -> Dict[str, bool]:
    """Checks system and python dependencies."""
    results = {}
    
    # Python version
    results["Python 3.10+"] = sys.version_info >= (3, 10)
    
    # Typst
    try:
        import typst
        results["Typst (Python library)"] = True
    except ImportError:
        results["Typst (Python library)"] = False
        
    # Playwright
    try:
        import playwright
        results["Playwright"] = True
    except ImportError:
        results["Playwright"] = False
        
    return results


def verify_groq(api_key: str) -> Tuple[bool, str]:
    """Tests Groq API credentials."""
    if not api_key or api_key.startswith("gsk_placeholder") or len(api_key) < 15:
        return False, "Invalid or missing Groq API Key."
    try:
        res = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=8
        )
        if res.status_code == 200:
            return True, "Groq API Connected successfully (Free Tier Active)."
        return False, f"Groq Error HTTP {res.status_code}: {res.text[:120]}"
    except Exception as e:
        return False, f"Groq Connection failed: {e}"


def verify_openrouter(api_key: str) -> Tuple[bool, str]:
    """Tests OpenRouter API key."""
    if not api_key:
        return False, "Not configured (Optional fallback)."
    try:
        res = requests.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=8
        )
        if res.status_code == 200:
            return True, "OpenRouter API Connected successfully."
        return False, f"OpenRouter Error HTTP {res.status_code}: {res.text[:120]}"
    except Exception as e:
        return False, f"OpenRouter Connection failed: {e}"


def verify_serper(api_key: str) -> Tuple[bool, str]:
    """Tests Serper API key for web search."""
    if not api_key or len(api_key) < 10:
        return False, "Not configured (Engine will fall back to website crawling)."
    try:
        res = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": "test", "num": 1},
            timeout=8
        )
        if res.status_code == 200:
            return True, "Serper Google Search Connected (2,500 Free Queries)."
        return False, f"Serper Error HTTP {res.status_code}: {res.text[:120]}"
    except Exception as e:
        return False, f"Serper Connection failed: {e}"


def verify_notion(token: str, database_id: str) -> Tuple[bool, str]:
    """Tests Notion API connection and database access."""
    if not token or not database_id:
        return False, "Not configured (Engine will save to local CSV audit log)."
    
    clean_id = database_id.replace("-", "").strip()
    try:
        res = requests.get(
            f"https://api.notion.com/v1/databases/{clean_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28"
            },
            timeout=8
        )
        if res.status_code == 200:
            title = res.json().get("title", [{}])[0].get("plain_text", "Untitled")
            return True, f"Notion Database Connected: '{title}'"
        return False, f"Notion HTTP {res.status_code}: {res.json().get('message', res.text[:100])}"
    except Exception as e:
        return False, f"Notion Connection failed: {e}"


def verify_gmail(sender: str, app_password: str) -> Tuple[bool, str]:
    """Tests Gmail SMTP login."""
    if not sender or not app_password:
        return False, "Not configured (Drafts/Emails will be skipped)."
    clean_pwd = app_password.replace(" ", "").strip()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(sender.strip(), clean_pwd)
        return True, f"Gmail SMTP Authenticated for {sender}"
    except Exception as e:
        return False, f"Gmail Authentication failed: {e}"


def run_candidate_profile_wizard() -> Dict[str, Any]:
    """Interactive wizard to configure candidate profile."""
    console.print("\n[bold yellow]Step 1: Candidate Profile Configuration[/bold yellow]")
    console.print("This information is used to match jobs, craft personalized cold emails, and dynamically compile your resume PDF.")

    profile_data: Dict[str, Any] = {}
    if PROFILE_PATH.exists():
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                profile_data = json.load(f)
            if Confirm.ask(f"[cyan]Existing profile found for '{profile_data.get('candidate_name', 'User')}'. Keep existing data?[/cyan]", default=True):
                return profile_data
        except Exception:
            pass
    elif PROFILE_EXAMPLE_PATH.exists():
        try:
            with open(PROFILE_EXAMPLE_PATH, "r", encoding="utf-8") as f:
                profile_data = json.load(f)
        except Exception:
            profile_data = {}

    name = Prompt.ask("Your Full Name", default=profile_data.get("candidate_name", "Jane Doe"))
    email = Prompt.ask("Your Primary Email", default=profile_data.get("candidate_email", "jane.doe@example.com"))
    phone = Prompt.ask("Your Phone (Optional)", default=profile_data.get("candidate_phone", ""))
    location = Prompt.ask("Your Location / Timezone", default=profile_data.get("candidate_location", "San Francisco, CA (Remote)"))
    
    roles_str = Prompt.ask(
        "Target Roles (comma-separated)",
        default=", ".join(profile_data.get("target_roles", ["Software Engineer", "Full Stack Engineer", "AI Engineer"]))
    )
    target_roles = [r.strip() for r in roles_str.split(",") if r.strip()]
    
    max_exp = int(Prompt.ask("Max Years of Experience (for screening filter)", default=str(profile_data.get("max_experience_years", 3))))
    
    skills_str = Prompt.ask(
        "Core Skills & Technologies (comma-separated)",
        default=", ".join(profile_data.get("tech_skills", ["Python", "FastAPI", "React", "TypeScript", "PostgreSQL", "Docker"]))
    )
    tech_skills = [s.strip() for s in skills_str.split(",") if s.strip()]
    
    linkedin = Prompt.ask("LinkedIn Profile URL", default=profile_data.get("links", {}).get("linkedin", "https://linkedin.com/in/yourprofile"))
    github = Prompt.ask("GitHub Profile URL", default=profile_data.get("links", {}).get("github", "https://github.com/yourprofile"))
    portfolio = Prompt.ask("Portfolio / Website URL", default=profile_data.get("links", {}).get("portfolio", "https://yourportfolio.dev"))
    drive_resume = Prompt.ask(
        "Public Google Drive link to Original Master Resume (View-Only)",
        default=profile_data.get("links", {}).get("resume_google_drive", "https://drive.google.com/file/d/YOUR_RESUME_ID/view")
    )
    
    highlights = Prompt.ask(
        "Key Accomplishment / Summary (1-2 sentences)",
        default=profile_data.get("experience_highlights", "Engineered scalable cloud services and full-stack AI workflows.")
    )

    full_profile = {
        "candidate_name": name,
        "candidate_email": email,
        "candidate_phone": phone,
        "candidate_location": location,
        "target_roles": target_roles,
        "max_experience_years": max_exp,
        "tech_skills": tech_skills,
        "experience_highlights": highlights,
        "links": {
            "linkedin": linkedin,
            "github": github,
            "portfolio": portfolio,
            "resume_google_drive": drive_resume
        }
    }

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(full_profile, f, indent=2)

    console.print(f"[bold green]✓ Candidate profile saved to {PROFILE_PATH}[/bold green]\n")
    return full_profile


def run_env_wizard():
    """Interactive wizard to configure API credentials and generate .env."""
    console.print("[bold yellow]Step 2: API Credentials & Outreach Services[/bold yellow]")
    console.print("The engine works out-of-the-box with 100% Free Tier API accounts.")

    current_env = {}
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    current_env[k.strip()] = v.strip().strip("'\"")

    # Groq API Key
    console.print("\n[bold cyan]1. LLM Reasoning Engine (Groq)[/bold cyan]")
    console.print("Provides 14,400 free daily requests with Llama-3.3-70b & GPT-OSS models.")
    console.print("Get your free key at: [underline]https://console.groq.com/keys[/underline]")
    groq_key = Prompt.ask(
        "Groq API Key",
        default=current_env.get("GROQ_API_KEY", "")
    )
    if groq_key:
        ok, msg = verify_groq(groq_key)
        if ok:
            console.print(f"[green]✓ {msg}[/green]")
        else:
            console.print(f"[red]✗ {msg}[/red]")

    # OpenRouter API Key (Optional)
    console.print("\n[bold cyan]2. LLM Fallback Engine (OpenRouter - Optional)[/bold cyan]")
    console.print("Used as automated failover if Groq rate limits are reached.")
    console.print("Get your key at: [underline]https://openrouter.ai/keys[/underline]")
    openrouter_key = Prompt.ask(
        "OpenRouter API Key (press Enter to skip)",
        default=current_env.get("OPENROUTER_API_KEY", "")
    )
    if openrouter_key:
        ok, msg = verify_openrouter(openrouter_key)
        if ok:
            console.print(f"[green]✓ {msg}[/green]")
        else:
            console.print(f"[yellow]! {msg}[/yellow]")

    # Serper API Key (Optional)
    console.print("\n[bold cyan]3. Web Intelligence & Email Discovery (Serper)[/bold cyan]")
    console.print("Provides 2,500 free Google searches to find founder/recruiter emails.")
    console.print("Get your free key at: [underline]https://serper.dev[/underline]")
    serper_key = Prompt.ask(
        "Serper API Key (press Enter to skip)",
        default=current_env.get("SERPER_API_KEY", "")
    )
    if serper_key:
        ok, msg = verify_serper(serper_key)
        if ok:
            console.print(f"[green]✓ {msg}[/green]")
        else:
            console.print(f"[yellow]! {msg}[/yellow]")

    # Notion CRM
    console.print("\n[bold cyan]4. Notion Application CRM (Optional)[/bold cyan]")
    console.print("Logs applications, tracking status, and contact emails in a Notion database.")
    notion_token = Prompt.ask(
        "Notion Internal Integration Secret (press Enter to skip)",
        default=current_env.get("NOTION_API_KEY", "")
    )
    notion_db = ""
    if notion_token:
        notion_db = Prompt.ask(
            "Notion Database ID or URL",
            default=current_env.get("NOTION_DATABASE_ID", "")
        )
        ok, msg = verify_notion(notion_token, notion_db)
        if ok:
            console.print(f"[green]✓ {msg}[/green]")
        else:
            console.print(f"[yellow]! {msg}[/yellow]")

    # Gmail SMTP / IMAP
    console.print("\n[bold cyan]5. Gmail Outreach & Drafts[/bold cyan]")
    console.print("Requires a Google Account 'App Password' (not your standard login password).")
    console.print("Create one at: [underline]https://myaccount.google.com/apppasswords[/underline]")
    gmail_sender = Prompt.ask(
        "Gmail Address (e.g. user@gmail.com)",
        default=current_env.get("GMAIL_SENDER", "")
    )
    gmail_pass = ""
    if gmail_sender:
        gmail_pass = Prompt.ask(
            "Gmail 16-Character App Password",
            default=current_env.get("GMAIL_APP_PASSWORD", "")
        )
        ok, msg = verify_gmail(gmail_sender, gmail_pass)
        if ok:
            console.print(f"[green]✓ {msg}[/green]")
        else:
            console.print(f"[yellow]! {msg}[/yellow]")

    # Dispatch Mode
    console.print("\n[bold cyan]6. Safety & Dispatch Preferences[/bold cyan]")
    console.print("Mode choices:")
    console.print("  • [bold green]draft[/bold green]: Creates drafts in Gmail for you to inspect & 1-click send (Safest & Recommended)")
    console.print("  • [bold red]send[/bold red]: Sends personalized emails directly via SMTP")
    console.print("  • [bold blue]dry-run[/bold blue]: Performs matching & resume compilation with zero external actions")
    
    dispatch_mode = Prompt.ask(
        "Choose dispatch mode (draft / send / dry-run)",
        choices=["draft", "send", "dry-run"],
        default=current_env.get("DISPATCH_MODE", "draft")
    )

    env_content = f"""# =====================================================================
# Autonomous AI Outreach Engine - Environment Configuration
# =====================================================================

# --- LLM API Configuration (100% Free Tier Available) ---
GROQ_API_KEY={groq_key}
GROQ_MODEL=openai/gpt-oss-120b
OPENROUTER_API_KEY={openrouter_key}
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

# --- Web Intelligence & Lead Enrichment ---
SERPER_API_KEY={serper_key}

# --- Notion CRM Integration ---
NOTION_API_KEY={notion_token}
NOTION_DATABASE_ID={notion_db}

# --- Email Outreach Configuration (Gmail SMTP & IMAP) ---
GMAIL_SENDER={gmail_sender}
GMAIL_APP_PASSWORD={gmail_pass}

# --- Dispatch Mode & Safety Settings ---
DISPATCH_MODE={dispatch_mode}
DRY_RUN={"true" if dispatch_mode == "dry-run" else "false"}
DAILY_APPLICATION_LIMIT=20
SCREENER_MIN_SCORE=65
"""

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(env_content)

    console.print(f"\n[bold green]✓ Environment file written successfully to {ENV_PATH}[/bold green]\n")


def print_status_summary():
    """Prints a verified service status table."""
    from engine.config import load_config
    cfg = load_config()

    table = Table(title="AI Outreach Engine - Service Diagnostics", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan", width=24)
    table.add_column("Status", width=14)
    table.add_column("Details", style="dim")

    # Groq
    if cfg.groq_api_key:
        ok, msg = verify_groq(cfg.groq_api_key)
        table.add_row("LLM Engine (Groq)", "[green]Connected[/green]" if ok else "[red]Error[/red]", msg)
    else:
        table.add_row("LLM Engine (Groq)", "[red]Missing[/red]", "Required for job screening and email crafting")

    # OpenRouter
    if cfg.openrouter_api_key:
        ok, msg = verify_openrouter(cfg.openrouter_api_key)
        table.add_row("LLM Fallback", "[green]Connected[/green]" if ok else "[yellow]Failed[/yellow]", msg)
    else:
        table.add_row("LLM Fallback", "[dim]Disabled[/dim]", "Optional secondary LLM failover")

    # Serper
    if cfg.serper_api_key:
        ok, msg = verify_serper(cfg.serper_api_key)
        table.add_row("Web Search (Serper)", "[green]Connected[/green]" if ok else "[yellow]Failed[/yellow]", msg)
    else:
        table.add_row("Web Search (Serper)", "[yellow]Crawler Only[/yellow]", "Serper missing; falls back to direct website crawling")

    # Notion
    if cfg.notion_api_key and cfg.notion_database_id:
        ok, msg = verify_notion(cfg.notion_api_key, cfg.notion_database_id)
        table.add_row("Notion CRM", "[green]Connected[/green]" if ok else "[yellow]Failed[/yellow]", msg)
    else:
        table.add_row("Notion CRM", "[dim]Disabled[/dim]", "Using local CSV audit log at data/applications.csv")

    # Gmail
    if cfg.gmail_sender and cfg.gmail_app_password:
        ok, msg = verify_gmail(cfg.gmail_sender, cfg.gmail_app_password)
        table.add_row("Gmail SMTP/IMAP", "[green]Authenticated[/green]" if ok else "[red]Auth Failed[/red]", f"Mode: {cfg.dispatch_mode.upper()}")
    else:
        table.add_row("Gmail SMTP/IMAP", "[yellow]Not Configured[/yellow]", "Live sending and draft creation disabled")

    # Resume Engine
    try:
        import typst
        table.add_row("Typst PDF Compiler", "[green]Available[/green]", "Universal resume engine loaded")
    except ImportError:
        table.add_row("Typst PDF Compiler", "[yellow]Fallback[/yellow]", "Install 'typst' python package or binary")

    console.print(table)


def main():
    """Main setup entrypoint."""
    console.print(BANNER)
    console.print(Panel(
        "[bold white]Welcome to the Autonomous AI Outreach Engine Setup Wizard![/bold white]\n"
        "This tool will guide you through setting up your candidate profile and free API services in under 2 minutes.",
        title="Quickstart Setup",
        border_style="cyan"
    ))

    # Step 1: Profile
    run_candidate_profile_wizard()

    # Step 2: Environment
    run_env_wizard()

    # Step 3: Diagnostics
    console.print("[bold yellow]Step 3: Verifying Services & Connectivity...[/bold yellow]\n")
    print_status_summary()

    console.print("\n[bold green]Setup Complete! You're ready to run outreach.[/bold green]")
    console.print("\n[bold cyan]Quick Commands:[/bold cyan]")
    console.print("  • [white]python run_agent.py --dry-run[/white]         (Safe test run: scans, matches, crafts without emailing)")
    console.print("  • [white]python run_agent.py --target 10[/white]        (Runs multi-platform funnel until 10 target leads are found)")
    console.print("  • [white]python run_agent.py --dispatch[/white]         (Dispatches drafts / emails according to DISPATCH_MODE)")
    console.print("  • [white]python dispatch_pending.py[/white]            (Scans Notion for 'Pending' rows and dispatches emails)\n")


if __name__ == "__main__":
    if "--status" in sys.argv or "--verify-only" in sys.argv:
        print_status_summary()
    else:
        main()
