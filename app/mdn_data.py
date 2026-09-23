"""
MDN HTTP Status Dataset Loader
Provides access to MDN HTTP status documentation with caching via HuggingFace datasets or local JSON.
"""

import os
import json
from typing import List, Dict, Any, Optional

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mdn_http_status.json")

class MDNDataLoader:
    def __init__(self):
        self._dataset: List[Dict[str, Any]] = []
        self._by_code: Dict[int, Dict[str, Any]] = {}
        self.load_data()

    def load_data(self):
        """Loads data from local JSON or datasets cache."""
        try:
            # Try loading via HuggingFace datasets library if available
            try:
                from datasets import Dataset
                # Check if cached or load from dict/json
                if os.path.exists(DATA_PATH):
                    with open(DATA_PATH, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    ds = Dataset.from_list(raw_data)
                    self._dataset = ds.to_list()
                else:
                    self._dataset = raw_data
            except Exception as e:
                # Fallback to direct json reading
                if os.path.exists(DATA_PATH):
                    with open(DATA_PATH, "r", encoding="utf-8") as f:
                        self._dataset = json.load(f)
                else:
                    self._dataset = []
        except Exception as err:
            print(f"Error loading MDN data: {err}")
            self._dataset = []

        # Index by status code
        self._by_code = {item["code"]: item for item in self._dataset if "code" in item}

    def get_all(self) -> List[Dict[str, Any]]:
        return self._dataset

    def get_by_code(self, code: int) -> Optional[Dict[str, Any]]:
        return self._by_code.get(code)

    def get_formatted_chunk(self, code: int) -> str:
        item = self.get_by_code(code)
        if not item:
            return f"No specific MDN documentation chunk available for HTTP Status Code {code}."
        
        causes = "\n".join([f"- {c}" for c in item.get("causes", [])])
        return (
            f"MDN HTTP Status Documentation Chunk for {item['name']} ({item['category']}):\n\n"
            f"Summary: {item['summary']}\n\n"
            f"Description: {item['description']}\n\n"
            f"Common QA Causes:\n{causes}\n\n"
            f"Recommended Fix: {item.get('remediation', 'N/A')}\n"
            f"Source URL: {item['mdn_url']} (CC-BY-SA)"
        )

_loader_instance = None

def get_mdn_loader() -> MDNDataLoader:
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = MDNDataLoader()
    return _loader_instance
