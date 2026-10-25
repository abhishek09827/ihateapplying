import re
try:
    import dns.resolver
    HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False
import socket
from typing import Tuple, Optional

# Basic regex for email validation
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

# Disposable and synthetic email blocks
DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "guerrillamail.com", "10minutemail.com",
    "yopmail.com", "trashmail.com", "fakemailgenerator.com"
}

_DNS_CACHE = {}

def does_domain_exist(domain: str) -> bool:
    """Verifies that domain exists on public DNS via MX or A records."""
    domain = domain.lower().strip()
    if not domain or "." not in domain:
        return False

    if domain in _DNS_CACHE:
        return _DNS_CACHE[domain]

    if HAS_DNSPYTHON:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 3.0
        resolver.lifetime = 3.0

        # 1. Check MX record (primary email handling indicator)
        try:
            answers = resolver.resolve(domain, 'MX')
            if answers:
                _DNS_CACHE[domain] = True
                return True
        except Exception:
            pass

        # 2. Check A record (fallback)
        try:
            answers = resolver.resolve(domain, 'A')
            if answers:
                _DNS_CACHE[domain] = True
                return True
        except Exception:
            pass
    else:
        # Standard library socket fallback
        try:
            socket.gethostbyname(domain)
            _DNS_CACHE[domain] = True
            return True
        except Exception:
            pass

    _DNS_CACHE[domain] = False
    return False

def verify_and_clean_email(raw_email: Optional[str]) -> Tuple[bool, str, str]:
    """
    Validates email format, verifies domain exists on public DNS,
    and strips illegal characters or synthetic domains.
    Returns (is_valid, clean_email, reason).
    """
    if not raw_email or not isinstance(raw_email, str):
        return False, "", "Empty or non-string email"

    clean = raw_email.strip().lower().rstrip(".").strip("<>\"'")

    # Syntax check
    if not EMAIL_REGEX.match(clean):
        return False, "", "Invalid email syntax"

    parts = clean.split("@")
    if len(parts) != 2:
        return False, "", "Malformed email address"

    user, domain = parts[0], parts[1]

    # Block disposable domains
    if domain in DISPOSABLE_DOMAINS:
        return False, "", "Disposable email domain rejected"

    # Block common invalid or test domains
    if domain.endswith((".test", ".example", ".invalid", ".localhost")):
        return False, "", "Test or non-routable domain"

    # DNS deliverability check
    if not does_domain_exist(domain):
        return False, "", f"Domain '{domain}' does not exist on DNS"

    return True, clean, "Domain verified & syntax valid"
