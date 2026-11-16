import re
import socket
import logging
import unicodedata
from typing import Tuple, Optional, List

try:
    import dns.resolver
    HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False

logger = logging.getLogger("EmailVerifier")

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$')

DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "guerrillamail.com", "10minutemail.com",
    "yopmail.com", "trashmail.com", "fakemailgenerator.com"
}

UNHELPFUL_EMAIL_PREFIXES = (
    "support@", "help@", "info@", "billing@", "sales@", "press@", "media@",
    "admin@", "office@", "service@", "customerservice@", "legal@", "privacy@",
    "abuse@", "security@", "terms@", "inquiry@", "inquiries@", "contact@"
)

_DNS_CACHE = {}

def is_unhelpful_generic_email(email: str) -> bool:
    """
    Returns True if email is a customer support, billing, inquiry, or unmonitored general mailbox
    that should NOT be used for direct cold job outreach.
    """
    if not email or not isinstance(email, str):
        return True
    clean = email.strip().lower()
    return any(clean.startswith(prefix) for prefix in UNHELPFUL_EMAIL_PREFIXES)

def is_valid_email_syntax(email: str) -> bool:
    """Verifies that the string conforms to standard RFC-5322 email syntax."""
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))

def does_domain_have_mx(domain: str) -> bool:
    """Checks whether the domain has valid active MX mail exchange records."""
    if not domain:
        return False
    clean_domain = domain.replace("http://", "").replace("https://", "").strip("/").split("/")[0].split(":")[0].lower()
    if "." not in clean_domain or len(clean_domain.split(".")[-1]) < 2:
        return False

    if clean_domain in _DNS_CACHE:
        return _DNS_CACHE[clean_domain]

    if HAS_DNSPYTHON:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 3.0
        resolver.lifetime = 3.0
        try:
            answers = resolver.resolve(clean_domain, 'MX')
            if answers and len(answers) > 0:
                _DNS_CACHE[clean_domain] = True
                return True
        except Exception:
            pass

    # Fallback to A record check if dnspython or MX resolution is unavailable
    try:
        socket.gethostbyname(clean_domain)
        _DNS_CACHE[clean_domain] = True
        return True
    except Exception:
        pass

    _DNS_CACHE[clean_domain] = False
    return False

def does_domain_exist(domain: str) -> bool:
    """Checks whether the domain exists on DNS (MX or A record)."""
    return does_domain_have_mx(domain)

def verify_and_clean_email(raw_email: Optional[str], allow_generic: bool = True) -> Tuple[bool, str, str]:
    """
    Validates email format, verifies domain MX records exist on public DNS,
    and strips illegal characters or synthetic domains.
    If allow_generic is False, rejects customer support/info mailboxes unsuitable for outreach.
    Returns (is_valid: bool, clean_email: str, reason: str).
    """
    if not raw_email or not isinstance(raw_email, str):
        return False, "", "Empty or non-string email"

    clean = raw_email.strip().lower().rstrip(".").strip("<>\"'")

    # 1. Syntax check
    if not is_valid_email_syntax(clean):
        return False, "", "Invalid email syntax"

    parts = clean.split("@")
    if len(parts) != 2:
        return False, "", "Malformed email address"

    user, domain = parts[0], parts[1]

    # 2. Block disposable domains
    if domain in DISPOSABLE_DOMAINS:
        return False, "", "Disposable email domain rejected"

    # 3. Discard non-deliverable placeholder strings
    if any(clean.startswith(bad) for bad in ["example@", "test@", "placeholder@", "noemail@", "none@", "null@", "undefined@"]):
        return False, "", "Generic placeholder address"

    # 4. Reject support/info generic mailboxes if allow_generic is False
    if not allow_generic and is_unhelpful_generic_email(clean):
        return False, "", "Generic support/info mailbox unsuitable for outreach"

    # 5. Block common invalid or test domains
    if domain.endswith((".test", ".example", ".invalid", ".localhost")):
        return False, "", "Test or non-routable domain"

    # 6. DNS MX deliverability check
    if not does_domain_have_mx(domain):
        logger.warning(f"Email domain '{domain}' does not have active MX records. Rejecting '{clean}'.")
        return False, "", f"Domain '{domain}' has no active MX records (DNS lookup failed)"

    return True, clean, "Domain verified & syntax valid"

def clean_ascii_token(s: str) -> str:
    """Normalizes unicode diacritics and converts to clean lowercase ASCII alphanumeric string."""
    if not s:
        return ""
    nfkd = unicodedata.normalize('NFKD', s)
    ascii_str = nfkd.encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^a-zA-Z0-9]', '', ascii_str).lower()

def is_likely_human_name(name: str) -> bool:
    """Determines whether a contact name is a real human person rather than a generic role or title."""
    if not name or len(name) < 2:
        return False
    lower = name.lower().strip()
    if any(phrase in lower for phrase in ["not mentioned", "not found", "not publicly", "unknown", "n/a", "no name"]):
        return False

    non_human_keywords = {
        "founder", "co-founder", "cto", "ceo", "cpo", "coo", "cio", "cso",
        "vp", "director", "head", "engineering", "leadership", "team",
        "recruiter", "talent", "hr", "people", "unknown", "company", "support",
        "admin", "office", "contact", "dr", "mr", "mrs", "ms", "hiring",
        "member", "lead", "architect", "manager", "representative"
    }

    clean = re.sub(r'[\(\[\{].*?[\)\]\}]', '', lower).strip()
    clean = re.sub(r'[/\\–\-|•,;:]', ' ', clean)
    tokens = [clean_ascii_token(w) for w in clean.split() if clean_ascii_token(w)]
    human_tokens = [t for t in tokens if t not in non_human_keywords and len(t) > 1]
    return len(human_tokens) >= 1

def generate_person_email_permutations(name: str, domain: str) -> List[str]:
    """
    Generates prioritized email permutations for an identified decision maker / engineer:
    1. firstname@domain
    2. firstinitial@domain
    3. firstinitiallastinitial@domain
    4. firstname.lastname@domain
    5. firstinitial.lastname@domain
    """
    if not name or not domain or not is_likely_human_name(name):
        return []

    clean_domain = domain.lower().replace("http://", "").replace("https://", "").split("/")[0].split(":")[0].strip()
    if clean_domain.startswith("www."):
        clean_domain = clean_domain[4:]
    if not clean_domain or "." not in clean_domain:
        return []

    non_human_keywords = {
        "founder", "co-founder", "cto", "ceo", "cpo", "coo", "cio", "cso",
        "vp", "director", "head", "engineering", "leadership", "team",
        "recruiter", "talent", "hr", "people", "unknown", "company", "support",
        "admin", "office", "contact", "dr", "mr", "mrs", "ms", "hiring",
        "member", "lead", "architect", "manager", "staff", "senior"
    }

    clean = re.sub(r'[\(\[\{].*?[\)\]\}]', '', name).strip()
    clean = re.sub(r'[/\\–\-|•,;:]', ' ', clean)
    raw_words = [clean_ascii_token(w) for w in clean.split() if clean_ascii_token(w)]
    tokens = [w for w in raw_words if w not in non_human_keywords and len(w) > 1]

    if not tokens:
        return []

    first = tokens[0]
    fi = first[0]

    if len(tokens) >= 2:
        last = tokens[-1]
        li = last[0]
        return [
            f"{first}@{clean_domain}",
            f"{fi}@{clean_domain}",
            f"{fi}{li}@{clean_domain}",
            f"{first}.{last}@{clean_domain}",
            f"{fi}.{last}@{clean_domain}",
        ]
    else:
        return [
            f"{first}@{clean_domain}",
            f"{fi}@{clean_domain}",
        ]
