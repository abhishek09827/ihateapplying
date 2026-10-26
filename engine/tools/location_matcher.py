import re
from typing import Tuple

# Positive indicators for India & APAC / Asia
INDIA_PATTERNS = [
    r'\bindia\b',
    r'\b(?:bengaluru|bangalore|delhi|new delhi|hyderabad|mumbai|pune|chennai|gurgaon|gurugram|noida|kolkata|ahmedabad)\b',
    r'\bapac\b',
    r'\basia[- ]pacific\b',
    r'\bsouth asia\b',
    r'\basia\b',
    r'\bist\b',
    r'\bindia remote\b',
    r'\bremote[- ]india\b',
    r'\bhiring in india\b',
    r'\bopen to (?:candidates in )?india\b',
]

# Positive indicators for Worldwide / Global / Anywhere remote
WORLDWIDE_PATTERNS = [
    r'\bworldwide\b',
    r'\bglobal\b',
    r'\bglobally\b',
    r'\banywhere\b',
    r'\bwork from anywhere\b',
    r'\bany location\b',
    r'\banywhere in the world\b',
    r'\bremote[- ]worldwide\b',
    r'\bremote[- ]global\b',
    r'\ball countries\b',
    r'\bno location restriction\b',
    r'\beverywhere\b',
]

# Strict exclusions: Regional blocks that exclude applicants living in India
RESTRICTED_GEO_PATTERNS = [
    r'\b(?:us|usa|united states|north america|u\.s\.|u\.s\.a\.)\s*(?:only|residents?|citizens?)\b',
    r'\b(?:only\s+(?:in|for)\s+(?:the\s+)?(?:us|usa|united states|north america|canada|uk|europe|eu))\b',
    r'\b(?:must\s+be\s+(?:located|based|living|resident)\s+in\s+(?:the\s+)?(?:us|usa|united states|north america|canada|uk|europe|eu))\b',
    r'\b(?:us\s+citizen(?:ship)?|green\s+card|security\s+clearance)\b',
    r'\b(?:authorized\s+to\s+work\s+in\s+the\s+us\s+without\s+sponsorship)\b',
    r'\b(?:no\s+(?:visa\s+)?sponsorship)\b',
    r'\b(?:canada|uk|united kingdom|europe|eu|germany|latam|australia)\s*only\b',
    r'\b(?:emea\s+only)\b',
]

# Single country values in location fields that indicate non-remote or single-country local hiring
SINGLE_RESTRICTED_COUNTRIES = {
    "usa", "us", "united states", "canada", "germany", "uk", "united kingdom",
    "france", "australia", "spain", "ireland", "poland", "netherlands", "sweden"
}

def get_india_remote_priority(location: str, description: str = "") -> Tuple[int, str]:
    """
    Evaluates a job posting's location and description for remote hiring from India.
    Returns (priority_rank: int, reasoning: str).
    Priority Ranks:
      3: Explicit India / APAC / Indian city / IST mentioned (Top priority)
      2: Worldwide / Global / Work from anywhere (High priority)
      1: Generic Remote / Unspecified location (Medium/Neutral)
      0: Geo-restricted to US/EU/etc. or requires US citizenship (Ineligible / lowest priority)
    """
    loc_clean = (location or "").strip().lower()
    desc_clean = (description or "")[:3000].lower()
    combined = f"{loc_clean} {desc_clean}"

    # 1. Explicit India / APAC in location field
    if any(re.search(p, loc_clean) for p in INDIA_PATTERNS):
        return 3, f"Explicit India/APAC remote role ({location})"

    # 2. Explicit Worldwide / Anywhere in location field
    if any(re.search(p, loc_clean) for p in WORLDWIDE_PATTERNS):
        return 2, f"Worldwide / Global remote role ({location})"

    # 3. Check for strict regional restrictions that disqualify India candidates
    for pattern in RESTRICTED_GEO_PATTERNS:
        if re.search(pattern, combined):
            # If India is also explicitly mentioned in the description as an eligible hub, keep it
            if any(re.search(p, desc_clean) for p in INDIA_PATTERNS):
                return 3, "India mentioned in eligible regions despite regional tags"
            return 0, f"Restricted location: matched {pattern}"

    if loc_clean in SINGLE_RESTRICTED_COUNTRIES:
        # Check if description mentions worldwide/India
        if any(re.search(p, desc_clean) for p in INDIA_PATTERNS):
            return 3, f"India remote eligible based on description ({location})"
        if any(re.search(p, desc_clean) for p in WORLDWIDE_PATTERNS):
            return 2, f"Worldwide remote eligible based on description ({location})"
        return 0, f"Restricted single-country location ({location})"

    # 4. Check description for positive indicators
    if any(re.search(p, desc_clean) for p in INDIA_PATTERNS):
        return 3, "India / APAC remote explicitly supported in description"

    if any(re.search(p, desc_clean) for p in WORLDWIDE_PATTERNS):
        return 2, "Worldwide / Global hiring explicitly supported in description"

    # 5. Default remote
    if "remote" in loc_clean or not loc_clean:
        return 1, "Generic remote role (open)"

    return 1, f"Standard remote/hybrid posting ({location})"

def is_india_remote_eligible(location: str, description: str = "") -> Tuple[bool, str]:
    """Checks whether a candidate based in India is legally and geographically eligible to apply."""
    rank, reason = get_india_remote_priority(location, description)
    if rank == 0:
        return False, reason
    return True, reason

def get_india_remote_score_bonus(location: str, description: str = "") -> int:
    """Returns scoring bonus or penalty points for match score computation."""
    rank, _ = get_india_remote_priority(location, description)
    if rank == 3:
        return 15   # High priority boost for India/APAC roles
    elif rank == 2:
        return 10   # Strong boost for Worldwide/Global roles
    elif rank == 1:
        return 0    # Neutral for generic remote
    else:
        return -50  # Heavy penalty for restricted non-India roles
