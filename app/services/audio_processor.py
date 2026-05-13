# -*- coding: utf-8 -*-
"""
Audio Processing Pipeline Coordinator

Orchestrates the complete audio processing workflow:
    1. Format normalization (wav/16kHz/mono)
    2. Speaker diarization (who spoke when)
    3. Whisper transcription (speech-to-text)
    4. Save recording record to database
    5. Per-segment processing: voice embedding + speaker matching
    6. LLM deep analysis (summary, topics, events, todos, bills, emotions)
    7. Update recording summary and insert derived records

Dependencies:
    - whisper_service
    - diarization_service
    - embedding_service
    - llm_service
    - vector_service
    - asyncpg (via app.db.db)
"""

from __future__ import annotations

import os
import uuid
import asyncio
import logging
import tempfile
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from pydub import AudioSegment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports to avoid circular dependencies
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Audio format normalization
# ---------------------------------------------------------------------------

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_FORMAT = "wav"


def _normalize_audio(input_path: str, output_path: str) -> Dict[str, Any]:
    """
    Normalize audio to standard format: WAV, 16kHz, mono, 16-bit.

    Args:
        input_path: Source audio file path.
        output_path: Destination normalized file path.

    Returns:
        Dict with original and normalized audio metadata.
    """
    audio = AudioSegment.from_file(input_path)

    orig_meta = {
        "channels": audio.channels,
        "sample_rate": audio.frame_rate,
        "duration_ms": len(audio),
        "duration_sec": round(len(audio) / 1000.0, 2),
        "bitrate": audio.frame_width * 8 * audio.frame_rate * audio.channels,
    }

    # Convert to mono
    if audio.channels > TARGET_CHANNELS:
        audio = audio.set_channels(TARGET_CHANNELS)

    # Resample to 16kHz
    if audio.frame_rate != TARGET_SAMPLE_RATE:
        audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)

    # Set sample width to 2 bytes (16-bit)
    if audio.sample_width != 2:
        audio = audio.set_sample_width(2)

    # Export as WAV
    audio.export(output_path, format=TARGET_FORMAT)

    norm_meta = {
        "channels": audio.channels,
        "sample_rate": audio.frame_rate,
        "duration_ms": len(audio),
        "duration_sec": round(len(audio) / 1000.0, 2),
    }

    logger.info(
        "Audio normalized: %s -> %s (%.1fs, %dHz, %dch -> %.1fs, %dHz, %dch)",
        input_path, output_path,
        orig_meta["duration_sec"], orig_meta["sample_rate"], orig_meta["channels"],
        norm_meta["duration_sec"], norm_meta["sample_rate"], norm_meta["channels"],
    )

    return {"original": orig_meta, "normalized": norm_meta}


# ---------------------------------------------------------------------------
# Speaker matching
# ---------------------------------------------------------------------------

SPEAKER_MATCH_THRESHOLD = 0.65  # Cosine similarity threshold


async def match_speaker(
    user_id: str,
    embedding: List[float],
    threshold: float = SPEAKER_MATCH_THRESHOLD,
) -> Optional[str]:
    """
    Match a voice embedding against the known speaker database.

    Uses native pgvector SQL with <=> operator for vector similarity search.

    Args:
        user_id: The user scope for speaker matching.
        embedding: 192-dim voice embedding vector.
        threshold: Minimum cosine similarity to consider a match (default: 0.65).

    Returns:
        Matched speaker_id (UUID) if found, None otherwise.

    Example:
        >>> speaker_id = await match_speaker("user_001", embedding)
        >>> print(speaker_id)
        "550e8400-e29b-41d4-a716-446655440000"
    """
    logger.debug("Matching speaker for user: %s", user_id)

    try:
        from app.db import db

        # Convert embedding list to PostgreSQL vector literal string
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        row = await db.fetchrow(
            """
            SELECT id, name, 1 - (embedding <=> $1::vector) as similarity
            FROM speakers
            WHERE user_id = $2 AND embedding IS NOT NULL
              AND 1 - (embedding <=> $1::vector) > $3
            ORDER BY embedding <=> $1::vector
            LIMIT 1
            """,
            embedding_str, user_id, threshold,
        )

        if row:
            similarity = row["similarity"]
            speaker_id = str(row["id"])
            logger.info(
                "Speaker matched: %s (similarity=%.3f)", speaker_id, similarity,
            )
            return speaker_id

        logger.info("No matching speaker found (threshold=%.2f)", threshold)
        return None

    except Exception as exc:
        logger.error("Speaker matching failed: %s", exc, exc_info=True)
        # Return None on failure -- don't break the pipeline
        return None


async def _create_or_match_speaker(
    user_id: str,
    embedding: List[float],
    speaker_label: str,
) -> Optional[str]:
    """
    Try to match embedding to existing speaker; if no match, create new speaker.

    Args:
        user_id: User scope.
        embedding: Voice embedding vector.
        speaker_label: Auto-generated label like "SPEAKER_00".

    Returns:
        speaker_id (UUID) if matched or created, None on error.
    """
    # Try to find existing match
    matched_id = await match_speaker(user_id, embedding)
    if matched_id:
        return matched_id

    # Create new speaker
    try:
        from app.db import db

        speaker_id = str(uuid.uuid4())
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        await db.execute(
            """
            INSERT INTO speakers (id, user_id, name, embedding, created_at)
            VALUES ($1, $2, $3, $4::vector, $5)
            """,
            speaker_id, user_id, speaker_label, embedding_str,
            datetime.utcnow(),
        )

        logger.info("New speaker created: %s (%s)", speaker_id, speaker_label)
        return speaker_id

    except Exception as exc:
        logger.error("Failed to create speaker: %s", exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Core processing pipeline
# ---------------------------------------------------------------------------

async def process_audio(
    file_path: str,
    user_id: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Complete audio processing pipeline.

    Processes a raw audio file through the full pipeline:
        1. Format normalization (wav/16kHz/mono)
        2. Speaker diarization
        3. Whisper transcription
        4. Save recording to database
        5. Per-segment processing: embedding extraction + speaker matching
        6. LLM deep analysis
        7. Insert derived records (events, todos, bills)

    Args:
        file_path: Absolute path to the uploaded audio file.
        user_id: The user who uploaded the recording.
        meta: Optional metadata dict, may contain:
            - title: Recording title
            - tags: List of tags
            - latitude, longitude: GPS coordinates
            - location_name: Human-readable location

    Returns:
        Dict containing:
            - recording_id (str): UUID of the saved recording.
            - analysis (Dict): LLM analysis results.
            - utterances (List[Dict]): Processed utterance records.
            - speakers (List[str]): Detected speaker labels.

    Raises:
        FileNotFoundError: If the audio file does not exist.
        RuntimeError: If critical pipeline step fails.

    Example:
        >>> result = await process_audio("/tmp/meeting.m4a", "user_001", {"title": "\u5468\u4f1a"})
        >>> print(result["recording_id"])
        "550e8400-e29b-41d4-a716-446655440000"
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    meta = meta or {}
    recording_id = str(uuid.uuid4())
    normalized_path = None

    logger.info(
        "Starting audio pipeline: file=%s, user=%s, recording=%s",
        file_path, user_id, recording_id,
    )

    try:
        # ------------------------------------------------------------------
        # Step 1: Format normalization
        # ------------------------------------------------------------------
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            normalized_path = tmp.name

        audio_meta = _normalize_audio(file_path, normalized_path)
        duration_sec = audio_meta["normalized"]["duration_sec"]

        # ------------------------------------------------------------------
        # Step 2: Speaker diarization (who spoke when)
        # ------------------------------------------------------------------
        from app.services.diarization_service import diarize

        diarization_segments = await diarize(normalized_path)
        logger.info(
            "Diarization completed: %d segments", len(diarization_segments),
        )

        # ------------------------------------------------------------------
        # Step 3: Whisper transcription
        # ------------------------------------------------------------------
        from app.services.whisper_service import transcribe_with_segments

        transcribed_segments = await transcribe_with_segments(normalized_path, language="zh")
        logger.info(
            "Transcription completed: %d segments", len(transcribed_segments),
        )

        # ------------------------------------------------------------------
        # Step 3b: Merge diarization + transcription
        # ------------------------------------------------------------------
        merged_utterances = _merge_segments(diarization_segments, transcribed_segments)
        logger.info(
            "Merged utterances: %d", len(merged_utterances),
        )

        # ------------------------------------------------------------------
        # Step 4: Save recording to database (asyncpg)
        # ------------------------------------------------------------------
        from app.db import db

        now = datetime.utcnow()
        title = meta.get("title", f"\u5f55\u97f3 {now.isoformat()[:19]}")

        await db.execute(
            """
            INSERT INTO recordings (
                id, user_id, audio_url, duration_sec,
                location_lat, location_lng, location_name,
                summary, topics, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            recording_id, user_id, file_path, duration_sec,
            meta.get("latitude"), meta.get("longitude"), meta.get("location_name"),
            None, meta.get("tags", []), now,
        )
        logger.info("Recording saved: %s", recording_id)

        # ------------------------------------------------------------------
        # Step 5: Per-segment processing
        # ------------------------------------------------------------------
        from app.services.embedding_service import extract_embedding
        from app.services.vector_service import embed_text

        utterance_records = []
        full_text_parts = []
        utterance_insert_args: List[tuple] = []

        for idx, utterance in enumerate(merged_utterances):
            speaker_label = utterance["speaker"]
            text = utterance["text"]
            start = utterance["start"]
            end = utterance["end"]

            full_text_parts.append(f"{speaker_label}: {text}")

            utterance_id = str(uuid.uuid4())

            # Try to extract embedding from segment
            speaker_id = None
            embedding_vector = None
            try:
                seg_audio = AudioSegment.from_wav(normalized_path)
                seg_audio = seg_audio[int(start * 1000):int(end * 1000)]

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as seg_tmp:
                    seg_path = seg_tmp.name
                seg_audio.export(seg_path, format="wav")

                # Extract voice embedding
                embedding = await extract_embedding(seg_path)
                embedding_vector = embedding  # Keep raw list for DB

                # Match/create speaker
                speaker_id = await _create_or_match_speaker(
                    user_id, embedding, speaker_label,
                )

                os.unlink(seg_path)

            except Exception as seg_exc:
                logger.warning(
                    "Embedding extraction failed for segment %d: %s",
                    idx, seg_exc,
                )
                embedding = None

            # Compute semantic embedding for vector search
            semantic_embedding = None
            if text:
                try:
                    semantic_embedding = await embed_text(text)
                except Exception as emb_exc:
                    logger.warning(
                        "Semantic embedding failed for segment %d: %s",
                        idx, emb_exc,
                    )

            # Build utterance record (for return)
            utt_record = {
                "id": utterance_id,
                "recording_id": recording_id,
                "user_id": user_id,
                "speaker": speaker_label,
                "speaker_id": speaker_id,
                "text": text,
                "start": start,
                "end": end,
                "embedding": embedding,
                "semantic_embedding": semantic_embedding,
                "created_at": now.isoformat(),
            }
            utterance_records.append(utt_record)

            # Prepare insert args for batch insert
            # Convert embeddings to PostgreSQL vector literals
            sem_emb_str = None
            if semantic_embedding:
                sem_emb_str = "[" + ",".join(str(x) for x in semantic_embedding) + "]"

            utterance_insert_args.append((
                utterance_id, recording_id, speaker_id,
                start, end, text,
                sem_emb_str,
                now,
            ))

        # Batch insert utterances (asyncpg executemany)
        if utterance_insert_args:
            await db.executemany(
                """
                INSERT INTO utterances (
                    id, recording_id, speaker_id,
                    start_sec, end_sec, text,
                    embedding,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8)
                """,
                utterance_insert_args,
            )
            logger.info("Inserted %d utterances", len(utterance_insert_args))

        # ------------------------------------------------------------------
        # Step 6: LLM deep analysis
        # ------------------------------------------------------------------
        from app.services.llm_service import analyze_conversation

        full_text = "\n".join(full_text_parts)

        try:
            analysis = await analyze_conversation(full_text, merged_utterances)
        except Exception as llm_exc:
            logger.error("LLM analysis failed: %s", llm_exc, exc_info=True)
            analysis = {
                "summary": full_text[:100] if full_text else "",
                "topics": [],
                "events": [],
                "todos": [],
                "bills": [],
                "emotions": {},
            }

        # ------------------------------------------------------------------
        # Step 7: Update recording and insert derived records (asyncpg)
        # ------------------------------------------------------------------

        # Update recording with summary
        topics = analysis.get("topics", [])
        topics_json = json.dumps(topics) if topics else None

        await db.execute(
            """
            UPDATE recordings
            SET summary = $1, topics = $2
            WHERE id = $3
            """,
            analysis.get("summary", ""), topics_json, recording_id,
        )

        # Insert events
        events = analysis.get("events", [])
        if events:
            event_args: List[tuple] = []
            for evt in events:
                event_args.append((
                    str(uuid.uuid4()),
                    user_id,
                    evt.get("title", "\u672a\u547d\u540d\u4e8b\u4ef6"),
                    evt.get("event_date"),
                    evt.get("event_type", "other"),
                    now,
                ))
            await db.executemany(
                """
                INSERT INTO events (id, user_id, title, event_date, event_type, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                event_args,
            )
            logger.info("Inserted %d events", len(event_args))

        # Insert todos
        todos = analysis.get("todos", [])
        if todos:
            todo_args: List[tuple] = []
            for todo in todos:
                todo_args.append((
                    str(uuid.uuid4()),
                    user_id,
                    todo.get("title", "\u672a\u547d\u540d\u5f85\u529e"),
                    todo.get("due_date"),
                    todo.get("owner"),
                    now,
                ))
            await db.executemany(
                """
                INSERT INTO todos (id, user_id, title, due_date, source, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                todo_args,
            )
            logger.info("Inserted %d todos", len(todo_args))

        # Insert bills
        bills = analysis.get("bills", [])
        if bills:
            bill_args: List[tuple] = []
            for bill in bills:
                bill_args.append((
                    str(uuid.uuid4()),
                    user_id,
                    bill.get("amount", 0),
                    bill.get("currency", "CNY"),
                    bill.get("category", "\u5176\u4ed6"),
                    bill.get("context", ""),
                    now,
                ))
            await db.executemany(
                """
                INSERT INTO bill_notes (id, user_id, amount, currency, category, context, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                bill_args,
            )
            logger.info("Inserted %d bills", len(bill_args))

        # ------------------------------------------------------------------
        # Cleanup and return
        # ------------------------------------------------------------------
        if normalized_path and os.path.exists(normalized_path):
            os.unlink(normalized_path)

        unique_speakers = list(set(u["speaker"] for u in merged_utterances))

        logger.info(
            "Audio pipeline completed: recording=%s, utterances=%d, speakers=%d",
            recording_id, len(utterance_records), len(unique_speakers),
        )

        return {
            "recording_id": recording_id,
            "analysis": analysis,
            "utterances": utterance_records,
            "speakers": unique_speakers,
        }

    except Exception as exc:
        logger.error(
            "Audio pipeline failed: %s", exc, exc_info=True,
        )

        # Update recording status to failed
        try:
            from app.db import db
            await db.execute(
                """
                UPDATE recordings
                SET summary = $1
                WHERE id = $2
                """,
                f"failed: {exc}", recording_id,
            )
        except Exception:
            pass

        # Cleanup temp file
        if normalized_path and os.path.exists(normalized_path):
            os.unlink(normalized_path)

        raise RuntimeError(f"Audio processing pipeline failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Segment merging utility
# ---------------------------------------------------------------------------

def _merge_segments(
    diarization: List[Dict[str, Any]],
    transcription: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merge diarization and transcription segments.

    For each transcription segment, find the overlapping diarization
    speaker label based on time overlap.

    Args:
        diarization: List of diarization segments with speaker, start, end.
        transcription: List of transcription segments with text, start, end.

    Returns:
        Merged list of utterances with speaker and text.
    """
    if not diarization:
        # No diarization data -- return all text as single unknown speaker
        return [{
            "speaker": "SPEAKER_00",
            "text": " ".join(t.get("text", "") for t in transcription),
            "start": transcription[0]["start"] if transcription else 0.0,
            "end": transcription[-1]["end"] if transcription else 0.0,
        }] if transcription else []

    merged = []
    for tseg in transcription:
        t_start = tseg["start"]
        t_end = tseg["end"]
        t_text = tseg.get("text", "").strip()

        if not t_text:
            continue

        # Find best overlapping speaker
        best_speaker = "SPEAKER_00"
        best_overlap = 0.0

        for dseg in diarization:
            # Compute overlap duration
            overlap_start = max(t_start, dseg["start"])
            overlap_end = min(t_end, dseg["end"])
            overlap = max(0.0, overlap_end - overlap_start)

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = dseg["speaker"]

        merged.append({
            "speaker": best_speaker,
            "text": t_text,
            "start": round(t_start, 2),
            "end": round(t_end, 2),
            "confidence": tseg.get("confidence", 0.8),
        })

    return merged
