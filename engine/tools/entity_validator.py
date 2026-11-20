import os
import re
import shutil
import logging
import subprocess
import urllib.parse
from typing import Optional, Tuple, Dict, Any, Set
import requests

from engine.tools.email_verifier import does_domain_exist, does_domain_have_mx

logger = logging.getLogger("EntityValidator")

# Generic route segments and UI elements on GitHub to block
GITHUB_BLOCKED_ROUTES: Set[str] = {
    "explore", "trending", "rules", "settings", "topics", "collections",
    "features", "site", "events", "about", "pricing", "login", "signup",
    "security", "pulls", "issues", "actions", "projects", "wiki", "pulse",
    "discussions", "releases", "tags", "commit", "commits", "blob", "tree",
    "raw", "plugins", "marketplace", "sponsors", "readme", "license",
    "insights", "network", "stargazers", "watchers", "forks", "community",
    "notifications", "organizations", "search", "stars", "account",
    "dashboard", "new", "orgs", "repositories", "security-advisories",
    "codespaces", "contact", "support", "customer-stories", "enterprise",
    "team", "premium_support", "solutions", "open-source", "repo", "cursor"
}

# Generic words or scraped navigation breadcrumbs that are not company entities
GENERIC_INVALID_COMPANY_NAMES: Set[str] = {
    "explore", "trending", "repo rules", "rules", "plugins", "collections",
    "features", "settings", "topics", "actions", "issues", "pulls", "discussions",
    "marketplace", "sponsors", "wiki", "projects", "events", "about", "pricing",
    "security", "open source", "good first issue", "up for grabs", "home",
    "login", "signup", "search", "overview", "documentation", "docs",
    "repository", "repositories", "cursor plugins", "readme", "license",
    "github", "github explore", "github trending"
}

# Free sub-path hosts, code repositories, or aggregator domains that do NOT qualify as custom company domains
FREE_HOSTING_AND_AGGREGATOR_DOMAINS: Set[str] = {
    "github.com", "gitlab.com", "bitbucket.org", "github.io", "gitlab.io",
    "pages.dev", "vercel.app", "netlify.app", "herokuapp.com", "glitch.me",
    "render.com", "surge.sh", "firebaseapp.com", "web.app", "ycombinator.com",
    "ossean.com", "opensourcestartups.com", "unicornscreener.vc",
    "goodfirstissue.dev", "up-for-grabs.net", "techcrunch.com", "news.ycombinator.com"
}

_CACHED_GITHUB_TOKEN: Optional[str] = None
_GITHUB_TOKEN_CHECKED: bool = False
_REPO_METADATA_CACHE: Dict[str, Tuple[bool, Optional[Dict[str, Any]], str]] = {}
_GITHUB_SESSION: Optional[requests.Session] = None

def get_github_session() -> requests.Session:
    global _GITHUB_SESSION
    if _GITHUB_SESSION is None:
        _GITHUB_SESSION = requests.Session()
    return _GITHUB_SESSION


def get_github_token() -> Optional[str]:
    """Retrieves an active GitHub personal access token for GitHub API queries."""
    global _CACHED_GITHUB_TOKEN, _GITHUB_TOKEN_CHECKED
    if _GITHUB_TOKEN_CHECKED:
        return _CACHED_GITHUB_TOKEN

    _GITHUB_TOKEN_CHECKED = True
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        _CACHED_GITHUB_TOKEN = token.strip()
        return _CACHED_GITHUB_TOKEN

    # Fall back to GitHub CLI if installed and authenticated
    gh_path = shutil.which("gh")
    if gh_path:
        try:
            res = subprocess.run([gh_path, "auth", "token"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                _CACHED_GITHUB_TOKEN = res.stdout.strip()
                return _CACHED_GITHUB_TOKEN
        except Exception:
            pass

    return None


def is_blocked_github_slug(owner: str, repo: str) -> bool:
    """Checks if an owner/repo pair is a blocked route, UI path, or navigation segment."""
    o_lower = owner.strip().lower()
    r_lower = repo.strip().lower()
    if o_lower in GITHUB_BLOCKED_ROUTES or r_lower in GITHUB_BLOCKED_ROUTES:
        return True
    comp_guess = r_lower.replace("-", " ")
    if comp_guess in GENERIC_INVALID_COMPANY_NAMES or r_lower in GENERIC_INVALID_COMPANY_NAMES:
        return True
    return False


def extract_github_owner_repo(text_or_url: str) -> Optional[Tuple[str, str]]:
    """
    Safely extracts and validates (owner, repo) from a URL or slug.
    Discards navigation breadcrumbs, route segments, and invalid URLs.
    """
    if not text_or_url:
        return None

    cleaned = text_or_url.strip()
    # Strip URL protocol and domain if present
    cleaned = re.sub(r'^https?://(?:www\.)?github\.com/', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\.git$', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip('/')

    parts = [p.strip() for p in cleaned.split('/') if p.strip()]
    if len(parts) < 2:
        return None

    owner, repo = parts[0], parts[1]

    # Validate characters (GitHub usernames and repo names only contain alphanumeric, hyphens, underscores, dots)
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', owner) or not re.match(r'^[a-zA-Z0-9_\-\.]+$', repo):
        return None

    if is_blocked_github_slug(owner, repo):
        return None

    return owner, repo


def validate_github_repo_metadata(
    owner: str,
    repo: str,
    min_stars: int = 250,
    require_license: bool = True
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Validates GitHub repository metadata via GitHub API:
    - Explicit metadata: stars > 250
    - has_license == True
    - Returns repository homepage (canonical domain) and description if valid.
    """
    cache_key = f"{owner.strip().lower()}/{repo.strip().lower()}"
    if cache_key in _REPO_METADATA_CACHE:
        return _REPO_METADATA_CACHE[cache_key]

    if is_blocked_github_slug(owner, repo):
        res_tuple = (False, None, f"Blocked GitHub route or UI segment: {owner}/{repo}")
        _REPO_METADATA_CACHE[cache_key] = res_tuple
        return res_tuple

    token = get_github_token()
    headers = {"User-Agent": "ai-outreach-engine"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    session = get_github_session()
    url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        res = session.get(url, headers=headers, timeout=3.0)
        if res.status_code == 200:
            data = res.json()
            stargazers = data.get("stargazers_count", 0)
            license_info = data.get("license")
            has_lic = bool(license_info and isinstance(license_info, dict) and license_info.get("key"))
            license_name = license_info.get("name") if license_info else None
            homepage = (data.get("homepage") or "").strip()
            description = (data.get("description") or "").strip()

            if stargazers < min_stars:
                res_tuple = (False, None, f"Insufficient GitHub stars: {stargazers} < {min_stars}")
            elif require_license and not has_lic:
                res_tuple = (False, None, f"Repository has no open source license (has_license == False)")
            else:
                res_tuple = (True, {
                    "owner": owner,
                    "repo": repo,
                    "stars": stargazers,
                    "has_license": has_lic,
                    "license_name": license_name,
                    "homepage": homepage,
                    "description": description
                }, "Valid GitHub repository metadata")

            _REPO_METADATA_CACHE[cache_key] = res_tuple
            return res_tuple

        elif res.status_code == 404:
            res_tuple = (False, None, f"GitHub repository {owner}/{repo} not found (404)")
            _REPO_METADATA_CACHE[cache_key] = res_tuple
            return res_tuple

        elif res.status_code in (403, 429):
            logger.warning(f"GitHub API rate limited for {owner}/{repo} (status {res.status_code})")
            res_tuple = (True, {
                "owner": owner,
                "repo": repo,
                "stars": None,
                "has_license": True,
                "homepage": "",
                "description": ""
            }, "GitHub API rate limited; passed syntactic route filter")
            _REPO_METADATA_CACHE[cache_key] = res_tuple
            return res_tuple
        else:
            res_tuple = (False, None, f"GitHub API returned status {res.status_code}")
            _REPO_METADATA_CACHE[cache_key] = res_tuple
            return res_tuple

    except Exception as e:
        logger.warning(f"GitHub API check exception for {owner}/{repo}: {e}")
        res_tuple = (True, {
            "owner": owner,
            "repo": repo,
            "stars": None,
            "has_license": True,
            "homepage": "",
            "description": ""
        }, f"GitHub API check timed out: {e}")
        _REPO_METADATA_CACHE[cache_key] = res_tuple
        return res_tuple


def is_free_hosting_or_raw_repo(domain_or_url: str) -> bool:
    """Checks whether a domain/URL belongs to a free hosting provider, raw git repo, or aggregator."""
    if not domain_or_url:
        return True

    try:
        parsed = urllib.parse.urlparse(domain_or_url if "://" in domain_or_url else f"http://{domain_or_url}")
        host = re.sub(r'^www\.', '', parsed.netloc or parsed.path).split(':')[0].lower()
        if not host or '.' not in host:
            return True
        for blocked in FREE_HOSTING_AND_AGGREGATOR_DOMAINS:
            if host == blocked or host.endswith(f".{blocked}"):
                return True
        return False
    except Exception:
        return True


def verify_linkedin_company_presence(company: str) -> Tuple[bool, Optional[str]]:
    """
    Performs a lightweight search verification for a commercial company LinkedIn profile
    via Serper Google Search (site:linkedin.com/company/ "{company}").
    """
    from engine.config import SERPER_API_KEY
    if not SERPER_API_KEY or not company:
        return False, None

    clean_comp = company.strip().strip('"')
    if len(clean_comp) < 2 or clean_comp.lower() in GENERIC_INVALID_COMPANY_NAMES:
        return False, None

    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": f'site:linkedin.com/company/ "{clean_comp}"', "num": 2}

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=7)
        if res.status_code == 200:
            data = res.json()
            for item in data.get("organic", []):
                link = item.get("link", "")
                if "linkedin.com/company/" in link:
                    # Clean URL to standard https://www.linkedin.com/company/{slug}
                    m = re.search(r'(https?://(?:www\.)?linkedin\.com/company/[a-zA-Z0-9_\-]+)', link)
                    if m:
                        return True, m.group(1)
            return False, None
    except Exception as e:
        logger.warning(f"LinkedIn company search failed for '{company}': {e}")

    return False, None


def classify_entity_commercial_vs_hobby(
    company: str,
    domain: str,
    lead_url: str = "",
    description: str = "",
    source_channel: str = ""
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Classifies an entity as a 'Commercial Startup' (eligible for Notion card & outreach)
    vs 'Hobby / Student Experiment' (solo proof-of-concept, student toy app without hiring budget).

    Verification checks:
    1. Immediate exemption for proven commercial job boards & funding rounds
       (Greenhouse, Ashby, Arbeitnow, RemoteOK, Remotive, YC OSS, TechCrunch Funding).
    2. Name & Route blocklist check (blocks UI scraps like Explore, Repo Rules, cursor/plugins).
    3. Domain Verification: Checks if the project has a custom domain (.com, .ai, .io, etc.)
       that resolves via DNS/MX rather than raw github.com or free sub-paths.
    4. Company registry / LinkedIn verification API: Lightweight check for linkedin.com/company/
    """
    clean_name = company.strip()
    ck = clean_name.lower()

    # 1. Filter out known generic navigation breadcrumbs & blocked routes immediately
    if ck in GENERIC_INVALID_COMPANY_NAMES or any(ck == r or ck.endswith(f" {r}") for r in GITHUB_BLOCKED_ROUTES):
        return False, f"Entity name '{clean_name}' matches generic navigation/UI route", {"entity_type": "Hobby / Noise"}

    # 2. Exemption for trusted commercial job boards and venture programs
    trusted_channel_keywords = [
        "greenhouse", "ashby", "arbeitnow", "jobicy", "remoteok", "remotive",
        "yc open source", "techcrunch", "hn ai funding", "who is hiring",
        "curated", "target ai"
    ]
    ch_lower = source_channel.lower()
    if any(k in ch_lower for k in trusted_channel_keywords):
        return True, f"Verified commercial venture from trusted channel: {source_channel}", {
            "entity_type": "Commercial Startup",
            "is_trusted_channel": True
        }

    # 3. Domain Verification Check
    has_custom_domain = False
    effective_domain = domain.strip().lower() if domain else ""
    if effective_domain and not is_free_hosting_or_raw_repo(effective_domain):
        if does_domain_exist(effective_domain):
            has_custom_domain = True

    # Check lead_url for custom domain if domain was generic
    if not has_custom_domain and lead_url:
        try:
            parsed = urllib.parse.urlparse(lead_url)
            host = re.sub(r'^www\.', '', parsed.netloc).split(':')[0].lower()
            if host and not is_free_hosting_or_raw_repo(host) and does_domain_exist(host):
                has_custom_domain = True
                effective_domain = host
        except Exception:
            pass

    # 4. LinkedIn Company Verification
    has_company_linkedin = False
    verified_linkedin_url: Optional[str] = None
    has_company_linkedin, verified_linkedin_url = verify_linkedin_company_presence(clean_name)

    # 5. Final Classification
    metadata = {
        "company": clean_name,
        "effective_domain": effective_domain,
        "has_custom_domain": has_custom_domain,
        "has_company_linkedin": has_company_linkedin,
        "company_linkedin_url": verified_linkedin_url
    }

    if has_company_linkedin:
        metadata["entity_type"] = "Commercial Startup"
        return True, f"Verified LinkedIn company profile: {verified_linkedin_url}", metadata

    if has_custom_domain:
        metadata["entity_type"] = "Commercial Startup"
        return True, f"Verified custom business domain: {effective_domain}", metadata

    # If neither custom domain nor company LinkedIn profile exists, it is a solo hobby/student app
    metadata["entity_type"] = "Hobby / Student Experiment"
    return False, f"No custom domain (.com/.ai/.io) and no LinkedIn company profile found for '{clean_name}'", metadata
