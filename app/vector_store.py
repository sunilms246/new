"""
Vector Store & RAG Retrieval Module for MDN HTTP Documentation
Integrates SentenceTransformers / FAISS / TF-IDF vector retrieval with cached MDN chunks.
"""

import os
from typing import Dict, Any, List, Optional, Tuple
from app.mdn_data import get_mdn_loader

class RAGVectorStore:
    def __init__(self):
        self.mdn_loader = get_mdn_loader()
        self.docs = self.mdn_loader.get_all()
        self.encoder = None
        self.vector_index = None
        self.is_transformer_active = False
        self._init_vector_store()

    def _init_vector_store(self):
        """Initializes sentence-transformers or sklearn TF-IDF vectorizer fallback."""
        try:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
            texts = [f"{d['name']} {d['summary']} {d['description']} {' '.join(d.get('keywords', []))}" for d in self.docs]
            self.doc_embeddings = self.encoder.encode(texts, show_progress_bar=False)
            self.is_transformer_active = True
            print("VectorStore: Loaded SentenceTransformer (all-MiniLM-L6-v2) successfully.")
        except Exception as e:
            print(f"VectorStore: SentenceTransformers fallback to TF-IDF vectorizer: {e}")
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
                self.tfidf = TfidfVectorizer(stop_words='english')
                texts = [f"{d['name']} {d['summary']} {d['description']} {' '.join(d.get('keywords', []))}" for d in self.docs]
                self.doc_vectors = self.tfidf.fit_transform(texts)
                self.cosine_sim = cosine_similarity
                self.is_transformer_active = False
            except Exception as err:
                print(f"VectorStore TF-IDF fallback init failed: {err}")

    def query(self, query_text: str, target_code: Optional[int] = None, top_k: int = 3) -> Tuple[str, Dict[str, Any]]:
        """
        Retrieves grounded MDN documentation chunk.
        If target_code is specified, retrieves the exact chunk for that status code.
        Otherwise performs semantic vector search across all MDN chunks.
        """
        # Exact code grounding if status code is identified
        if target_code:
            item = self.mdn_loader.get_by_code(target_code)
            if item:
                formatted_chunk = self.mdn_loader.get_formatted_chunk(target_code)
                return formatted_chunk, item

        # Semantic Search Fallback
        if not self.docs:
            return "No MDN documentation available in vector store.", {}

        if self.is_transformer_active and self.encoder is not None:
            import numpy as np
            q_emb = self.encoder.encode([query_text])[0]
            scores = np.dot(self.doc_embeddings, q_emb) / (np.linalg.norm(self.doc_embeddings, axis=1) * np.linalg.norm(q_emb))
            best_idx = int(np.argmax(scores))
            best_item = self.docs[best_idx]
            formatted_chunk = self.mdn_loader.get_formatted_chunk(best_item["code"])
            return formatted_chunk, best_item

        elif hasattr(self, 'tfidf'):
            import numpy as np
            q_vec = self.tfidf.transform([query_text])
            sims = self.cosine_sim(q_vec, self.doc_vectors)[0]
            best_idx = int(np.argmax(sims))
            best_item = self.docs[best_idx]
            formatted_chunk = self.mdn_loader.get_formatted_chunk(best_item["code"])
            return formatted_chunk, best_item

        # Default fallback to first document
        item = self.docs[0]
        return self.mdn_loader.get_formatted_chunk(item["code"]), item

_vector_store_instance = None

def get_vector_store() -> RAGVectorStore:
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = RAGVectorStore()
    return _vector_store_instance
