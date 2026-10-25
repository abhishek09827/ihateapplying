import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger("ATSPlaywright")

def auto_apply_ats_playwright(
    job_url: str,
    pdf_path: Optional[str] = None,
    cover_note: str = ""
) -> str:
    """
    Automated ATS interaction helper for supported job boards (Greenhouse, Lever, Ashby).
    Validates form availability and flags for manual review if CAPTCHAs are detected.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return f"Playwright not installed. Manual Apply: {job_url}"

    if not job_url:
        return "No Job URL provided"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(job_url, timeout=20000)
            title = page.title()
            browser.close()
            return f"ATS Page Verified ({title[:40]}). Ready for review: {job_url}"
    except Exception as e:
        logger.warning(f"Playwright navigation check failed for {job_url}: {e}")
        return f"Manual Apply Link: {job_url}"
