import csv
import logging
from pathlib import Path
from engine.agents.base import BaseAgent
from engine.state import ApplicationPackage
from engine.config import BASE_DIR, DISPATCH_MODE
from engine.tools.email_client import dispatch_cold_email
from engine.tools.ats_playwright import auto_apply_ats_playwright
from engine.tools.notion_client import push_to_notion

logger = logging.getLogger("DispatchAgent")

class DispatchAgent(BaseAgent):
    """
    Executes outreach actions:
    - Creates Gmail Draft or sends Live SMTP cold email with tailored PDF attachment
    - Performs ATS autofill via Playwright for supported job boards
    - Synchronizes application package and status directly to Notion CRM
    - Maintains local execution history CSV audit trail
    """

    def __init__(self):
        super().__init__(name="DispatchAgent", role="Outreach Execution & CRM Manager")
        self.csv_path = BASE_DIR / "engine_dispatch_history.csv"

    def dispatch(self, package: ApplicationPackage, override_mode: str = None) -> ApplicationPackage:
        """Executes email dispatch, ATS check, and Notion database recording."""
        mode = override_mode or DISPATCH_MODE
        email_status = "No Email Provided"

        # 1. Cold Email Dispatch
        if package.contact.email:
            success, status_msg = dispatch_cold_email(
                to_email=package.contact.email,
                subject=package.cold_email_subject,
                body=package.cold_email_body,
                pdf_path=package.pdf_resume_path,
                override_mode=mode
            )
            email_status = status_msg
        else:
            email_status = "No Email Found"

        # 2. ATS Handling
        ats_status = "Direct Outreach"
        if package.lead.url and any(ats in package.lead.url.lower() for ats in ["greenhouse.io", "ashbyhq.com", "lever.co"]):
            try:
                ats_status = auto_apply_ats_playwright(
                    job_url=package.lead.url,
                    pdf_path=package.pdf_resume_path,
                    cover_note=package.cold_email_body
                )
            except Exception as e:
                ats_status = f"ATS Error: {e}"
        elif package.lead.url:
            ats_status = f"Manual Apply Link: {package.lead.url}"

        combined_dispatch = f"Email: {email_status} | ATS: {ats_status}"
        package.dispatch_status = combined_dispatch

        # 3. Synchronize to Notion CRM
        notion_success, page_id_or_err = push_to_notion(package)
        if notion_success:
            package.notion_page_id = page_id_or_err
            logger.info(f"Pushed {package.company_clean_name} to Notion (Page ID: {page_id_or_err})")
        else:
            logger.warning(f"Notion sync failed for {package.company_clean_name}: {page_id_or_err}")

        # 4. Save to local CSV audit trail
        self._append_to_csv(package)

        return package

    def _append_to_csv(self, pkg: ApplicationPackage):
        """Maintains local historical log of all processed outreach packages."""
        file_exists = self.csv_path.exists()
        try:
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow([
                        "company", "role", "channel", "score", "angle",
                        "contact_name", "contact_email", "linkedin",
                        "dispatch_status", "notion_id", "subject"
                    ])
                writer.writerow([
                    pkg.company_clean_name,
                    pkg.lead.role,
                    pkg.lead.source_channel,
                    pkg.fit.match_score,
                    pkg.fit.selected_angle,
                    pkg.contact.name,
                    pkg.contact.email,
                    pkg.contact.linkedin_url,
                    pkg.dispatch_status,
                    pkg.notion_page_id or "",
                    pkg.cold_email_subject
                ])
        except Exception as e:
            logger.error(f"Failed to append to history CSV: {e}")
