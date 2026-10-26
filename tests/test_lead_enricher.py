import unittest
from engine.agents.lead_enricher import EnrichmentAgent

class TestEnrichmentAgent(unittest.TestCase):
    def setUp(self):
        self.agent = EnrichmentAgent()

    def test_extract_email_from_text(self):
        text = "Join our team! Send your resume to careers@acmecorp.com or visit our site."
        extracted = self.agent._extract_email_from_text(text)
        self.assertEqual(extracted, "careers@acmecorp.com")

        no_email_text = "Apply via our online form at https://example.com"
        self.assertIsNone(self.agent._extract_email_from_text(no_email_text))

    def test_extract_name_from_linkedin(self):
        name = self.agent._extract_name_from_linkedin("https://www.linkedin.com/in/satya-nadella-1234")
        self.assertEqual(name, "Satya Nadella")

        name2 = self.agent._extract_name_from_linkedin("https://www.linkedin.com/in/john_doe")
        self.assertEqual(name2, "John Doe")

    def test_resolve_canonical_domain_from_job_url(self):
        domain = self.agent._resolve_canonical_domain("Askable", "askable.com", "https://askable.com/jobs/dev-123")
        self.assertEqual(domain, "askable.com")

if __name__ == "__main__":
    unittest.main()
