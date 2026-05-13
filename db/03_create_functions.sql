-- ============================================================
-- AILife Project - Database Migration: Step 03
-- Vector Search Functions & Stored Procedures
-- ============================================================
-- PostgreSQL 15 + pgvector

-- ------------------------------------------------------------
-- Function 1: match_speakers
-- Purpose: Voiceprint similarity search using 192-dim ECAPA-TDNN embeddings
-- Parameters:
--   query_embedding  - 192-dim voice embedding to search for
--   match_threshold  - Minimum cosine similarity (recommended: 0.65)
--   match_count      - Maximum number of results to return
--   p_user_id        - Filter by user_id for multi-tenant isolation
-- Returns: Table of speaker id, name, and similarity score
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_speakers(
  query_embedding vector(192),
  match_threshold float,
  match_count int,
  p_user_id uuid
)
RETURNS TABLE(
  id uuid,
  name text,
  similarity float
) LANGUAGE sql STABLE AS $$
  SELECT
    speakers.id,
    speakers.name,
    1 - (speakers.embedding <=> query_embedding) AS similarity
  FROM speakers
  WHERE speakers.user_id = p_user_id
    AND speakers.embedding IS NOT NULL
    AND 1 - (speakers.embedding <=> query_embedding) > match_threshold
  ORDER BY speakers.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- ------------------------------------------------------------
-- Function 2: match_utterances
-- Purpose: Semantic search using 768-dim BGE embeddings
-- Parameters:
--   query_embedding  - 768-dim text embedding to search for
--   match_threshold  - Minimum cosine similarity (recommended: 0.65)
--   match_count      - Maximum number of results to return
--   p_user_id        - Filter by user_id for multi-tenant isolation
-- Returns: Table of utterance id, text, speaker name, timestamp, and similarity score
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_utterances(
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  p_user_id uuid
)
RETURNS TABLE(
  id uuid,
  text text,
  speaker_name text,
  created_at timestamp,
  similarity float
) LANGUAGE sql STABLE AS $$
  SELECT
    u.id,
    u.text,
    s.name as speaker_name,
    u.created_at,
    1 - (u.embedding <=> query_embedding) AS similarity
  FROM utterances u
  JOIN recordings r ON u.recording_id = r.id
  LEFT JOIN speakers s ON u.speaker_id = s.id
  WHERE r.user_id = p_user_id
    AND u.embedding IS NOT NULL
    AND 1 - (u.embedding <=> query_embedding) > match_threshold
  ORDER BY u.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- ------------------------------------------------------------
-- Function 3: get_user_weekly_stats
-- Purpose: Aggregate conversation statistics for weekly report generation
-- Parameters:
--   p_user_id    - User UUID to aggregate stats for
--   p_week_start - Start date of the week (inclusive)
--   p_week_end   - End date of the week (inclusive)
-- Returns: JSONB object containing total recordings, utterances, speakers, duration, emotion breakdown
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_user_weekly_stats(
  p_user_id uuid,
  p_week_start date,
  p_week_end date
)
RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE
  result jsonb;
BEGIN
  SELECT jsonb_build_object(
    'total_recordings', COUNT(DISTINCT r.id),
    'total_utterances', COUNT(u.id),
    'unique_speakers', COUNT(DISTINCT u.speaker_id),
    'total_duration', COALESCE(SUM(r.duration_sec), 0),
    'emotion_breakdown', jsonb_object_agg(
      COALESCE(u.emotion, '未知'),
      COUNT(*)
    ) FILTER (WHERE u.emotion IS NOT NULL)
  )
  INTO result
  FROM recordings r
  LEFT JOIN utterances u ON r.id = u.recording_id
  WHERE r.user_id = p_user_id
    AND r.created_at >= p_week_start
    AND r.created_at < p_week_end + interval '1 day';

  RETURN COALESCE(result, '{}'::jsonb);
END;
$$;

-- ------------------------------------------------------------
-- Function 4: get_speaker_timeline
-- Purpose: Get chronological utterances for a specific speaker
-- Parameters:
--   p_speaker_id - Speaker UUID
--   p_limit      - Maximum number of results
-- Returns: Table of utterance details ordered by time
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_speaker_timeline(
  p_speaker_id uuid,
  p_limit int DEFAULT 50
)
RETURNS TABLE(
  utterance_id uuid,
  text text,
  recording_id uuid,
  start_sec float,
  end_sec float,
  emotion text,
  created_at timestamp
) LANGUAGE sql STABLE AS $$
  SELECT
    u.id AS utterance_id,
    u.text,
    u.recording_id,
    u.start_sec,
    u.end_sec,
    u.emotion,
    u.created_at
  FROM utterances u
  WHERE u.speaker_id = p_speaker_id
  ORDER BY u.created_at DESC
  LIMIT p_limit;
$$;

-- ------------------------------------------------------------
-- Function 5: search_speaker_utterances
-- Purpose: Semantic search within a specific speaker's utterances
-- Parameters:
--   query_embedding  - 768-dim text embedding
--   match_threshold  - Minimum cosine similarity
--   match_count      - Maximum results
--   p_speaker_id     - Target speaker UUID
-- Returns: Table of matching utterances with similarity scores
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION search_speaker_utterances(
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  p_speaker_id uuid
)
RETURNS TABLE(
  id uuid,
  text text,
  similarity float,
  created_at timestamp
) LANGUAGE sql STABLE AS $$
  SELECT
    u.id,
    u.text,
    1 - (u.embedding <=> query_embedding) AS similarity,
    u.created_at
  FROM utterances u
  WHERE u.speaker_id = p_speaker_id
    AND u.embedding IS NOT NULL
    AND 1 - (u.embedding <=> query_embedding) > match_threshold
  ORDER BY u.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- ------------------------------------------------------------
-- Function 6: get_recent_events
-- Purpose: Get upcoming and recent events for a user
-- Parameters:
--   p_user_id - User UUID
--   p_days    - Number of days to look ahead and behind
-- Returns: Table of events within the time window
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_recent_events(
  p_user_id uuid,
  p_days int DEFAULT 7
)
RETURNS TABLE(
  event_id uuid,
  title text,
  event_date timestamp,
  event_type text,
  status text,
  related_speaker_ids uuid[]
) LANGUAGE sql STABLE AS $$
  SELECT
    e.id AS event_id,
    e.title,
    e.event_date,
    e.event_type,
    e.status,
    e.related_speaker_ids
  FROM events e
  WHERE e.user_id = p_user_id
    AND e.status = 'active'
    AND e.event_date BETWEEN NOW() - interval '1 day' * p_days AND NOW() + interval '1 day' * p_days
  ORDER BY e.event_date;
$$;

-- Print summary
DO $$
BEGIN
    RAISE NOTICE 'All AILife functions created successfully.';
END $$;
