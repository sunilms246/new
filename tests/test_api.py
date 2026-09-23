"""
Unit Tests for FastAPI REST Endpoints
"""

import unittest
from fastapi.testclient import TestClient
from app.main import app

class TestFastAPIApp(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")

    def test_status_codes_endpoint(self):
        response = self.client.get("/api/status-codes")
        self.assertEqual(response.status_code, 200)
        codes = response.json()
        self.assertTrue(len(codes) > 5)

    def test_generate_endpoint_http_grounded(self):
        payload = {"raw_input": "getting 500 error on checkout submit"}
        response = self.client.post("/api/generate", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["transparency"]["detected_code"], 500)
        self.assertTrue(data["is_http_grounded"])
        self.assertIn("steps_to_reproduce", data)

    def test_generate_endpoint_no_match(self):
        payload = {"raw_input": "unrelated styling bug button margin"}
        response = self.client.post("/api/generate", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["is_http_grounded"])

if __name__ == "__main__":
    unittest.main()
