import unittest
from engine.tools.email_verifier import verify_and_clean_email, is_unhelpful_generic_email

class TestEmailVerifier(unittest.TestCase):
    def test_valid_email(self):
        is_valid, clean, reason = verify_and_clean_email("founder@google.com")
        self.assertTrue(is_valid)
        self.assertEqual(clean, "founder@google.com")

    def test_disposable_domain_rejection(self):
        is_valid, clean, reason = verify_and_clean_email("test@mailinator.com")
        self.assertFalse(is_valid)
        self.assertIn("Disposable", reason)

    def test_invalid_syntax(self):
        is_valid, clean, reason = verify_and_clean_email("not-an-email")
        self.assertFalse(is_valid)
        self.assertIn("syntax", reason.lower())

    def test_empty_email(self):
        is_valid, clean, reason = verify_and_clean_email("")
        self.assertFalse(is_valid)

    def test_support_and_info_rejection(self):
        self.assertTrue(is_unhelpful_generic_email("support@company.com"))
        self.assertTrue(is_unhelpful_generic_email("info@company.com"))
        self.assertTrue(is_unhelpful_generic_email("help@company.com"))
        self.assertTrue(is_unhelpful_generic_email("billing@company.com"))
        self.assertFalse(is_unhelpful_generic_email("careers@company.com"))
        self.assertFalse(is_unhelpful_generic_email("founder@company.com"))
        self.assertFalse(is_unhelpful_generic_email("marc@company.com"))

        # allow_generic=False should block support/info
        is_valid, clean, reason = verify_and_clean_email("support@google.com", allow_generic=False)
        self.assertFalse(is_valid)
        self.assertIn("support/info", reason)

        # allow_generic=True allows syntax & domain validation only
        is_valid, clean, reason = verify_and_clean_email("support@google.com", allow_generic=True)
        self.assertTrue(is_valid)

if __name__ == "__main__":
    unittest.main()
