import unittest
from engine.tools.entity_validator import (
    extract_github_owner_repo,
    validate_github_repo_metadata,
    is_blocked_github_slug,
    is_free_hosting_or_raw_repo,
    classify_entity_commercial_vs_hobby,
    GITHUB_BLOCKED_ROUTES,
    GENERIC_INVALID_COMPANY_NAMES
)

class TestEntityValidator(unittest.TestCase):

    def test_blocked_routes_and_slugs(self):
        self.assertTrue(is_blocked_github_slug("explore", "explore"))
        self.assertTrue(is_blocked_github_slug("repo", "rules"))
        self.assertTrue(is_blocked_github_slug("cursor", "plugins"))
        self.assertTrue(is_blocked_github_slug("trending", "python"))
        self.assertTrue(is_blocked_github_slug("github", "explore"))
        self.assertFalse(is_blocked_github_slug("twentyhq", "twenty"))
        self.assertFalse(is_blocked_github_slug("langfuse", "langfuse"))

    def test_extract_github_owner_repo(self):
        # Valid GitHub repositories
        self.assertEqual(extract_github_owner_repo("https://github.com/twentyhq/twenty"), ("twentyhq", "twenty"))
        self.assertEqual(extract_github_owner_repo("twentyhq/twenty"), ("twentyhq", "twenty"))
        self.assertEqual(extract_github_owner_repo("https://github.com/langfuse/langfuse/"), ("langfuse", "langfuse"))
        self.assertEqual(extract_github_owner_repo("https://github.com/coollabsio/coolify.git"), ("coollabsio", "coolify"))

        # Blocked UI routes, breadcrumbs, single segments
        self.assertIsNone(extract_github_owner_repo("https://github.com/explore"))
        self.assertIsNone(extract_github_owner_repo("https://github.com/cursor/plugins"))
        self.assertIsNone(extract_github_owner_repo("repo/rules"))
        self.assertIsNone(extract_github_owner_repo("/rules"))
        self.assertIsNone(extract_github_owner_repo("xiaobei"))
        self.assertIsNone(extract_github_owner_repo("https://github.com/features/actions"))

    def test_is_free_hosting_or_raw_repo(self):
        self.assertTrue(is_free_hosting_or_raw_repo("github.com"))
        self.assertTrue(is_free_hosting_or_raw_repo("myproject.github.io"))
        self.assertTrue(is_free_hosting_or_raw_repo("cool-app.vercel.app"))
        self.assertTrue(is_free_hosting_or_raw_repo("https://ossean.com/ai-apps"))
        self.assertTrue(is_free_hosting_or_raw_repo("https://goodfirstissue.dev/python"))

        self.assertFalse(is_free_hosting_or_raw_repo("twenty.com"))
        self.assertFalse(is_free_hosting_or_raw_repo("langfuse.com"))
        self.assertFalse(is_free_hosting_or_raw_repo("portkey.ai"))
        self.assertFalse(is_free_hosting_or_raw_repo("modal.com"))

    def test_classify_entity_commercial_vs_hobby(self):
        # 1. Trusted commercial job boards
        is_comm, reason, meta = classify_entity_commercial_vs_hobby(
            company="Anthropic",
            domain="anthropic.com",
            source_channel="Greenhouse Board API"
        )
        self.assertTrue(is_comm)
        self.assertEqual(meta.get("entity_type"), "Commercial Startup")

        # 2. Blocked UI scrapes / Generic route segments
        is_comm, reason, meta = classify_entity_commercial_vs_hobby(
            company="Explore",
            domain="explore.com",
            source_channel="GitHub Explore"
        )
        self.assertFalse(is_comm)

        is_comm, reason, meta = classify_entity_commercial_vs_hobby(
            company="Repo Rules",
            domain="reporules.com",
            source_channel="GitHub Explore"
        )
        self.assertFalse(is_comm)

        # 3. Commercial Startup with custom domain and company LinkedIn
        is_comm, reason, meta = classify_entity_commercial_vs_hobby(
            company="Twenty",
            domain="twenty.com",
            lead_url="https://twenty.com",
            source_channel="OSSEAN AI Apps"
        )
        self.assertTrue(is_comm)
        self.assertEqual(meta.get("entity_type"), "Commercial Startup")

        # 4. Hobby repo without custom domain or company LinkedIn
        is_comm, reason, meta = classify_entity_commercial_vs_hobby(
            company="rikkahub",
            domain="",
            lead_url="https://github.com/rikka/rikkahub",
            source_channel="OSSEAN AI Apps"
        )
        self.assertFalse(is_comm)
        self.assertEqual(meta.get("entity_type"), "Hobby / Student Experiment")

if __name__ == "__main__":
    unittest.main()
