import os
import re
import json
import logging
import requests
from typing import Set, Tuple, Optional
from engine.config import NOTION_TOKEN, NOTION_DATABASE_ID, clean_uuid
from engine.state import ApplicationPackage

logger = logging.getLogger("NotionClient")

NOTION_VERSION = "2022-06-28"

def get_notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

def get_existing_notion_companies() -> Set[str]:
    """Retrieves list of company names already recorded in the Notion database."""
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        return set()

    db_id = clean_uuid(NOTION_DATABASE_ID)
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    seen = set()

    has_more = True
    start_cursor = None

    try:
        while has_more:
            payload = {"page_size": 100}
            if start_cursor:
                payload["start_cursor"] = start_cursor

            res = requests.post(url, headers=get_notion_headers(), json=payload, timeout=12)
            if res.status_code != 200:
                logger.warning(f"Failed to query Notion database ({res.status_code}): {res.text[:100]}")
                break

            data = res.json()
            for page in data.get("results", []):
                props = page.get("properties", {})
                title_list = props.get("Company", {}).get("title", [])
                if title_list:
                    comp_name = title_list[0].get("plain_text", "").strip().lower()
                    if comp_name:
                        seen.add(comp_name)

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

    except Exception as e:
        logger.error(f"Error fetching existing companies from Notion: {e}")

    return seen

def push_to_notion(pkg: ApplicationPackage) -> Tuple[bool, str]:
    """Pushes a processed application package to Notion CRM."""
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        return False, "Notion credentials not configured in .env"

    db_id = clean_uuid(NOTION_DATABASE_ID)
    url = "https://api.notion.com/v1/pages"

    status_name = "Email Sent Live" if "Sent" in pkg.dispatch_status else ("Draft Created in Gmail" if "Draft" in pkg.dispatch_status else "To Review")

    properties = {
        "Company": {
            "title": [{"text": {"content": pkg.company_clean_name[:100]}}]
        },
        "Role / Pitch Angle": {
            "rich_text": [{"text": {"content": f"{pkg.lead.role} [{pkg.fit.selected_angle}]"[:2000]}}]
        },
        "Channel": {
            "select": {"name": pkg.lead.source_channel[:100].replace(",", "")}
        },
        "Match Score": {
            "number": pkg.fit.match_score
        },
        "Key Metrics / Custom Angle": {
            "rich_text": [{"text": {"content": f"{pkg.fit.fit_reasoning}\n\nBullets:\n" + "\n".join(pkg.tailored_resume_bullets)[:1800]}}]
        },
        "Target Contact": {
            "rich_text": [{"text": {"content": f"{pkg.contact.name} ({pkg.contact.title})"[:2000]}}]
        },
        "Dispatch Status": {
            "select": {"name": status_name}
        },
        "Custom Cold Email": {
            "rich_text": [{"text": {"content": f"Subject: {pkg.cold_email_subject}\n\n{pkg.cold_email_body}"[:2000]}}]
        }
    }

    if pkg.contact.email:
        properties["Contact Email"] = {"email": pkg.contact.email}

    if pkg.contact.linkedin_url:
        properties["LinkedIn URL"] = {"url": pkg.contact.linkedin_url[:2000]}

    if pkg.lead.url:
        properties["Job Posting URL"] = {"url": pkg.lead.url[:2000]}

    body = {
        "parent": {"database_id": db_id},
        "properties": properties
    }

    try:
        res = requests.post(url, headers=get_notion_headers(), json=body, timeout=12)
        if res.status_code == 200:
            page_id = res.json().get("id")
            return True, page_id
        else:
            return False, f"Notion API error ({res.status_code}): {res.text[:120]}"
    except Exception as e:
        return False, str(e)


def fetch_pending_notion_applications() -> list:
    """
    Fetches records from Notion CRM that need dispatching or email resolution.
    Returns list of dicts with page_id, company, role, email, status, and raw properties.
    """
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        return []

    db_id = clean_uuid(NOTION_DATABASE_ID)
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    pending = []

    try:
        # Filter for rows that are not yet marked as 'Email Sent Live'
        payload = {
            "page_size": 100,
            "filter": {
                "property": "Dispatch Status",
                "select": {
                    "does_not_equal": "Email Sent Live"
                }
            }
        }
        res = requests.post(url, headers=get_notion_headers(), json=payload, timeout=12)
        if res.status_code != 200:
            # If the filter fails (e.g. property is status or different type), fall back to unfiltered query
            res = requests.post(url, headers=get_notion_headers(), json={"page_size": 100}, timeout=12)
            if res.status_code != 200:
                logger.error(f"Failed to query Notion for pending records: {res.text[:100]}")
                return []

        for page in res.json().get("results", []):
            page_id = page.get("id")
            props = page.get("properties", {})

            # Extract company
            company = ""
            for t in props.get("Company", {}).get("title", []):
                company += t.get("plain_text", "")

            # Extract role
            role = ""
            for t in props.get("Role / Pitch Angle", {}).get("rich_text", []):
                role += t.get("plain_text", "")

            # Extract email
            email = props.get("Contact Email", {}).get("email") or ""

            # Extract status
            status_obj = props.get("Dispatch Status", {}).get("select") or {}
            status_val = status_obj.get("name", "Pending")

            # Extract custom email body & subject
            email_text = ""
            for t in props.get("Custom Cold Email", {}).get("rich_text", []):
                email_text += t.get("plain_text", "")

            # Extract target contact
            contact_str = ""
            for t in props.get("Target Contact", {}).get("rich_text", []):
                contact_str += t.get("plain_text", "")

            # Extract job url
            job_url = props.get("Job Posting URL", {}).get("url") or ""

            if status_val != "Email Sent Live" and company:
                pending.append({
                    "page_id": page_id,
                    "company": company.strip(),
                    "role": role.strip(),
                    "email": email.strip() if email else "",
                    "status": status_val,
                    "email_text": email_text,
                    "contact_str": contact_str,
                    "job_url": job_url
                })

    except Exception as e:
        logger.error(f"Error reading pending applications from Notion: {e}")

    return pending


def update_notion_page(page_id: str, properties: dict) -> Tuple[bool, str]:
    """Updates properties on an existing Notion page."""
    if not NOTION_TOKEN or not page_id:
        return False, "Notion credentials or page_id missing"

    url = f"https://api.notion.com/v1/pages/{page_id}"
    try:
        res = requests.patch(url, headers=get_notion_headers(), json={"properties": properties}, timeout=12)
        if res.status_code == 200:
            return True, "Updated"
        return False, f"Notion error {res.status_code}: {res.text[:120]}"
    except Exception as e:
        return False, str(e)

