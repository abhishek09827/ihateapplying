import os
import re
import time
import imaplib
import smtplib
import logging
from email.message import EmailMessage
from pathlib import Path
from typing import Tuple, Optional
from engine.config import (
    GMAIL_USER,
    GMAIL_APP_PASSWORD,
    DISPATCH_MODE,
    CANDIDATE_NAME,
    CANDIDATE_TITLE,
    CANDIDATE_PHONE,
    CANDIDATE_EMAIL,
    RESUME_DRIVE_URL,
    PORTFOLIO_URL,
    GITHUB_URL,
    LINKEDIN_URL
)
from engine.tools.email_verifier import verify_and_clean_email
from engine.tools.resume_compiler import validate_pdf_attachment, get_master_resume_pdf

logger = logging.getLogger("EmailClient")

def format_email_body_with_links(body: str) -> str:
    """
    Ensures cold email body includes candidate signoff and 4 essential links:
    - Google Drive Resume link
    - Portfolio
    - GitHub
    - LinkedIn
    """
    body = (body or "").strip()
    if not body:
        body = "Hi there,\n\nI am writing to express my strong interest in joining your team. I have attached my tailored resume for your review."

    # Prevent duplicate appending if links are already present
    if PORTFOLIO_URL and PORTFOLIO_URL in body and GITHUB_URL and GITHUB_URL in body:
        return body

    # Clean off redundant signoffs from LLM generation
    signoff_patterns = [
        r"(?i)\n+best regards,?\s*([a-zA-Z\s]+)?$",
        r"(?i)\n+best,?\s*([a-zA-Z\s]+)?$",
        r"(?i)\n+sincerely,?\s*([a-zA-Z\s]+)?$",
        r"(?i)\n+thanks & regards,?\s*([a-zA-Z\s]+)?$",
        r"(?i)\n+cheers,?\s*([a-zA-Z\s]+)?$"
    ]
    cleaned_body = body
    for pat in signoff_patterns:
        cleaned_body = re.sub(pat, "", cleaned_body).strip()

    links_block = []
    if RESUME_DRIVE_URL:
        links_block.append(f"• Master Resume (Google Drive): {RESUME_DRIVE_URL}")
    if PORTFOLIO_URL:
        links_block.append(f"• Portfolio: {PORTFOLIO_URL}")
    if GITHUB_URL:
        links_block.append(f"• GitHub: {GITHUB_URL}")
    if LINKEDIN_URL:
        links_block.append(f"• LinkedIn: {LINKEDIN_URL}")

    links_text = "\n".join(links_block)

    signature = (
        f"\n\nBest regards,\n"
        f"{CANDIDATE_NAME}\n"
        f"{CANDIDATE_TITLE}\n"
        f"{CANDIDATE_PHONE + ' | ' if CANDIDATE_PHONE else ''}{CANDIDATE_EMAIL}\n\n"
        f"Verified Links:\n"
        f"{links_text}\n\n"
        f"📎 Tailored 1-page PDF resume is also attached for your convenience."
    )

    return f"{cleaned_body}{signature}".strip()

def dispatch_cold_email(
    to_email: str,
    subject: str,
    body: str,
    pdf_path: Optional[str],
    override_mode: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Dispatches cold email (Gmail Draft or Live SMTP).
    Enforces strict DNS email deliverability check and guarantees PDF resume attachment.
    """
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        return False, "Gmail credentials not configured in .env"

    # 1. DNS Deliverability & Format Verification (Prevents emailing non-existent domains)
    is_valid, clean_email, reason = verify_and_clean_email(to_email)
    if not is_valid or not clean_email:
        logger.warning(f"Email dispatch aborted for '{to_email}': {reason}")
        return False, f"Email Blocked: {reason}"

    # 2. Strict PDF Resume Attachment Verification (Guarantees resume is never omitted)
    verified_pdf = pdf_path if validate_pdf_attachment(pdf_path) else get_master_resume_pdf()
    if not validate_pdf_attachment(verified_pdf):
        logger.error(f"Cannot dispatch email to {clean_email}: No valid PDF resume could be found or compiled.")
        return False, "Email Blocked: PDF Resume Attachment Missing"

    mode = (override_mode or DISPATCH_MODE).upper()

    msg = EmailMessage()
    msg["From"] = f"{CANDIDATE_NAME} <{GMAIL_USER}>"
    msg["To"] = clean_email
    msg["Subject"] = subject.strip()
    formatted_body = format_email_body_with_links(body)
    msg.set_content(formatted_body.strip())

    # Attach verified PDF
    try:
        with open(verified_pdf, "rb") as f:
            pdf_bytes = f.read()
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=f"{re.sub(r'[^a-zA-Z0-9]', '_', CANDIDATE_NAME)}_Resume.pdf",
            disposition="attachment"
        )
    except Exception as e:
        logger.error(f"Failed to read/attach PDF {verified_pdf}: {e}")
        return False, f"Email Blocked: Attachment read failure ({e})"

    try:
        if mode in ("GMAIL_SEND", "AUTO_SEND", "SEND"):
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                smtp.send_message(msg)
            # Safe throttle between live cold emails to prevent spam flags
            time.sleep(15)
            return True, "Email Sent Live (PDF Attached)"
        else:
            # GMAIL_DRAFT (Include \Draft \Seen flags so Gmail renders attachment chip properly)
            with imaplib.IMAP4_SSL("imap.gmail.com", 993) as imap:
                imap.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                imap.append('"[Gmail]/Drafts"', r'(\Draft \Seen)', imaplib.Time2Internaldate(time.time()), msg.as_bytes())
            return True, "Draft Created in Gmail (PDF Attached)"
    except Exception as e:
        logger.error(f"Email dispatch error for {clean_email}: {e}")
        return False, f"Email Failed: {str(e)[:60]}"


def create_gmail_draft(
    to_email: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None
) -> Tuple[bool, str]:
    """Creates a draft in Gmail with tailored PDF resume attached."""
    return dispatch_cold_email(to_email, subject, body, attachment_path, override_mode="GMAIL_DRAFT")


def send_gmail_smtp(
    to_email: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None
) -> Tuple[bool, str]:
    """Sends a live email via Gmail SMTP with tailored PDF resume attached."""
    return dispatch_cold_email(to_email, subject, body, attachment_path, override_mode="SEND")

