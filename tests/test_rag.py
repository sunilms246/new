"""
Unit Tests for Vector Store RAG Retrieval
Verifies MDN grounding and context retrieval accuracy.
"""

import unittest
from app.vector_store import get_vector_store

class TestRAGVectorStore(unittest.TestCase):
    def setUp(self):
        self.vector_store = get_vector_store()

    def test_target_code_retrieval(self):
        chunk, item = self.vector_store.query("login problem", target_code=401)
        self.assertEqual(item["code"], 401)
        self.assertIn("401 Unauthorized", chunk)
        self.assertIn("https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401", chunk)

    def test_semantic_retrieval(self):
        chunk, item = self.vector_store.query("server crashed unexpectedly during submit")
        self.assertIsNotNone(item)
        self.assertIn("code", item)
        self.assertTrue(len(chunk) > 50)

if __name__ == "__main__":
    unittest.main()
