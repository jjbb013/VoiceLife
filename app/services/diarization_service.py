# -*- coding: utf-8 -*-
"""
Speaker Diarization Service

Encapsulates pyannote.audio for speaker diarization (who spoke when).
Uses global lazy-loaded pipeline to avoid repeated initialization.

Requires:
    - HuggingFace token with access to pyannote/speaker-diarization-3.1
    - Accept gated model usage on HuggingFace Hub
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import List, Dict, Optional

import torch
from pyannote.audio import Pipeline
from pyannote.core import Annotation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global pipeline instance (lazy-loaded singleton)
# ---------------------------------------------------------------------------
_pipeline: Optional[Pipeline] = None
_pipeline_lock = asyncio.Lock()


def get_pipeline() -> Pipeline:
    """
    Get or initialize the global pyannote diarization pipeline.

    Environment variables:
        HF_TOKEN: HuggingFace authentication token (required).
        DIARIZATION_DEVICE: Force device (cuda/cpu, auto-detected if not set).
        DIARIZATION_MIN_SPEAKERS: Minimum number of speakers.
        DIARIZATION_MAX_SPEAKERS: Maximum number of speakers.

    Returns:
        Initialized pyannote Pipeline instance.

    Raises:
        RuntimeError: If pipeline initialization fails (missing token, network, etc.).
    """
    global _pipeline

    if _pipeline is not None:
        return _pipeline

    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        logger.error("HF_TOKEN environment variable is not set")
        raise RuntimeError(
            "HF_TOKEN is required for pyannote.audio speaker diarization. "
            "Please set it in your environment or .env file."
        )

    try:
        logger.info(
            "Initializing pyannote speaker diarization pipeline (3.1) ...",
        )

        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token,
            cache_dir=os.getenv("HF_CACHE_DIR", None),
        )

        if _pipeline is None:
            raise RuntimeError("Pipeline.from_pretrained returned None")

        # Move to GPU if available
        device_setting = os.getenv("DIARIZATION_DEVICE")
        if device_setting:
            device = torch.device(device_setting)
        elif torch.cuda.is_available():
            device = torch.device("cuda")
        else:
            device = torch.device("cpu")

        if device.type == "cuda":
            _pipeline.to(device)
            logger.info("Diarization pipeline moved to CUDA")

        # Optional: configure speaker count constraints
        min_speakers = os.getenv("DIARIZATION_MIN_SPEAKERS")
        max_speakers = os.getenv("DIARIZATION_MAX_SPEAKERS")
        if min_speakers:
            _pipeline.min_speakers = int(min_speakers)
        if max_speakers:
            _pipeline.max_speakers = int(max_speakers)

        logger.info("Speaker diarization pipeline initialized successfully")
        return _pipeline

    except Exception as exc:
        logger.error(
            "Failed to initialize diarization pipeline: %s", exc, exc_info=True,
        )
        raise RuntimeError(
            f"Diarization pipeline initialization failed: {exc}. "
            f"Ensure HF_TOKEN is valid and you have accepted the gated model usage."
        ) from exc


def unload_pipeline() -> None:
    """Unload the global diarization pipeline to free GPU/CPU memory."""
    global _pipeline
    if _pipeline is not None:
        del _pipeline
        _pipeline = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Diarization pipeline unloaded")


# ---------------------------------------------------------------------------
# Diarization functions
# ---------------------------------------------------------------------------

def _diarize_sync(audio_path: str, num_speakers: Optional[int] = None) -> Annotation:
    """
    Synchronous diarization helper (runs in thread pool).

    Args:
        audio_path: Path to the audio file.
        num_speakers: Optional fixed number of speakers.

    Returns:
        pyannote Annotation object with speaker labels.
    """
    pipeline = get_pipeline()

    # Build inference parameters
    params: Dict = {}
    if num_speakers is not None:
        params["num_speakers"] = num_speakers

    return pipeline(audio_path, **params)


async def diarize(
    audio_path: str,
    num_speakers: Optional[int] = None,
) -> List[Dict]:
    """
    Perform speaker diarization on an audio file.

    Identifies "who spoke when" and returns a list of speaker segments
    with start/end timestamps.

    Args:
        audio_path: Absolute path to the audio file.
        num_speakers: Optional hint for the number of speakers.

    Returns:
        List of segment dicts, each containing:
            - speaker (str): Speaker label, e.g., "SPEAKER_00", "SPEAKER_01"
            - start (float): Segment start time in seconds.
            - end (float): Segment end time in seconds.
            - duration (float): Segment duration in seconds.

    Raises:
        FileNotFoundError: If the audio file does not exist.
        RuntimeError: If diarization fails.

    Example:
        >>> segments = await diarize("/tmp/meeting.wav")
        >>> print(segments)
        [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 3.5, "duration": 3.5},
            {"speaker": "SPEAKER_01", "start": 3.8, "end": 8.2, "duration": 4.4},
        ]
    """
    # Check if diarization is enabled
    if os.getenv("ENABLE_DIARIZATION", "true").lower() in ("false", "0", "no", "off"):
        logger.info("Speaker diarization is disabled (ENABLE_DIARIZATION=false)")
        return []

    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info("Starting speaker diarization for: %s", audio_path)

    try:
        # Run blocking diarization in a thread pool
        loop = asyncio.get_event_loop()
        annotation: Annotation = await loop.run_in_executor(
            None,
            _diarize_sync,
            audio_path,
            num_speakers,
        )

        # Convert pyannote Annotation to list of dicts
        results = []
        for speech_turn, _, speaker_label in annotation.itertracks(yield_label=True):
            start = round(speech_turn.start, 2)
            end = round(speech_turn.end, 2)
            duration = round(end - start, 2)

            # Skip very short segments (< 0.3s) as they are likely noise
            if duration < 0.3:
                continue

            results.append({
                "speaker": speaker_label,
                "start": start,
                "end": end,
                "duration": duration,
            })

        # Sort by start time
        results.sort(key=lambda x: x["start"])

        # Report unique speaker count
        unique_speakers = set(seg["speaker"] for seg in results)
        logger.info(
            "Diarization completed: %d segments, %d unique speakers",
            len(results), len(unique_speakers),
        )

        return results

    except Exception as exc:
        logger.error(
            "Diarization failed for %s: %s", audio_path, exc, exc_info=True,
        )
        raise RuntimeError(f"Speaker diarization failed: {exc}") from exc


async def diarize_and_label(
    audio_path: str,
    speaker_labels: Optional[Dict[str, str]] = None,
    num_speakers: Optional[int] = None,
) -> List[Dict]:
    """
    Perform diarization and optionally remap speaker labels to real names.

    Args:
        audio_path: Absolute path to the audio file.
        speaker_labels: Optional mapping from auto labels to real names,
            e.g., {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
        num_speakers: Optional hint for the number of speakers.

    Returns:
        Same format as `diarize()`, but with remapped speaker names if provided.
    """
    segments = await diarize(audio_path, num_speakers)

    if speaker_labels:
        for seg in segments:
            original = seg["speaker"]
            seg["speaker"] = speaker_labels.get(original, original)
            seg["speaker_id"] = original  # Keep original ID for reference

    return segments
