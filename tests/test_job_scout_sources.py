import unittest
from unittest.mock import patch, MagicMock
from engine.agents.job_scout import JobScoutAgent
from engine.state import JobLead

SAMPLE_WWR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>We Work Remotely</title>
    <item>
      <title>DuckDuckGo: Applied AI Engineer</title>
      <link>https://weworkremotely.com/remote-jobs/duckduckgo-applied-ai-engineer</link>
      <pubDate>Wed, 21 Oct 2026 13:46:32 +0000</pubDate>
      <description>&lt;p&gt;Looking for an AI engineer with LLM and Python experience.&lt;/p&gt;</description>
      <region>Anywhere in the World</region>
    </item>
    <item>
      <title>PlanetScale: Founding AI Engineer</title>
      <link>https://weworkremotely.com/remote-jobs/planetscale-founding-ai-engineer</link>
      <pubDate>Thu, 22 Oct 2026 10:00:00 +0000</pubDate>
      <description>&lt;p&gt;Join our AI platform team building vector and LLM retrieval infrastructure.&lt;/p&gt;</description>
      <region>Remote US/EU</region>
    </item>
  </channel>
</rss>
"""

SAMPLE_ADZUNA_JSON = {
    "results": [
        {
            "id": "987654",
            "title": "AI Engineer",
            "company": {"display_name": "ScaleGen AI"},
            "location": {"display_name": "Remote, US"},
            "description": "Architect agentic workflows, LLM routing, and high-performance Python services.",
            "redirect_url": "https://www.adzuna.com/land/ad/987654",
            "created": "2026-10-23T12:00:00Z",
            "salary_min": 140000,
            "salary_max": 185000
        }
    ]
}

class TestJobScoutSources(unittest.TestCase):
    def setUp(self):
        self.scout = JobScoutAgent()

    @patch("requests.get")
    def test_fetch_weworkremotely(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = SAMPLE_WWR_RSS.encode("utf-8")
        mock_get.return_value = mock_response

        leads = self.scout._fetch_weworkremotely(limit=5)
        self.assertTrue(len(leads) > 0)
        lead = leads[0]
        self.assertEqual(lead.company, "DuckDuckGo")
        self.assertEqual(lead.role, "Applied AI Engineer")
        self.assertEqual(lead.source_channel, "WeWorkRemotely RSS")
        self.assertEqual(lead.location, "Anywhere in the World")
        self.assertTrue("duckduckgo" in lead.url)

    def test_fetch_adzuna_skipped_when_no_credentials(self):
        with patch.dict("os.environ", {"ADZUNA_APP_ID": "", "ADZUNA_APP_KEY": ""}):
            leads = self.scout._fetch_adzuna(limit=5)
            self.assertEqual(leads, [])

    @patch("requests.get")
    def test_fetch_adzuna_success_with_credentials(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_ADZUNA_JSON
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {"ADZUNA_APP_ID": "test_id_123", "ADZUNA_APP_KEY": "test_key_abc"}):
            leads = self.scout._fetch_adzuna(limit=5)
            self.assertEqual(len(leads), 1)
            lead = leads[0]
            self.assertEqual(lead.company, "ScaleGen AI")
            self.assertEqual(lead.role, "AI Engineer")
            self.assertEqual(lead.source_channel, "Adzuna API")
            self.assertTrue("$140,000" in (lead.salary_raw or ""))

if __name__ == "__main__":
    unittest.main()
