import unittest
from engine.tools.email_verifier import verify_and_clean_email

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

if __name__ == "__main__":
    unittest.main()
