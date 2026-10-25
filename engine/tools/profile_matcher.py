import re
from typing import Tuple, List, Optional
from engine.config import MASTER_PROFILE

# Default target patterns if not specified in profile.json
DEFAULT_TARGET_PATTERNS = [
    r'\bai\s+engineer\b',
    r'\bapplied\s+ai\b',
    r'\bgenerative\s+ai\b',
    r'\bgenai\b',
    r'\bllm\b',
    r'\bagentic\b',
    r'\bai\s+agent\b',
    r'\bmachine\s+learning\s+engineer\b',
    r'\bml\s+engineer\b',
    r'\bfounding\s+ai\b',
    r'\bfounding\s+engineer\b',
    r'\bdata\s+platform\b',
    r'\bdata\s+engineer\b',
    r'\bpython\s+(?:developer|engineer|backend)\b'
]

# Strict disqualification patterns for overly senior, unrelated, or non-technical roles
DISQUALIFYING_TITLE_PATTERNS = [
    r'\bprincipal\b',
    r'\bstaff\b',
    r'\barchitect\b',
    r'\bdirector\b',
    r'\bvp\b',
    r'\bhead\s+of\b',
    r'\bmanager\b',
    r'\bfrontend\b',
    r'\breact\s+developer\b',
    r'\bui/ux\b',
    r'\bproduct\s+manager\b',
    r'\bqa\s+engineer\b',
    r'\bscrum\s+master\b'
]

# Experience requirement detection regex
EXPERIENCE_PATTERNS = [
    r'(\d+)\+?\s*(?:-\s*(\d+))?\s*(?:years?|yrs?)\b',
    r'(\d+)\s*(?:to|-)\s*(\d+)\s*(?:years?|yrs?)\b',
    r'minimum\s+of\s+(\d+)\s*(?:years?|yrs?)\b'
]

def get_target_patterns() -> List[str]:
    """Generates regex patterns from candidate's configured target_roles."""
    target_roles = MASTER_PROFILE.get("candidate", {}).get("target_roles", [])
    if not target_roles:
        return DEFAULT_TARGET_PATTERNS

    patterns = []
    for role in target_roles:
        escaped = re.escape(role.strip()).replace(r'\ ', r'\s+')
        patterns.append(rf'\b{escaped}\b')
    return patterns + DEFAULT_TARGET_PATTERNS[:4]

def is_seniority_compatible(description: str, max_allowed_exp: int = 4) -> Tuple[bool, str]:
    """
    Scans job description to detect explicit experience requirements.
    Rejects postings explicitly demanding 5+, 7+, or 10+ years of experience.
    """
    if not description:
        return True, "No explicit experience stated"

    desc_lower = description.lower()
    for pat in EXPERIENCE_PATTERNS:
        matches = re.findall(pat, desc_lower)
        for m in matches:
            if isinstance(m, tuple):
                nums = [int(n) for n in m if n.isdigit()]
            elif isinstance(m, str) and m.isdigit():
                nums = [int(m)]
            else:
                continue

            if nums:
                min_exp = nums[0]
                if min_exp > max_allowed_exp:
                    return False, f"Requires {min_exp}+ years experience (exceeds 1-3 yr target)"

    return True, "Experience requirements compatible"

def is_profile_aligned(
    title: str,
    description: str = "",
    tags: Optional[List[str]] = None
) -> Tuple[bool, str]:
    """
    Fast, deterministic profile matcher that filters out non-matching roles at source in 0.001s.
    Returns (is_aligned, match_reason).
    """
    if not title:
        return False, "Empty title"

    title_lower = title.strip().lower()
    desc_lower = (description or "").strip().lower()
    tags_lower = [t.lower() for t in (tags or [])]

    # 1. Immediate disqualification on negative title keywords
    for pat in DISQUALIFYING_TITLE_PATTERNS:
        if re.search(pat, title_lower):
            return False, f"Disqualified title keyword: {pat}"

    # 2. Seniority validation (Rejects 5+ yr requirement)
    seniority_ok, exp_reason = is_seniority_compatible(desc_lower)
    if not seniority_ok:
        return False, exp_reason

    # 3. Match against candidate target patterns
    patterns = get_target_patterns()
    for pat in patterns:
        if re.search(pat, title_lower):
            return True, f"Direct title match: {pat}"

    # 4. Check tags for technical alignment
    target_skills = [s.lower() for s in MASTER_PROFILE.get("candidate", {}).get("target_skills", ["ai", "python", "llm", "kafka"])]
    matching_tags = [t for t in tags_lower if any(s in t for s in target_skills)]
    if len(matching_tags) >= 2 and any(k in title_lower for k in ["engineer", "developer", "founding"]):
        return True, f"Technical tags alignment: {', '.join(matching_tags)}"

    return False, "Role not aligned with target profile"


def is_candidate_profile_match(
    title: str,
    description: str = "",
    target_roles: Optional[List[str]] = None,
    max_allowed_exp: int = 4
) -> bool:
    """
    Checks if a job title and description match the target candidate profile.
    Returns True if compatible, False otherwise.
    """
    if not title:
        return False

    title_lower = title.strip().lower()

    # 1. Reject disqualifying title keywords
    for pat in DISQUALIFYING_TITLE_PATTERNS:
        if re.search(pat, title_lower):
            return False

    # 2. Reject excessive seniority requirements
    seniority_ok, _ = is_seniority_compatible(description, max_allowed_exp)
    if not seniority_ok:
        return False

    # 3. Match against target roles if provided
    roles = target_roles or MASTER_PROFILE.get("candidate", {}).get("target_roles", [])
    if roles:
        for r in roles:
            escaped = re.escape(r.strip().lower()).replace(r'\ ', r'\s+')
            if re.search(rf'\b{escaped}\b', title_lower):
                return True
        return False

    aligned, _ = is_profile_aligned(title, description)
    return aligned

