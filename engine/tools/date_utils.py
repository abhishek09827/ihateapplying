import time
from email.utils import parsedate_to_datetime
from datetime import datetime
from typing import Union, Optional

def parse_date_to_timestamp(date_val: Optional[Union[str, int, float]]) -> float:
    """
    Parses various date representations (ISO-8601, RFC-2822, Unix epoch)
    into a standardized float Unix timestamp for descending sort (latest first).
    """
    if not date_val:
        return 0.0

    if isinstance(date_val, (int, float)):
        # If milliseconds timestamp
        if date_val > 1e11:
            return float(date_val) / 1000.0
        return float(date_val)

    s = str(date_val).strip()
    if not s:
        return 0.0

    # 1. ISO 8601
    try:
        clean_iso = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_iso)
        return dt.timestamp()
    except Exception:
        pass

    # 2. RFC 2822 (Common in RSS feeds)
    try:
        dt = parsedate_to_datetime(s)
        return dt.timestamp()
    except Exception:
        pass

    # 3. Numeric string
    try:
        num = float(s)
        if num > 1e11:
            return num / 1000.0
        return num
    except Exception:
        pass

    return 0.0
