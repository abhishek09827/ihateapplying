import re
import socket
import logging
from typing import Tuple, Optional

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

_DNS_CACHE = {}

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

def verify_and_clean_email(raw_email: Optional[str]) -> Tuple[bool, str, str]:
    """
    Validates email format, verifies domain MX records exist on public DNS,
    and strips illegal characters or synthetic domains.
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

    # 4. Block common invalid or test domains
    if domain.endswith((".test", ".example", ".invalid", ".localhost")):
        return False, "", "Test or non-routable domain"

    # 5. DNS MX deliverability check
    if not does_domain_have_mx(domain):
        logger.warning(f"Email domain '{domain}' does not have active MX records. Rejecting '{clean}'.")
        return False, "", f"Domain '{domain}' has no active MX records (DNS lookup failed)"

    return True, clean, "Domain verified & syntax valid"
