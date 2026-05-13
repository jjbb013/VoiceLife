# -*- coding: utf-8 -*-
"""
Vector Embedding & Semantic Search Service

Uses BGE (BAAI/bge-small-zh-v1.5) for text embedding and
pgvector in PostgreSQL (via asyncpg) for similarity search.

BGE-small-zh-v1.5 produces 512-dimensional embeddings.
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global BGE model instance (lazy-loaded singleton)
# ---------------------------------------------------------------------------
_bge_model = None
_bge_model_lock = asyncio.Lock()

BGE_MODEL_NAME = os.getenv("BGE_MODEL", "BAAI/bge-small-zh-v1.5")
EMBEDDING_DIM = 512  # bge-small-zh-v1.5 outputs 512-dim vectors


def get_bge_model():
    """
    Get or initialize the global SentenceTransformer (BGE) model.

    Environment variables:
        BGE_MODEL: Model name (default: BAAI/bge-small-zh-v1.5).
        SENTENCE_TRANSFORMERS_HOME: Cache directory.

    Returns:
        Initialized SentenceTransformer instance.

    Raises:
        RuntimeError: If model initialization fails.
    """
    global _bge_model

    if _bge_model is not None:
        return _bge_model

    try:
        logger.info("Loading BGE model: %s", BGE_MODEL_NAME)

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Install it with: pip install sentence-transformers"
            )

        _bge_model = SentenceTransformer(BGE_MODEL_NAME)
        logger.info(
            "BGE model loaded: %s, embedding_dim=%d",
            BGE_MODEL_NAME, EMBEDDING_DIM,
        )
        return _bge_model

    except Exception as exc:
        logger.error(
            "Failed to load BGE model: %s", exc, exc_info=True,
        )
        raise RuntimeError(f"BGE model initialization failed: {exc}") from exc


def unload_bge_model() -> None:
    """Unload the global BGE model to free memory."""
    global _bge_model
    if _bge_model is not None:
        del _bge_model
        _bge_model = None
        logger.info("BGE model unloaded")


# ---------------------------------------------------------------------------
# Embedding functions
# ---------------------------------------------------------------------------

def _embed_sync(texts: List[str]) -> np.ndarray:
    """
    Synchronous embedding helper (runs in thread pool).

    Args:
        texts: List of text strings to embed.

    Returns:
        NumPy array of shape (len(texts), EMBEDDING_DIM).
    """
    model = get_bge_model()
    return model.encode(
        texts,
        normalize_embeddings=True,  # L2-normalize for cosine similarity
        convert_to_numpy=True,
        show_progress_bar=False,
    )


async def embed_text(text: str) -> List[float]:
    """
    Embed a single text into a vector using BGE model.

    Args:
        text: The text string to encode.

    Returns:
        List of 512 float values (L2-normalized).

    Raises:
        ValueError: If text is empty.
        RuntimeError: If embedding fails.

    Example:
        >>> vec = await embed_text("\u4eca\u5929\u5929\u6c14\u771f\u597d")
        >>> len(vec)
        512
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    try:
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            _embed_sync,
            [text],
        )
        return embedding[0].tolist()

    except Exception as exc:
        logger.error("Text embedding failed: %s", exc, exc_info=True)
        raise RuntimeError(f"Text embedding failed: {exc}") from exc


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed multiple texts in batch.

    Args:
        texts: List of text strings.

    Returns:
        List of embedding vectors, one per input text.
    """
    if not texts:
        return []

    try:
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            _embed_sync,
            texts,
        )
        return [emb.tolist() for emb in embeddings]

    except Exception as exc:
        logger.error("Batch text embedding failed: %s", exc, exc_info=True)
        raise RuntimeError(f"Batch embedding failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Native pgvector search via asyncpg
# ---------------------------------------------------------------------------

def _embedding_to_vector(embedding: List[float]) -> str:
    """Convert embedding list to PostgreSQL vector literal string.

    Args:
        embedding: List of float values.

    Returns:
        PostgreSQL vector literal like "[0.1,0.2,...]".
    """
    return "[" + ",".join(str(x) for x in embedding) + "]"


async def search_utterances(
    user_id: str,
    query: str,
    top_k: int = 10,
    threshold: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Semantic search over historical utterances using pgvector.

    Uses native asyncpg SQL with pgvector <=> operator for similarity search.

    Args:
        user_id: The user to scope the search to.
        query: Natural language query string.
        top_k: Maximum number of results (default: 10).
        threshold: Minimum similarity threshold (default: 0.3).

    Returns:
        List of utterance dicts, each containing:
            - id: Utterance UUID
            - recording_id: Parent recording UUID
            - speaker_name: Speaker name
            - text: Utterance text content
            - created_at: Timestamp
            - similarity: Cosine similarity score

    Raises:
        RuntimeError: If search fails.

    Example:
        >>> results = await search_utterances("user_001", "\u9879\u76ee\u8fdb\u5ea6")
        >>> print(results[0]["text"])
        "\u6211\u4eec\u9879\u76ee\u5df2\u7ecf\u8fdb\u884c\u5230\u7b2c\u4e8c\u9636\u6bb5\u4e86"
    """
    if not query or not query.strip():
        return []

    logger.info(
        "Searching utterances for user=%s, query='%s', top_k=%d",
        user_id, query, top_k,
    )

    try:
        from app.db import db

        # 1. Embed the query
        query_embedding = await embed_text(query)
        query_vector = _embedding_to_vector(query_embedding)

        # 2. Native pgvector SQL search
        rows = await db.fetch(
            """
            SELECT
                u.id,
                u.recording_id,
                s.name as speaker_name,
                u.text,
                u.start_sec,
                u.end_sec,
                u.created_at,
                1 - (u.embedding <=> $1::vector) as similarity
            FROM utterances u
            JOIN recordings r ON u.recording_id = r.id
            LEFT JOIN speakers s ON u.speaker_id = s.id
            WHERE r.user_id = $2 AND u.embedding IS NOT NULL
              AND 1 - (u.embedding <=> $1::vector) > $3
            ORDER BY u.embedding <=> $1::vector
            LIMIT $4
            """,
            query_vector, user_id, threshold, top_k,
        )

        # Format results
        formatted = []
        for row in rows:
            formatted.append({
                "id": str(row["id"]),
                "recording_id": str(row["recording_id"]) if row["recording_id"] else None,
                "speaker": row["speaker_name"] or "\u672a\u77e5",
                "text": row["text"] or "",
                "start": row["start_sec"],
                "end": row["end_sec"],
                "similarity": round(row["similarity"], 4) if row["similarity"] else 0.0,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })

        logger.info("Search returned %d results", len(formatted))
        return formatted

    except Exception as exc:
        logger.error(
            "Utterance search failed: %s", exc, exc_info=True,
        )
        raise RuntimeError(f"Semantic search failed: {exc}") from exc


async def search_similar_utterances_by_vector(
    user_id: str,
    embedding: List[float],
    top_k: int = 10,
    threshold: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Search utterances using a pre-computed embedding vector.

    Args:
        user_id: The user to scope the search to.
        embedding: Pre-computed embedding vector.
        top_k: Maximum number of results.
        threshold: Minimum similarity threshold.

    Returns:
        Same format as search_utterances().
    """
    logger.info(
        "Vector search for user=%s, top_k=%d", user_id, top_k,
    )

    try:
        from app.db import db

        query_vector = _embedding_to_vector(embedding)

        rows = await db.fetch(
            """
            SELECT
                u.id,
                u.recording_id,
                s.name as speaker_name,
                u.text,
                u.start_sec,
                u.end_sec,
                u.created_at,
                1 - (u.embedding <=> $1::vector) as similarity
            FROM utterances u
            JOIN recordings r ON u.recording_id = r.id
            LEFT JOIN speakers s ON u.speaker_id = s.id
            WHERE r.user_id = $2 AND u.embedding IS NOT NULL
              AND 1 - (u.embedding <=> $1::vector) > $3
            ORDER BY u.embedding <=> $1::vector
            LIMIT $4
            """,
            query_vector, user_id, threshold, top_k,
        )

        formatted = []
        for row in rows:
            formatted.append({
                "id": str(row["id"]),
                "recording_id": str(row["recording_id"]) if row["recording_id"] else None,
                "speaker": row["speaker_name"] or "\u672a\u77e5",
                "text": row["text"] or "",
                "start": row["start_sec"],
                "end": row["end_sec"],
                "similarity": round(row["similarity"], 4) if row["similarity"] else 0.0,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })

        return formatted

    except Exception as exc:
        logger.error("Vector utterance search failed: %s", exc, exc_info=True)
        raise RuntimeError(f"Vector search failed: {exc}") from exc


async def store_utterance_embedding(
    utterance_id: str,
    embedding: List[float],
) -> None:
    """
    Store/update the embedding vector for an utterance.

    Args:
        utterance_id: The utterance UUID.
        embedding: The embedding vector to store.

    Raises:
        RuntimeError: If update fails.
    """
    try:
        from app.db import db

        vector_str = _embedding_to_vector(embedding)

        await db.execute(
            """
            UPDATE utterances
            SET embedding = $1::vector
            WHERE id = $2
            """,
            vector_str, utterance_id,
        )

        logger.debug("Stored embedding for utterance: %s", utterance_id)

    except Exception as exc:
        logger.error(
            "Failed to store utterance embedding: %s", exc, exc_info=True,
        )
        raise RuntimeError(f"Failed to store embedding: {exc}") from exc


# ---------------------------------------------------------------------------
# Utility: cosine similarity computation
# ---------------------------------------------------------------------------

def compute_similarity(
    vec_a: List[float],
    vec_b: List[float],
) -> float:
    """
    Compute cosine similarity between two embedding vectors.

    Args:
        vec_a: First embedding vector.
        vec_b: Second embedding vector.

    Returns:
        Cosine similarity score between 0.0 and 1.0
        (assuming L2-normalized vectors, range is [-1, 1]).
    """
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))
