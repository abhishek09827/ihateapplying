import unittest
from unittest.mock import patch, MagicMock
from engine.state import JobLead, ContactInfo, FitEvaluation
from engine.agents.crafter import ApplicationCrafterAgent

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
    def test_craft_package_generation(self, mock_generate_json, mock_pdf):
        mock_pdf.return_value = "/tmp/test_resume.pdf"
        mock_generate_json.return_value = {
            "company_clean_name": "ClickHouse",
            "cold_email_subject": "scaling clickhouse's kafka ingestion pipelines",
            "cold_email_body": (
                "Hi Alexey,\n\n"
                "I'm Alex, an AI & systems engineer. I saw ClickHouse's work on real-time analytics "
                "and wanted to reach out about helping scale your streaming infrastructure.\n\n"
                "Two things from my background that may be relevant:\n"
                "- Scaled Kafka streaming to 40K records/sec with event-driven pipelines.\n"
                "- Designed serverless data validation pipelines reducing latency by 35%.\n\n"
                "I think I could help scale your Kafka ingestion pipelines quickly. Worth a chat?"
            ),
            "linkedin_note": "Hi Alexey, saw ClickHouse's real-time streaming scale. Would love to connect.",
            "tailored_resume_bullets": [
                "Engineered event-driven streaming pipelines handling 40K rec/sec with Kafka.",
                "Built distributed data validation pipelines with PySpark and Delta Lake."
            ]
        }

        with patch("engine.agents.crafter.validate_pdf_attachment", return_value=True):
            package = self.crafter.craft(self.lead, self.contact, self.fit)

        self.assertEqual(package.company_clean_name, "ClickHouse")
        self.assertIn("scaling clickhouse", package.cold_email_subject.lower())
        self.assertIn("Two things from my background that may be relevant:", package.cold_email_body)
        self.assertIn("Worth a chat?", package.cold_email_body)
        self.assertEqual(len(package.tailored_resume_bullets), 2)
        self.assertEqual(package.dispatch_status, "Draft Ready")

        # Verify the prompt passed to generate_json contains proof-of-work catalog and domain matching rules
        call_prompt = mock_generate_json.call_args[0][0]
        self.assertIn("CANDIDATE PROOF-OF-WORK CATALOG:", call_prompt)
        self.assertIn("DYNAMICALLY MATCHED TO ClickHouse's BACKGROUND & REQUIREMENTS", call_prompt)
        self.assertIn("Two things from my background that may be relevant:", call_prompt)

if __name__ == "__main__":
    unittest.main()
