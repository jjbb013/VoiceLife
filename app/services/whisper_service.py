# -*- coding: utf-8 -*-
"""
Whisper Speech Recognition Service

Encapsulates faster-whisper for Chinese/English speech-to-text transcription.
Uses global lazy-loaded model instance to avoid repeated initialization.
"""

import os
import asyncio
import logging
from typing import Optional

import torch
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global model instance (lazy-loaded singleton)
# ---------------------------------------------------------------------------
_model: Optional[WhisperModel] = None
_model_lock = asyncio.Lock()


def get_model() -> WhisperModel:
    """
    Get or initialize the global WhisperModel instance.

    Environment variables:
        WHISPER_MODEL: Model size (default: "large-v3", options: tiny, base, small, medium, large-v1/2/3)
        WHISPER_DEVICE: Force device (cuda/cpu, auto-detected if not set)
        WHISPER_COMPUTE_TYPE: Force compute type (float16/int8/int8_float16)

    Returns:
        Initialized WhisperModel instance.

    Raises:
        RuntimeError: If model initialization fails.
    """
    global _model

    if _model is not None:
        return _model

    try:
        model_size = os.getenv("WHISPER_MODEL", "large-v3")
        device = os.getenv("WHISPER_DEVICE")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE")

        # Auto-detect device and compute type if not explicitly set
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if compute_type is None:
            compute_type = "float16" if device == "cuda" else "int8"

        logger.info(
            "Initializing Whisper model: size=%s, device=%s, compute_type=%s",
            model_size, device, compute_type,
        )

        _model = WhisperModel(
            model_size_or_path=model_size,
            device=device,
            compute_type=compute_type,
            download_root=os.getenv("WHISPER_DOWNLOAD_ROOT", None),
            local_files_only=False,
        )

        logger.info("Whisper model initialized successfully")
        return _model

    except Exception as exc:
        logger.error("Failed to initialize Whisper model: %s", exc, exc_info=True)
        raise RuntimeError(f"Whisper model initialization failed: {exc}") from exc


def unload_model() -> None:
    """Unload the global Whisper model to free GPU/CPU memory."""
    global _model
    if _model is not None:
        del _model
        _model = None
        # Force garbage collection to release CUDA memory
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Whisper model unloaded")


# ---------------------------------------------------------------------------
# Transcription functions
# ---------------------------------------------------------------------------

def _transcribe_sync(
    audio_path: str,
    language: str = "zh",
    beam_size: int = 5,
    vad_filter: bool = True,
    vad_parameters: Optional[dict] = None,
) -> str:
    """
    Synchronous transcription helper (runs in thread pool).

    Args:
        audio_path: Path to the audio file.
        language: Language code (default: "zh" for Chinese).
        beam_size: Beam size for decoding (default: 5).
        vad_filter: Enable voice activity detection filtering (default: True).
        vad_parameters: Optional VAD parameters dict.

    Returns:
        Concatenated transcript text from all segments.
    """
    model = get_model()

    if vad_parameters is None:
        vad_parameters = {
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 400,
        }

    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=beam_size,
        vad_filter=vad_filter,
        vad_parameters=vad_parameters,
        condition_on_previous_text=True,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
    )

    logger.debug(
        "Transcription info: language=%s, language_probability=%.2f, duration=%.1fs",
        info.language, info.language_probability, info.duration,
    )

    texts = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            texts.append(text)
            logger.debug(
                "Segment [%.2f - %.2f]: %s",
                segment.start, segment.end, text,
            )

    return " ".join(texts)


async def transcribe(
    audio_path: str,
    language: str = "zh",
    beam_size: int = 5,
    vad_filter: bool = True,
) -> str:
    """
    Transcribe an audio file to text using faster-whisper.

    Args:
        audio_path: Absolute path to the audio file (wav, mp3, m4a, etc.).
        language: Language code (default: "zh" for Chinese/English mixed).
        beam_size: Beam search width (default: 5).
        vad_filter: Enable VAD to filter non-speech segments (default: True).

    Returns:
        Full transcript text from all segments concatenated.

    Raises:
        FileNotFoundError: If the audio file does not exist.
        RuntimeError: If transcription fails.

    Example:
        >>> text = await transcribe("/tmp/recording.wav")
        >>> print(text)
        "今天我们要讨论一下项目的进度安排"
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info("Starting transcription for: %s", audio_path)

    try:
        # Run blocking whisper inference in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,  # Uses default executor
            _transcribe_sync,
            audio_path,
            language,
            beam_size,
            vad_filter,
        )

        logger.info(
            "Transcription completed for %s: %d characters",
            audio_path, len(result),
        )
        return result

    except Exception as exc:
        logger.error(
            "Transcription failed for %s: %s", audio_path, exc, exc_info=True,
        )
        raise RuntimeError(f"Transcription failed: {exc}") from exc


async def transcribe_with_segments(
    audio_path: str,
    language: str = "zh",
    beam_size: int = 5,
) -> list[dict]:
    """
    Transcribe audio and return per-segment results with timestamps.

    Args:
        audio_path: Absolute path to the audio file.
        language: Language code (default: "zh").
        beam_size: Beam search width (default: 5).

    Returns:
        List of segment dicts with keys:
            - text (str): Transcribed text for the segment.
            - start (float): Segment start time in seconds.
            - end (float): Segment end time in seconds.
            - confidence (float): Average word-level confidence.

    Raises:
        FileNotFoundError: If the audio file does not exist.
        RuntimeError: If transcription fails.
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info("Starting segmented transcription for: %s", audio_path)

    def _transcribe_segments_sync() -> list[dict]:
        model = get_model()
        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=beam_size,
            vad_filter=True,
            word_timestamps=True,
        )

        results = []
        for segment in segments:
            avg_confidence = 1.0
            if segment.words:
                confidences = [getattr(w, "probability", 0.8) for w in segment.words]
                avg_confidence = sum(confidences) / len(confidences)

            results.append({
                "text": segment.text.strip(),
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "confidence": round(avg_confidence, 3),
            })

        return results

    try:
        loop = asyncio.get_event_loop()
        segments = await loop.run_in_executor(None, _transcribe_segments_sync)

        logger.info(
            "Segmented transcription completed: %d segments", len(segments),
        )
        return segments

    except Exception as exc:
        logger.error(
            "Segmented transcription failed for %s: %s",
            audio_path, exc, exc_info=True,
        )
        raise RuntimeError(f"Segmented transcription failed: {exc}") from exc
