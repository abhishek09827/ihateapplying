import unittest
from unittest.mock import patch
from engine.state import JobLead, ContactInfo, FitEvaluation
from engine.agents.crafter import ApplicationCrafterAgent
from engine.tools.email_client import format_email_body_with_links


class TestApplicationCrafterAgent(unittest.TestCase):
    def setUp(self):
        self.crafter = ApplicationCrafterAgent()
        self.lead = JobLead(
            company="ClickHouse",
            domain="clickhouse.com",
            role="Streaming Data Engineer",
            source_channel="Greenhouse Board API",
            url="https://clickhouse.com",
            description="Real-time analytics and columnar database scaling Kafka ingestion pipelines.",
            is_remote=True
        )
        self.contact = ContactInfo(name="Alexey Milovidov", title="CTO")
        self.fit = FitEvaluation(
            match_score=88,
            qualified=True,
            selected_angle="High-Throughput Streaming & Data Infrastructure",
            fit_reasoning="Data streaming and Kafka matching",
            estimated_salary_fit="Pass",
            seniority_fit="Pass"
        )

    @patch("engine.agents.crafter.build_tailored_pdf")
    @patch.object(ApplicationCrafterAgent, "generate_json")
    def test_craft_human_anti_spam_email(self, mock_generate_json, mock_pdf):
        mock_pdf.return_value = "/tmp/test_resume.pdf"
        mock_generate_json.return_value = {
            "company_clean_name": "ClickHouse",
            "cold_email_subject": "kafka ingestion — clickhouse",
            "cold_email_body": (
                "Hey Alexey,\n\n"
                "Saw ClickHouse is expanding its streaming ingestion connectors. I've spent a lot of time "
                "building Kafka pipelines handling 40K records/sec and serverless PySpark validation jobs "
                "that cut pipeline latency by 35%.\n\n"
                "Are you bringing on engineers for the ingestion side right now?\n\n"
                "I've attached my tailored resume for your review."
            ),
            "linkedin_note": "Hey Alexey, been following ClickHouse's streaming ingestion work and wanted to connect.",
            "tailored_resume_bullets": [
                "Engineered event-driven streaming pipelines handling 40K rec/sec with Kafka.",
                "Built distributed data validation pipelines with PySpark and Delta Lake."
            ]
        }

        with patch("engine.agents.crafter.validate_pdf_attachment", return_value=True):
            package = self.crafter.craft(self.lead, self.contact, self.fit)

        self.assertEqual(package.company_clean_name, "ClickHouse")
        self.assertNotIn("—", package.cold_email_subject)
        self.assertNotIn("Tailored PDF", package.cold_email_body)
        self.assertNotIn("tailored 1-page pdf", package.cold_email_body.lower())
        self.assertNotIn("tailored resume", package.cold_email_body.lower())
        self.assertNotIn("Verified Links:", package.cold_email_body)
        self.assertNotIn("•", package.cold_email_body)
        self.assertNotIn("📎", package.cold_email_body)
        self.assertEqual(len(package.tailored_resume_bullets), 2)
        self.assertEqual(package.dispatch_status, "Draft Ready")

        call_prompt = mock_generate_json.call_args[0][0]
        self.assertIn("CANDIDATE PROOF-OF-WORK CATALOG:", call_prompt)
        self.assertIn("PROSE ONLY — NO BULLET POINTS", call_prompt)
        self.assertIn("NEVER mention attaching a resume", call_prompt)

    def test_format_email_strips_attached_tailored_resume_lines(self):
        raw = (
            "Hi team,\n\n"
            "Working on similar distributed storage tooling — would love to connect.\n"
            "(Tailored PDF also attached)\n"
            "📎 Tailored 1-page PDF resume is also attached for your convenience."
        )
        formatted = format_email_body_with_links(raw)
        self.assertNotIn("Tailored PDF", formatted)
        self.assertNotIn("Tailored 1-page PDF", formatted)
        self.assertNotIn("📎", formatted)
        self.assertNotIn("—", formatted)
        self.assertNotIn("Verified Links:", formatted)


if __name__ == "__main__":
    unittest.main()
