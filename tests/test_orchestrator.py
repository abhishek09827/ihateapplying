import unittest
from unittest.mock import MagicMock, patch
from engine.state import JobLead, ContactInfo, FitEvaluation, ApplicationPackage, PipelineReport
from engine.agents.orchestrator import OutreachOrchestrator

class TestOrchestratorTargetLoop(unittest.TestCase):
    def setUp(self):
        self.orchestrator = OutreachOrchestrator()
        # Mock sub-agents to avoid network/LLM calls
        self.orchestrator.job_scout = MagicMock()
        self.orchestrator.startup_scout = MagicMock()
        self.orchestrator.screener = MagicMock()
        self.orchestrator.enricher = MagicMock()
        self.orchestrator.crafter = MagicMock()
        self.orchestrator.dispatcher = MagicMock()
        self.orchestrator._persist_cache = MagicMock()
        self.orchestrator.seen_companies = set()

    @patch("time.sleep")
    @patch("engine.agents.orchestrator.CACHE_FILE")
    @patch("engine.agents.orchestrator.get_existing_notion_companies", return_value=set())
    def test_target_continues_when_lead_lacks_email(self, mock_notion, mock_cache, mock_sleep):
        """
        Verify that when a lead qualifies but lacks an email, the orchestrator
        does not prematurely terminate, and instead continues until target
        actionable applications with emails are satisfied.
        """
        mock_cache.exists.return_value = False
        # Create 3 candidate leads
        lead_1 = JobLead(company="NoEmailCorp", domain="noemail.com", role="AI Engineer", source_channel="remoteok", url="https://noemail.com", description="Desc 1")
        lead_2 = JobLead(company="EmailCorp", domain="hasemail.com", role="AI Engineer", source_channel="remoteok", url="https://hasemail.com", description="Desc 2")
        lead_3 = JobLead(company="ExtraCorp", domain="extra.com", role="AI Engineer", source_channel="remoteok", url="https://extra.com", description="Desc 3")

        self.orchestrator.job_scout.run.return_value = [lead_1, lead_2, lead_3]
        self.orchestrator.startup_scout.run.return_value = []

        # All leads pass screener
        self.orchestrator.screener.screen.return_value = FitEvaluation(
            match_score=85,
            qualified=True,
            selected_angle="AI Architecture",
            fit_reasoning="Strong match"
        )

        # Lead 1 has no email; Lead 2 has a valid email; Lead 3 has an email
        def mock_enrich(lead):
            if lead.company == "NoEmailCorp":
                return ContactInfo(name="CEO", title="Founder", email="", enrichment_source="LinkedIn Only")
            return ContactInfo(name="Hiring Lead", title="VP Eng", email="founder@emailcorp.com", enrichment_source="Serper")

        self.orchestrator.enricher.enrich.side_effect = mock_enrich

        def mock_craft(lead, contact, fit):
            return ApplicationPackage(
                lead=lead,
                contact=contact,
                fit=fit,
                company_clean_name=lead.company,
                cold_email_subject="Test Subject",
                cold_email_body="Test Body",
                linkedin_note="Test Note",
                tailored_resume_bullets=["Test bullet"],
                pdf_resume_path="test.pdf"
            )

        self.orchestrator.crafter.craft.side_effect = mock_craft

        # Target 1 actionable application
        report = self.orchestrator.run(
            mode="remote-jobs",
            target_qualified=1,
            max_scans=10,
            dry_run=True
        )

        # Both Lead 1 (no email) and Lead 2 (has email) should be evaluated
        # The loop must NOT stop at Lead 1!
        self.assertEqual(report.qualified_count, 2, "Both leads should be counted as score-qualified")
        self.assertEqual(report.missing_email_count, 1, "Lead 1 should be counted as missing email")
        self.assertEqual(report.contactable_count, 1, "Lead 2 should fulfill the 1 actionable target")
        self.assertEqual(report.dispatched_count, 2, "Both leads should be processed through pipeline")

    @patch("time.sleep")
    @patch("engine.agents.orchestrator.CACHE_FILE")
    @patch("engine.agents.orchestrator.get_existing_notion_companies", return_value=set())
    def test_safety_cap_halts_when_no_emails_found(self, mock_notion, mock_cache, mock_sleep):
        """
        Verify that max_scans safety cap stops the loop even if no leads have emails,
        preventing infinite scanning or runaway API usage.
        """
        mock_cache.exists.return_value = False
        leads = [
            JobLead(company=f"NoEmail_{i}", domain=f"noemail{i}.com", role="AI Engineer", source_channel="remoteok", url=f"https://noemail{i}.com", description="Desc")
            for i in range(10)
        ]
        self.orchestrator.job_scout.run.return_value = leads
        self.orchestrator.startup_scout.run.return_value = []

        self.orchestrator.screener.screen.return_value = FitEvaluation(
            match_score=90,
            qualified=True,
            selected_angle="AI Architecture",
            fit_reasoning="Strong match"
        )
        self.orchestrator.enricher.enrich.return_value = ContactInfo(
            name="CEO", title="Founder", email="", enrichment_source="None"
        )
        self.orchestrator.crafter.craft.side_effect = lambda lead, contact, fit: ApplicationPackage(
            lead=lead,
            contact=contact,
            fit=fit,
            company_clean_name=lead.company,
            cold_email_subject="Sub",
            cold_email_body="Body",
            linkedin_note="Note",
            tailored_resume_bullets=["Bullet"]
        )

        # Max scans is capped at 3
        report = self.orchestrator.run(
            mode="remote-jobs",
            target_qualified=5,
            max_scans=3,
            dry_run=True
        )

        self.assertEqual(report.qualified_count, 3)
        self.assertEqual(report.missing_email_count, 3)
        self.assertEqual(report.contactable_count, 0)

if __name__ == "__main__":
    unittest.main()
