import os
import re
import json
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

def clean_str(val: str) -> str:
    """Safely strips whitespace, quotes, and newlines from env strings."""
    if not val:
        return ""
    return str(val).strip().strip('"').strip("'").strip()

def clean_uuid(raw_id: str) -> str:
    """Normalizes 32-character hex Notion database IDs (or URLs) into valid dashed UUIDs."""
    if not raw_id:
        return ""
    s = clean_str(raw_id)
    # Check if a 32-character hex string exists (e.g. raw ID or embedded in Notion database URL)
    m = re.search(r'([a-fA-F0-9]{32})', s)
    if m:
        h = m.group(1)
        return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"
    # Check if already a dashed UUID
    m2 = re.search(r'([a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})', s)
    if m2:
        return m2.group(1)
    return s

# LLM Providers & Keys
OPENROUTER_API_KEY = clean_str(os.getenv("OPENROUTER_API_KEY", ""))
GROQ_API_KEY = clean_str(os.getenv("GROQ_API_KEY", ""))
LLM_PROVIDER = clean_str(os.getenv("LLM_PROVIDER", "AUTO")).upper()

# Verified Free Model Hierarchy on OpenRouter
OPENROUTER_FREE_MODELS = [
    "openrouter/free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "google/gemma-4-31b-it:free",
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "poolside/laguna-s-2.1:free",
    "google/gemma-4-26b-a4b-it:free",
    "cohere/north-mini-code-20260617:free"
]

# Groq High-Speed Models (14,400 free calls/day, ~0.8s latency)
GROQ_PRIMARY_MODEL = "openai/gpt-oss-120b"
GROQ_FALLBACK_MODEL = "openai/gpt-oss-20b"

# CRM & Email Credentials
NOTION_TOKEN = clean_str(os.getenv("NOTION_TOKEN", "") or os.getenv("NOTION_API_KEY", ""))
NOTION_API_KEY = NOTION_TOKEN
NOTION_DATABASE_ID = clean_uuid(os.getenv("NOTION_DATABASE_ID", ""))
GMAIL_USER = clean_str(os.getenv("GMAIL_USER", "") or os.getenv("GMAIL_SENDER", "") or os.getenv("EMAIL_USER", ""))
GMAIL_SENDER = GMAIL_USER
GMAIL_APP_PASSWORD = clean_str(os.getenv("GMAIL_APP_PASSWORD", "") or os.getenv("GMAIL_PASSWORD", "")).replace(" ", "")

# Search & Enrichment Keys
SERPER_API_KEY = clean_str(os.getenv("SERPER_API_KEY", ""))
APOLLO_API_KEY = clean_str(os.getenv("APOLLO_API_KEY", ""))

# Pipeline Parameters
DISPATCH_MODE = clean_str(os.getenv("DISPATCH_MODE", "GMAIL_DRAFT")).upper()
TARGET_QUALIFIED = int(os.getenv("TARGET_QUALIFIED", "6"))
MAX_SCANS = int(os.getenv("MAX_SCANS", "50"))
MIN_MATCH_SCORE = int(os.getenv("MIN_MATCH_SCORE", "65"))
OUTREACH_MODE = clean_str(os.getenv("OUTREACH_MODE", "all")).lower()

# Paths & Directories
CONFIG_DIR = BASE_DIR / "config"
TEMPLATES_DIR = BASE_DIR / "templates"
GENERATED_RESUMES_DIR = BASE_DIR / "generated_resumes"
GENERATED_RESUMES_DIR.mkdir(parents=True, exist_ok=True)

OFFSET_FILE = BASE_DIR / ".api_offset.json"
CACHE_FILE = BASE_DIR / ".seen_companies.json"
TARGET_STARTUPS_PATH = TEMPLATES_DIR / "target_startups.json"
TEMPLATE_PATH = TEMPLATES_DIR / "resume_template.typ"

# Load Candidate Profile
LOCAL_PROFILE_PATH = BASE_DIR / "profile_context.json"
PROFILE_PATH = CONFIG_DIR / "profile.json"
PROFILE_EXAMPLE_PATH = CONFIG_DIR / "profile.example.json"

if LOCAL_PROFILE_PATH.exists():
    with open(LOCAL_PROFILE_PATH, "r", encoding="utf-8") as f:
        MASTER_PROFILE = json.load(f)
elif PROFILE_PATH.exists():
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        MASTER_PROFILE = json.load(f)
elif PROFILE_EXAMPLE_PATH.exists():
    with open(PROFILE_EXAMPLE_PATH, "r", encoding="utf-8") as f:
        MASTER_PROFILE = json.load(f)
else:
    MASTER_PROFILE = {}

# Candidate Profile & Links (Supports both nested 'candidate' object and flat JSON)
CANDIDATE_DATA = MASTER_PROFILE.get("candidate", MASTER_PROFILE)
CANDIDATE_NAME = CANDIDATE_DATA.get("name") or CANDIDATE_DATA.get("candidate_name", "Job Applicant")
CANDIDATE_TITLE = CANDIDATE_DATA.get("title") or CANDIDATE_DATA.get("candidate_title", "Software Engineer")
CANDIDATE_PHONE = CANDIDATE_DATA.get("phone") or CANDIDATE_DATA.get("candidate_phone", "")
CANDIDATE_EMAIL = CANDIDATE_DATA.get("email") or CANDIDATE_DATA.get("candidate_email", GMAIL_USER)

CANDIDATE_LINKS = CANDIDATE_DATA.get("links", {})

def _resolve_resume_drive_url() -> str:
    # 1. Environment variable check across common aliases
    for key in ["RESUME_DRIVE_URL", "RESUME_URL", "DRIVE_RESUME_URL", "RESUME_LINK", "GOOGLE_DRIVE_RESUME"]:
        val = clean_str(os.getenv(key, ""))
        if val and "YOUR_GOOGLE_DRIVE_RESUME_ID" not in val and "YOUR_RESUME_ID" not in val and val.startswith("http"):
            return val

    # 2. Check profile links dictionary
    for key in ["resume_drive", "resume_google_drive", "resume"]:
        val = clean_str(CANDIDATE_LINKS.get(key, ""))
        if val and "YOUR_GOOGLE_DRIVE_RESUME_ID" not in val and "YOUR_RESUME_ID" not in val and val.startswith("http"):
            return val

    # 3. Canonical verified fallback
    return "https://drive.google.com/file/d/18kbu7pKjkYbaVGCq50BTCSFxtznOFUAT/view?usp=sharing"

RESUME_DRIVE_URL = _resolve_resume_drive_url()
PORTFOLIO_URL = clean_str(os.getenv("PORTFOLIO_URL", CANDIDATE_LINKS.get("portfolio", "")))
GITHUB_URL = clean_str(os.getenv("GITHUB_URL", CANDIDATE_LINKS.get("github", "")))
LINKEDIN_URL = clean_str(os.getenv("LINKEDIN_URL", CANDIDATE_LINKS.get("linkedin", "")))

DRY_RUN = clean_str(os.getenv("DRY_RUN", "false")).lower() in ("true", "1", "yes")

from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class AppConfig:
    groq_api_key: str = GROQ_API_KEY
    openrouter_api_key: str = OPENROUTER_API_KEY
    llm_provider: str = LLM_PROVIDER
    notion_api_key: str = NOTION_TOKEN or clean_str(os.getenv("NOTION_API_KEY", ""))
    notion_database_id: str = NOTION_DATABASE_ID
    gmail_sender: str = GMAIL_USER or clean_str(os.getenv("GMAIL_SENDER", ""))
    gmail_app_password: str = GMAIL_APP_PASSWORD
    serper_api_key: str = SERPER_API_KEY
    dispatch_mode: str = DISPATCH_MODE
    target_qualified: int = TARGET_QUALIFIED
    max_scans: int = MAX_SCANS
    min_match_score: int = MIN_MATCH_SCORE
    outreach_mode: str = OUTREACH_MODE
    dry_run: bool = DRY_RUN
    candidate_name: str = CANDIDATE_NAME
    candidate_title: str = CANDIDATE_TITLE
    candidate_email: str = CANDIDATE_EMAIL
    candidate_phone: str = CANDIDATE_PHONE
    target_roles: List[str] = field(default_factory=lambda: CANDIDATE_DATA.get("target_roles", ["Software Engineer", "AI Engineer"]))
    tech_skills: List[str] = field(default_factory=lambda: CANDIDATE_DATA.get("target_skills") or CANDIDATE_DATA.get("tech_skills", ["Python", "FastAPI"]))
    resume_drive_url: str = RESUME_DRIVE_URL
    portfolio_url: str = PORTFOLIO_URL
    github_url: str = GITHUB_URL
    linkedin_url: str = LINKEDIN_URL

def load_config() -> AppConfig:
    """Loads and returns an AppConfig instance with current environment and profile settings."""
    gmail_sender = clean_str(os.getenv("GMAIL_USER", "") or os.getenv("GMAIL_SENDER", "") or os.getenv("EMAIL_USER", "")) or GMAIL_USER
    gmail_app_password = clean_str(os.getenv("GMAIL_APP_PASSWORD", "") or os.getenv("GMAIL_PASSWORD", "")).replace(" ", "") or GMAIL_APP_PASSWORD
    notion_api_key = clean_str(os.getenv("NOTION_TOKEN", "") or os.getenv("NOTION_API_KEY", "")) or NOTION_TOKEN
    notion_database_id = clean_uuid(os.getenv("NOTION_DATABASE_ID", "")) or NOTION_DATABASE_ID
    groq_api_key = clean_str(os.getenv("GROQ_API_KEY", "")) or GROQ_API_KEY
    openrouter_api_key = clean_str(os.getenv("OPENROUTER_API_KEY", "")) or OPENROUTER_API_KEY
    serper_api_key = clean_str(os.getenv("SERPER_API_KEY", "")) or SERPER_API_KEY
    dispatch_mode = clean_str(os.getenv("DISPATCH_MODE", "")).upper() or DISPATCH_MODE
    dry_run = clean_str(os.getenv("DRY_RUN", "")).lower() in ("true", "1", "yes") if os.getenv("DRY_RUN") is not None else DRY_RUN

    return AppConfig(
        groq_api_key=groq_api_key,
        openrouter_api_key=openrouter_api_key,
        llm_provider=LLM_PROVIDER,
        notion_api_key=notion_api_key,
        notion_database_id=notion_database_id,
        gmail_sender=gmail_sender,
        gmail_app_password=gmail_app_password,
        serper_api_key=serper_api_key,
        dispatch_mode=dispatch_mode,
        target_qualified=TARGET_QUALIFIED,
        max_scans=MAX_SCANS,
        min_match_score=MIN_MATCH_SCORE,
        outreach_mode=OUTREACH_MODE,
        dry_run=dry_run,
        candidate_name=CANDIDATE_NAME,
        candidate_title=CANDIDATE_TITLE,
        candidate_email=gmail_sender or CANDIDATE_EMAIL,
        candidate_phone=CANDIDATE_PHONE,
        resume_drive_url=_resolve_resume_drive_url(),
        portfolio_url=PORTFOLIO_URL,
        github_url=GITHUB_URL,
        linkedin_url=LINKEDIN_URL
    )

