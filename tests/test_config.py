import unittest
from engine.config import load_config, clean_uuid

class TestConfig(unittest.TestCase):
    def test_load_config_defaults(self):
        cfg = load_config()
        self.assertIsNotNone(cfg)
        self.assertIsInstance(cfg.target_roles, list)
        self.assertTrue(len(cfg.target_roles) > 0)
        self.assertTrue(bool(cfg.candidate_name))

    def test_clean_uuid(self):
        uuid_raw = "12345678123412341234123456789abc"
        cleaned = clean_uuid(uuid_raw)
        self.assertEqual(cleaned, "12345678-1234-1234-1234-123456789abc")

        url_raw = "https://notion.so/myworkspace/12345678123412341234123456789abc?v=123"
        cleaned_from_url = clean_uuid(url_raw)
        self.assertEqual(cleaned_from_url, "12345678-1234-1234-1234-123456789abc")

    def test_credential_aliases(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {
            "GMAIL_USER": "",
            "GMAIL_SENDER": "testuser@gmail.com",
            "GMAIL_APP_PASSWORD": "abcd efgh ijkl mnop",
            "NOTION_TOKEN": "",
            "NOTION_API_KEY": "secret_notion_key_123"
        }):
            cfg = load_config()
            self.assertEqual(cfg.gmail_sender, "testuser@gmail.com")
            self.assertEqual(cfg.gmail_app_password, "abcdefghijklmnop")
            self.assertEqual(cfg.notion_api_key, "secret_notion_key_123")
    def test_resume_drive_url_resolution(self):
        import os
        from unittest.mock import patch
        from engine.config import _resolve_resume_drive_url

        # Test valid alias
        with patch.dict(os.environ, {"RESUME_DRIVE_URL": "", "RESUME_URL": "https://drive.google.com/file/d/custom_resume_id/view"}):
            url = _resolve_resume_drive_url()
            self.assertEqual(url, "https://drive.google.com/file/d/custom_resume_id/view")

        # Test placeholder rejected and falls back
        with patch.dict(os.environ, {"RESUME_DRIVE_URL": "https://drive.google.com/file/d/YOUR_GOOGLE_DRIVE_RESUME_ID/view?usp=sharing"}):
            url = _resolve_resume_drive_url()
            self.assertNotIn("YOUR_GOOGLE_DRIVE_RESUME_ID", url)
            self.assertTrue(url.startswith("https://drive.google.com/file/d/"))

    def test_format_email_body_self_healing(self):
        from engine.tools.email_client import format_email_body_with_links
        # Email with placeholder should be replaced
        raw_body = "Hi,\nHere is my resume: https://drive.google.com/file/d/YOUR_GOOGLE_DRIVE_RESUME_ID/view?usp=sharing\nBest regards"
        formatted = format_email_body_with_links(raw_body)
        self.assertNotIn("YOUR_GOOGLE_DRIVE_RESUME_ID", formatted)
        self.assertIn("18kbu7pKjkYbaVGCq50BTCSFxtznOFUAT", formatted)

        # Email missing Drive link but having other links should get Drive link injected
        body_with_some_links = "Hi team,\nHere are my links:\n• Portfolio: https://www.abhibuilds.work\n• GitHub: https://github.com/abhishek09827"
        formatted_with_drive = format_email_body_with_links(body_with_some_links)
        self.assertIn("drive.google.com", formatted_with_drive)

if __name__ == "__main__":
    unittest.main()

