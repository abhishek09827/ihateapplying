import unittest
from engine.tools.profile_matcher import is_candidate_profile_match

class TestProfileMatcher(unittest.TestCase):
    def test_matching_target_roles(self):
        target_roles = ["Software Engineer", "Full Stack Engineer", "Backend Developer"]
        self.assertTrue(is_candidate_profile_match("Full Stack Software Engineer", "Build web services in Python and React", target_roles, 3))
        self.assertTrue(is_candidate_profile_match("Backend Developer", "Work with APIs and databases", target_roles, 3))
        self.assertTrue(is_candidate_profile_match("Software Engineer - Core Platform", "Scaling distributed services", target_roles, 3))

    def test_seniority_rejection(self):
        target_roles = ["Software Engineer"]
        self.assertFalse(is_candidate_profile_match("Staff Software Engineer", "Tech leadership", target_roles, 3))
        self.assertFalse(is_candidate_profile_match("Principal Software Engineer", "Architecture lead", target_roles, 3))
        self.assertFalse(is_candidate_profile_match("VP of Engineering", "Management", target_roles, 3))

    def test_unrelated_roles(self):
        target_roles = ["Software Engineer", "AI Engineer"]
        self.assertFalse(is_candidate_profile_match("Account Executive", "Drive B2B sales quota", target_roles, 3))
        self.assertFalse(is_candidate_profile_match("Clinical Nurse Specialist", "Patient care", target_roles, 3))
        self.assertFalse(is_candidate_profile_match("Content Marketing Manager", "Social media campaigns", target_roles, 3))

if __name__ == "__main__":
    unittest.main()
