import os
import smtplib
import logging
from email.message import EmailMessage
from engine.config import GMAIL_USER, GMAIL_APP_PASSWORD

logger = logging.getLogger("Alerter")

def send_error_alert(subject_prefix: str, error_detail: str):
    """Sends an emergency failure notification email to the configured Gmail user."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        logger.warning("Alerter cannot send email: Gmail credentials not configured.")
        return

    msg = EmailMessage()
    msg["From"] = f"AI Outreach Engine Monitor <{GMAIL_USER}>"
    msg["To"] = GMAIL_USER
    msg["Subject"] = f"[Outreach Alert] {subject_prefix}"
    msg.set_content(f"The automated AI outreach pipeline encountered an error:\n\n{error_detail}\n\nPlease check your configuration.")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        logger.info(f"Alert email sent to {GMAIL_USER}")
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")
