import unittest
from engine.tools.email_verifier import (
    verify_and_clean_email,
    is_unhelpful_generic_email,
    generate_person_email_permutations,
    is_likely_human_name
)

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

    def test_email_permutations(self):
        perms = generate_person_email_permutations("John Doe", "stripe.com")
        self.assertEqual(len(perms), 5)
        # 1. firstname@
        self.assertEqual(perms[0], "john@stripe.com")
        # 2. firstinitial@
        self.assertEqual(perms[1], "j@stripe.com")
        # 3. firstinitiallastinitial@
        self.assertEqual(perms[2], "jd@stripe.com")
        # 4. firstname.lastname@
        self.assertEqual(perms[3], "john.doe@stripe.com")
        # 5. firstinitial.lastname@
        self.assertEqual(perms[4], "j.doe@stripe.com")

    def test_email_permutations_with_titles_and_accents(self):
        perms = generate_person_email_permutations("Brandon Thomas (Founder & CEO)", "getartcraft.com")
        self.assertEqual(perms, [
            "brandon@getartcraft.com",
            "b@getartcraft.com",
            "bt@getartcraft.com",
            "brandon.thomas@getartcraft.com",
            "b.thomas@getartcraft.com"
        ])

        perms_accent = generate_person_email_permutations("Jürgen Klopp", "liverpool.com")
        self.assertEqual(perms_accent[0], "jurgen@liverpool.com")
        self.assertEqual(perms_accent[3], "jurgen.klopp@liverpool.com")

    def test_email_permutations_single_name(self):
        perms = generate_person_email_permutations("Gabriel", "langflow.org")
        self.assertEqual(perms, ["gabriel@langflow.org", "g@langflow.org"])

    def test_email_permutations_non_human(self):
        self.assertEqual(generate_person_email_permutations("Founder / CTO", "acme.com"), [])
        self.assertEqual(generate_person_email_permutations("Engineering Leadership", "acme.com"), [])
        self.assertEqual(generate_person_email_permutations("Not mentioned", "acme.com"), [])
        self.assertEqual(generate_person_email_permutations("Not publicly identified", "acme.com"), [])

    def test_is_likely_human_name(self):
        self.assertTrue(is_likely_human_name("John Doe"))
        self.assertTrue(is_likely_human_name("Ari Gilberg"))
        self.assertTrue(is_likely_human_name("Brandon Thomas (Founder)"))
        self.assertFalse(is_likely_human_name("Founder / CTO"))
        self.assertFalse(is_likely_human_name("Engineering Leadership"))
        self.assertFalse(is_likely_human_name("Not mentioned"))
        self.assertFalse(is_likely_human_name("Not publicly identified (Unknown)"))

if __name__ == "__main__":
    unittest.main()
