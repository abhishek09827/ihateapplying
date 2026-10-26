import unittest
from engine.tools.email_verifier import (
    verify_and_clean_email,
    is_valid_email_syntax,
    does_domain_have_mx
)

class TestEmailVerifier(unittest.TestCase):
    def test_valid_email(self):
        is_valid, clean, reason = verify_and_clean_email("founder@google.com")
        self.assertTrue(is_valid)
        self.assertEqual(clean, "founder@google.com")

    def test_disposable_domain_rejection(self):
        is_valid, clean, reason = verify_and_clean_email("user@mailinator.com")
        self.assertFalse(is_valid)
        self.assertIn("Disposable", reason)

    def test_placeholder_rejection(self):
        is_valid, clean, reason = verify_and_clean_email("null@google.com")
        self.assertFalse(is_valid)
        self.assertIn("placeholder", reason.lower())

        is_valid, clean, reason = verify_and_clean_email("undefined@google.com")
        self.assertFalse(is_valid)
        self.assertIn("placeholder", reason.lower())

    def test_invalid_syntax(self):
        self.assertFalse(is_valid_email_syntax("not-an-email"))
        self.assertFalse(is_valid_email_syntax("@missingusername.com"))
        self.assertTrue(is_valid_email_syntax("valid.user+tag@domain.co.uk"))

        is_valid, clean, reason = verify_and_clean_email("not-an-email")
        self.assertFalse(is_valid)
        self.assertIn("syntax", reason.lower())

    def test_empty_email(self):
        is_valid, clean, reason = verify_and_clean_email("")
        self.assertFalse(is_valid)

    def test_domain_mx_verification(self):
        self.assertTrue(does_domain_have_mx("google.com"))
        self.assertFalse(does_domain_have_mx("thisdomaindoesnotexist123456789xyz.com"))

if __name__ == "__main__":
    unittest.main()
