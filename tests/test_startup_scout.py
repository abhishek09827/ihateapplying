import unittest
from engine.agents.startup_scout import clean_domain_from_url, FundedStartupAgent

class TestStartupScout(unittest.TestCase):
    def test_clean_domain_from_url(self):
        self.assertEqual(clean_domain_from_url("https://apollographql.com/", "Apollo"), "apollographql.com")
        self.assertEqual(clean_domain_from_url("https://www.langfuse.com", "Langfuse"), "langfuse.com")
        self.assertEqual(clean_domain_from_url("https://github.com/coollabsio/coolify", "Coolify"), "coolify.com")
        self.assertEqual(clean_domain_from_url("", "TradingAgents"), "tradingagents.com")
        self.assertEqual(clean_domain_from_url("https://ossean.com/langflow/langflow", "Langflow"), "langflow.com")

    def test_fetch_curated_startups(self):
        scout = FundedStartupAgent()
        leads = scout._fetch_curated_startups(limit=3)
        self.assertGreater(len(leads), 0)
        lead = leads[0]
        self.assertTrue(lead.company)
        self.assertTrue(lead.domain)
        self.assertEqual(lead.source_channel, "Curated AI Startup")
        self.assertTrue(lead.is_remote)

if __name__ == "__main__":
    unittest.main()
