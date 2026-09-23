"""
Unit Tests for HTTP Status Code Detector
Verifies FR2 & FR6 requirements across standard QA test phrasings.
"""

import unittest
from app.detector import get_detector

class TestStatusCodeDetector(unittest.TestCase):
    def setUp(self):
        self.detector = get_detector()

    def test_explicit_regex_detection(self):
        code, reason, candidates = self.detector.detect("getting 404 error on page load")
        self.assertEqual(code, 404)
        self.assertIn("regex", candidates[0].match_type)

    def test_keyword_login_detection(self):
        code, reason, candidates = self.detector.detect("login problem")
        self.assertEqual(code, 401)
        self.assertTrue(any(c.code in [401, 403] for c in candidates))

    def test_keyword_server_error_detection(self):
        code, reason, candidates = self.detector.detect("getting 500 error on checkout submit")
        self.assertEqual(code, 500)

    def test_keyword_timeout_detection(self):
        code, reason, candidates = self.detector.detect("gateway timeout during payment process")
        self.assertEqual(code, 504)

    def test_keyword_access_denied_detection(self):
        code, reason, candidates = self.detector.detect("forbidden permission denied on admin dashboard")
        self.assertEqual(code, 403)

    def test_manual_override(self):
        code, reason, candidates = self.detector.detect("login problem", manual_override=403)
        self.assertEqual(code, 403)

    def test_no_match_case(self):
        code, reason, candidates = self.detector.detect("button color alignment issue by 5px")
        self.assertIsNone(code)
        self.assertIn("No specific HTTP status code matched", reason)

if __name__ == "__main__":
    unittest.main()
