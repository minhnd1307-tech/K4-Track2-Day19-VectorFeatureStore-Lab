"""HybridMemoryAgent: Minimal POC combining Vector Store and Feature Store for Personal AI Memory.

Implements the Bonus Challenge specifications:
1. Episodic Memory (Vector Store): remember notes/docs/conversations per user,
   retrieve via filtered search (user_id isolation).
2. Stable Profile & Activity (Feature Store): online lookup for topic affinity,
   reading speed, language, and recent query velocity.
3. Context Assembly: synthesizes episodic memory and user profile into structured context.
"""
from __future__ import annotations

import os
import re
import sys
import time
import warnings
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi

# Add repo root to sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.embeddings import Embedder

BONUS_COLLECTION = "bonus_episodic_memory"


class HybridMemoryAgent:
    """Personal AI Assistant memory combining episodic vector memory and feature store profile."""

    def __init__(
        self,
        client: QdrantClient | None = None,
        embedder: Embedder | None = None,
        feast_repo_path: Path | None = None,
    ) -> None:
        self.client = client or QdrantClient(":memory:")
        self.embedder = embedder or Embedder()
        self.dim = self.embedder.dim
        self.feast_repo_path = feast_repo_path or (_REPO_ROOT / "app" / "feast_repo")

        # Initialize Qdrant collection for episodic memory
        existing = {c.name for c in self.client.get_collections().collections}
        if BONUS_COLLECTION not in existing:
            self.client.create_collection(
                collection_name=BONUS_COLLECTION,
                vectors_config=models.VectorParams(
                    size=self.dim, distance=models.Distance.COSINE
                ),
            )

        # In-memory document storage for BM25 sparse retrieval
        self._docs: list[dict[str, Any]] = []
        self._bm25: BM25Okapi | None = None
        self._next_id: int = 0

        # Feast store; defaults keep the standalone demo usable before NB4.
        self._fs = None
        self._init_feast()

    def _init_feast(self) -> None:
        """Attempt to load Feast FeatureStore if registry.db exists."""
        try:
            from feast import FeatureStore
            if (self.feast_repo_path / "registry.db").exists():
                self._fs = FeatureStore(repo_path=str(self.feast_repo_path))
        except Exception as exc:
            warnings.warn(f"Feast unavailable; using demo defaults: {exc}")
            self._fs = None

    def _chunk_text(self, text: str, max_words: int = 60, overlap: int = 15) -> list[str]:
        """Sliding windows of whitespace tokens; no sentence segmentation."""
        words = text.strip().split()
        if len(words) <= max_words:
            return [text.strip()]
        chunks = []
        start = 0
        step = max_words - overlap
        while start < len(words):
            chunk = " ".join(words[start : start + max_words])
            chunks.append(chunk)
            if start + max_words >= len(words):
                break
            start += step
        return chunks

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\w+(?:[-/]\w+)*", text.casefold())

    def remember(self, text: str, user_id: str = "u_001") -> None:
        """Add a new piece of episodic memory for this user."""
        if not text.strip() or not user_id.strip():
            raise ValueError("text and user_id must be non-empty")
        chunks = self._chunk_text(text)
        points = []
        for chunk in chunks:
            vec = next(self.embedder.embed([chunk])).tolist()
            doc_record = {
                "id": self._next_id,
                "user_id": user_id,
                "text": chunk,
                "created_at": time.time(),
            }
            self._docs.append(doc_record)
            points.append(
                models.PointStruct(
                    id=self._next_id,
                    vector=vec,
                    payload={"user_id": user_id, "text": chunk, "id": self._next_id},
                )
            )
            self._next_id += 1

        self.client.upsert(collection_name=BONUS_COLLECTION, points=points)

        # Rebuild BM25 on updated docs
        tokenized = [self._tokenize(d["text"]) for d in self._docs]
        if tokenized:
            self._bm25 = BM25Okapi(tokenized)

    def _get_user_features(self, user_id: str) -> dict[str, Any]:
        """Fetch stable profile + real-time velocity from Feast or fallback defaults."""
        features = {
            "reading_speed_wpm": 220,
            "preferred_language": "vi",
            "topic_affinity": "cloud",
            "queries_last_hour": 3,
            "distinct_topics_24h": 2,
        }
        if self._fs is not None:
            try:
                out = self._fs.get_online_features(
                    features=[
                        "user_profile_features:reading_speed_wpm",
                        "user_profile_features:preferred_language",
                        "user_profile_features:topic_affinity",
                        "query_velocity_features:queries_last_hour",
                        "query_velocity_features:distinct_topics_24h",
                    ],
                    entity_rows=[{"user_id": user_id}],
                ).to_dict()
                for k, v in out.items():
                    clean_k = k.split(":")[-1]
                    if v and v[0] is not None:
                        features[clean_k] = v[0]
            except Exception as exc:
                warnings.warn(f"Feast lookup failed; using demo defaults: {exc}")
        return features

    def recall(self, query: str, user_id: str = "u_001", top_k: int = 3) -> str:
        """Retrieve top-K memories + user profile features -> return assembled context."""
        if not query.strip() or not user_id.strip() or top_k < 1:
            raise ValueError("query/user_id must be non-empty and top_k positive")
        # 1. Get user profile + recent activity from Feature Store
        prof = self._get_user_features(user_id)

        # 2. Hybrid search Qdrant filtered by user_id
        q_vec = next(self.embedder.embed([query])).tolist()
        user_filter = models.Filter(
            must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id))]
        )

        dense_hits = self.client.query_points(
            collection_name=BONUS_COLLECTION,
            query=q_vec,
            query_filter=user_filter,
            limit=top_k * 2,
        ).points

        # BM25 filtered by user_id
        user_doc_indices = [
            (i, d) for i, d in enumerate(self._docs) if d["user_id"] == user_id
        ]
        bm25_scores: dict[int, float] = {}
        if self._bm25 and user_doc_indices:
            q_tokens = self._tokenize(query)
            all_scores = self._bm25.get_scores(q_tokens)
            for idx, d in user_doc_indices:
                if all_scores[idx] > 0:
                    bm25_scores[d["id"]] = float(all_scores[idx])

        # RRF Fusion (k=60)
        rrf_scores: dict[int, float] = {}
        text_lookup: dict[int, str] = {}

        # dense rank
        for rank, p in enumerate(dense_hits, start=1):
            doc_id = p.payload["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (60.0 + rank)
            text_lookup[doc_id] = p.payload["text"]

        # sparse rank
        sparse_sorted = sorted(bm25_scores.items(), key=lambda kv: -kv[1])
        for rank, (doc_id, _) in enumerate(sparse_sorted, start=1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (60.0 + rank)
            for d in self._docs:
                if d["id"] == doc_id:
                    text_lookup[doc_id] = d["text"]
                    break

        ordered_hits = sorted(rrf_scores.items(), key=lambda kv: -kv[1])[:top_k]
        top_memories = [text_lookup[doc_id] for doc_id, _ in ordered_hits]

        # 3. Assemble context string
        mem_str = " | ".join(top_memories) if top_memories else "(No relevant episodic memory found)"
        context = (
            f"User likes {prof['topic_affinity']} reading at {prof['reading_speed_wpm']} wpm "
            f"(Language: {prof['preferred_language']}).\n"
            f"Recent activity: {prof['queries_last_hour']} queries in last hour "
            f"across {prof['distinct_topics_24h']} distinct topics.\n"
            f"Top memories: {mem_str}"
        )
        return context
