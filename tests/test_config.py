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

    def test_ats_board_configs(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {
            "GREENHOUSE_BOARDS": "anthropic,stripe,figma",
            "ASHBY_ORGS": "openai,modal,perplexity"
        }):
            cfg = load_config()
            self.assertEqual(cfg.greenhouse_boards, ["anthropic", "stripe", "figma"])
            self.assertEqual(cfg.ashby_orgs, ["openai", "modal", "perplexity"])

if __name__ == "__main__":
    unittest.main()
