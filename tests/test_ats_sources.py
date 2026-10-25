import unittest
from unittest.mock import patch, MagicMock
from engine.agents.job_scout import JobScoutAgent
from engine.state import JobLead

class TestATSSources(unittest.TestCase):
    def setUp(self):
        self.scout = JobScoutAgent()

    @patch("engine.agents.job_scout.requests.get")
    def test_fetch_greenhouse_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jobs": [
                {
                    "id": 101,
                    "title": "Applied AI Engineer",
                    "company_name": "Anthropic",
                    "absolute_url": "https://job-boards.greenhouse.io/anthropic/jobs/101",
                    "location": {"name": "San Francisco, CA (Remote)"},
                    "content": "<p>Build production LLM agents and evaluation frameworks using Python.</p>",
                    "updated_at": "2026-10-20T12:00:00Z"
                },
                {
                    "id": 102,
                    "title": "VP of Global Marketing",
                    "company_name": "Anthropic",
                    "absolute_url": "https://job-boards.greenhouse.io/anthropic/jobs/102",
                    "location": {"name": "New York, NY"},
                    "content": "<p>15+ years experience leading enterprise marketing teams.</p>",
                    "updated_at": "2026-10-20T12:00:00Z"
                }
            ]
        }
        mock_get.return_value = mock_response

        with patch("engine.config.GREENHOUSE_BOARDS", ["anthropic"]):
            leads = self.scout._fetch_greenhouse(limit=10)

        # Disqualifying VP role should be filtered out, Applied AI Engineer kept
        self.assertEqual(len(leads), 1)
        lead = leads[0]
        self.assertEqual(lead.company, "Anthropic")
        self.assertEqual(lead.role, "Applied AI Engineer")
        self.assertEqual(lead.source_channel, "Greenhouse Board API")
        self.assertTrue(lead.is_remote)
        self.assertIn("job-boards.greenhouse.io/anthropic/jobs/101", lead.url)

    @patch("engine.agents.job_scout.requests.get")
    def test_fetch_ashby_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jobs": [
                {
                    "id": "abc-123",
                    "title": "AI Engineer",
                    "jobUrl": "https://jobs.ashbyhq.com/modal/abc-123",
                    "location": "Remote - Worldwide",
                    "isRemote": True,
                    "descriptionPlain": "Develop scalable Python systems and distributed AI workflows with 2 years experience.",
                    "publishedAt": "2026-10-22T10:00:00Z",
                    "compensation": {
                        "compensationTierSummary": "$140K - $180K"
                    }
                },
                {
                    "id": "abc-456",
                    "title": "Staff Enterprise Architect",
                    "jobUrl": "https://jobs.ashbyhq.com/modal/abc-456",
                    "location": "Remote",
                    "isRemote": True,
                    "descriptionPlain": "Requires 10+ years architecting enterprise legacy transformations.",
                    "publishedAt": "2026-10-22T10:00:00Z"
                }
            ]
        }
        mock_get.return_value = mock_response

        with patch("engine.config.ASHBY_ORGS", ["modal"]):
            leads = self.scout._fetch_ashby(limit=10)

        # Disqualified staff role filtered out, AI Engineer kept
        self.assertEqual(len(leads), 1)
        lead = leads[0]
        self.assertEqual(lead.company, "Modal")
        self.assertEqual(lead.role, "AI Engineer")
        self.assertEqual(lead.source_channel, "Ashby ATS API")
        self.assertEqual(lead.salary_raw, "$140K - $180K")
        self.assertTrue(lead.is_remote)

    @patch("engine.agents.job_scout.requests.get")
    def test_ats_sources_error_resilience(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException("Connection timeout")

        with patch("engine.config.GREENHOUSE_BOARDS", ["anthropic"]):
            gh_leads = self.scout._fetch_greenhouse(limit=5)
            self.assertEqual(gh_leads, [])

        with patch("engine.config.ASHBY_ORGS", ["modal"]):
            ash_leads = self.scout._fetch_ashby(limit=5)
            self.assertEqual(ash_leads, [])

if __name__ == "__main__":
    unittest.main()
