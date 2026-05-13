# -*- coding: utf-8 -*-
"""
AILife AI/ML Services Package

Provides speech recognition, speaker diarization, voice embedding,
LLM integration, vector search, and audio processing pipelines.
"""

from app.services.whisper_service import transcribe
from app.services.diarization_service import diarize
from app.services.embedding_service import extract_embedding
from app.services.llm_service import (
    analyze_conversation,
    chat_with_memory,
    generate_meeting_summary,
    generate_daily_report,
)
from app.services.vector_service import embed_text, search_utterances
from app.services.audio_processor import process_audio, match_speaker

__all__ = [
    "transcribe",
    "diarize",
    "extract_embedding",
    "analyze_conversation",
    "chat_with_memory",
    "generate_meeting_summary",
    "generate_daily_report",
    "embed_text",
    "search_utterances",
    "process_audio",
    "match_speaker",
]
