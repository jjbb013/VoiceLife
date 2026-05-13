# -*- coding: utf-8 -*-
"""
Voice Embedding Service

Extracts 192-dimensional speaker embeddings using SpeechBrain ECAPA-TDNN.
Used for speaker identification / voice-print matching.

Reference:
    https://huggingface.co/speechbrain/ecapa-tdnn
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import List

import torch
import torchaudio

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global classifier instance (lazy-loaded singleton)
# ---------------------------------------------------------------------------
_classifier = None
_classifier_lock = asyncio.Lock()


def get_classifier():
    """
    Get or initialize the global SpeechBrain ECAPA-TDNN classifier.

    Environment variables:
        EMBEDDING_DEVICE: Force device (cuda/cpu, auto-detected if not set).
        EMBEDDING_CACHE_DIR: Cache directory for pretrained models.

    Returns:
        Initialized EncoderClassifier instance.

    Raises:
        RuntimeError: If classifier initialization fails.
    """
    global _classifier

    if _classifier is not None:
        return _classifier

    try:
        logger.info(
            "Initializing SpeechBrain ECAPA-TDNN classifier ...",
        )

        # SpeechBrain uses its own loading mechanism
        cache_dir = os.getenv("EMBEDDING_CACHE_DIR", "pretrained_models/ecapa-tdnn")

        # Import here to allow optional dependency
        try:
            from speechbrain.pretrained import EncoderClassifier
        except ImportError:
            raise RuntimeError(
                "speechbrain is not installed. "
                "Install it with: pip install speechbrain"
            )

        _classifier = EncoderClassifier.from_hparams(
            source="speechbrain/ecapa-tdnn",
            savedir=cache_dir,
        )

        # Move to appropriate device
        device_setting = os.getenv("EMBEDDING_DEVICE")
        if device_setting:
            device = torch.device(device_setting)
        elif torch.cuda.is_available():
            device = torch.device("cuda")
        else:
            device = torch.device("cpu")

        _classifier = _classifier.to(device)
        logger.info("ECAPA-TDNN classifier initialized on %s", device)

        return _classifier

    except Exception as exc:
        logger.error(
            "Failed to initialize embedding classifier: %s", exc, exc_info=True,
        )
        raise RuntimeError(f"Embedding classifier initialization failed: {exc}") from exc


def unload_classifier() -> None:
    """Unload the global classifier to free GPU/CPU memory."""
    global _classifier
    if _classifier is not None:
        del _classifier
        _classifier = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Embedding classifier unloaded")


# ---------------------------------------------------------------------------
# Embedding extraction functions
# ---------------------------------------------------------------------------

def _extract_embedding_sync(audio_path: str) -> List[float]:
    """
    Synchronous embedding extraction helper.

    Args:
        audio_path: Path to the audio file.

    Returns:
        192-dimensional speaker embedding as a list of floats.

    Raises:
        RuntimeError: If extraction fails.
    """
    classifier = get_classifier()

    # Load audio
    signal, fs = torchaudio.load(audio_path)

    # Resample to 16kHz if needed (ECAPA-TDNN expects 16kHz)
    if fs != 16000:
        resampler = torchaudio.transforms.Resample(orig_freq=fs, new_freq=16000)
        signal = resampler(signal)

    # Convert stereo to mono if needed
    if signal.shape[0] > 1:
        signal = torch.mean(signal, dim=0, keepdim=True)

    # Ensure batch dimension
    if signal.ndim == 1:
        signal = signal.unsqueeze(0)

    # Extract embedding
    embeddings = classifier.encode_batch(signal)

    # embeddings shape: (batch, 192) or (batch, 1, 192)
    if embeddings.ndim == 3:
        embeddings = embeddings.squeeze(1)

    # Normalize to unit vector (cosine similarity friendly)
    embeddings = torch.nn.functional.normalize(embeddings, dim=1)

    # Return as list of floats
    return embeddings.squeeze(0).cpu().tolist()


async def extract_embedding(audio_path: str) -> List[float]:
    """
    Extract a 192-dimensional speaker embedding from an audio file.

    Uses SpeechBrain ECAPA-TDNN model. The embedding is L2-normalized
    and can be compared using cosine similarity.

    Args:
        audio_path: Absolute path to the audio file.

    Returns:
        List of 192 float values representing the voice print.

    Raises:
        FileNotFoundError: If the audio file does not exist.
        RuntimeError: If embedding extraction fails.

    Example:
        >>> emb = await extract_embedding("/tmp/voice_sample.wav")
        >>> len(emb)
        192
        >>> type(emb[0])
        <class 'float'>
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info("Extracting voice embedding from: %s", audio_path)

    try:
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            _extract_embedding_sync,
            audio_path,
        )

        logger.info(
            "Voice embedding extracted: %d dimensions", len(embedding),
        )
        return embedding

    except Exception as exc:
        logger.error(
            "Embedding extraction failed for %s: %s",
            audio_path, exc, exc_info=True,
        )
        raise RuntimeError(f"Embedding extraction failed: {exc}") from exc


def cosine_similarity(emb_a: List[float], emb_b: List[float]) -> float:
    """
    Compute cosine similarity between two embeddings.

    Args:
        emb_a: First embedding vector.
        emb_b: Second embedding vector.

    Returns:
        Cosine similarity score between -1.0 and 1.0.
        Values > 0.65 typically indicate the same speaker.
    """
    import numpy as np

    a = torch.tensor(emb_a, dtype=torch.float32)
    b = torch.tensor(emb_b, dtype=torch.float32)

    similarity = torch.nn.functional.cosine_similarity(a.unsqueeze(0), b.unsqueeze(0))
    return float(similarity.item())


async def compare_voices(
    audio_path_a: str,
    audio_path_b: str,
) -> dict:
    """
    Compare two voice samples and return similarity score.

    Args:
        audio_path_a: Path to first audio file.
        audio_path_b: Path to second audio file.

    Returns:
        Dict with keys:
            - similarity (float): Cosine similarity score.
            - is_same_speaker (bool): True if similarity >= 0.65.
            - confidence (str): "high" | "medium" | "low" based on thresholds.
    """
    emb_a = await extract_embedding(audio_path_a)
    emb_b = await extract_embedding(audio_path_b)

    sim = cosine_similarity(emb_a, emb_b)

    if sim >= 0.75:
        confidence = "high"
    elif sim >= 0.65:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "similarity": round(sim, 4),
        "is_same_speaker": sim >= 0.65,
        "confidence": confidence,
    }
