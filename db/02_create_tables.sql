-- ============================================================
-- AILife Project - Database Migration: Step 02
-- Create All Tables with Indexes
-- ============================================================
-- PostgreSQL 15 + pgvector

-- ------------------------------------------------------------
-- 1. speakers: 说话人档案
--    Stores voice embeddings (192-dim ECAPA-TDNN) for speaker identification
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS speakers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name TEXT,
    relation TEXT,
    is_master BOOLEAN DEFAULT FALSE,
    embedding VECTOR(192),
    voice_sample_count INT DEFAULT 0,
    first_met_at TIMESTAMP,
    last_talk_at TIMESTAMP,
    summary TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Speaker indexes
CREATE INDEX IF NOT EXISTS idx_speakers_user_id ON speakers(user_id);
CREATE INDEX IF NOT EXISTS idx_speakers_is_master ON speakers(user_id, is_master);
CREATE INDEX IF NOT EXISTS idx_speakers_embedding ON speakers USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);  -- HNSW/IVFFlat index for fast approximate nearest neighbor search

-- ------------------------------------------------------------
-- 2. recordings: 录音会话
--    Stores recording session metadata
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS recordings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    audio_url TEXT NOT NULL,
    duration_sec FLOAT,
    is_meeting_mode BOOLEAN DEFAULT FALSE,
    location_lat FLOAT,
    location_lng FLOAT,
    location_name TEXT,
    summary TEXT,
    topics TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

-- Recording indexes
CREATE INDEX IF NOT EXISTS idx_recordings_user_id ON recordings(user_id);
CREATE INDEX IF NOT EXISTS idx_recordings_created_at ON recordings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recordings_user_created ON recordings(user_id, created_at DESC);

-- ------------------------------------------------------------
-- 3. utterances: 语音片段
--    Stores transcribed text with semantic embeddings (768-dim BGE)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS utterances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recording_id UUID REFERENCES recordings(id) ON DELETE CASCADE,
    speaker_id UUID REFERENCES speakers(id) ON DELETE SET NULL,
    start_sec FLOAT,
    end_sec FLOAT,
    text TEXT NOT NULL,
    embedding VECTOR(768),
    emotion TEXT,
    is_master BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Utterance indexes
CREATE INDEX IF NOT EXISTS idx_utterances_recording_id ON utterances(recording_id);
CREATE INDEX IF NOT EXISTS idx_utterances_speaker_id ON utterances(speaker_id);
CREATE INDEX IF NOT EXISTS idx_utterances_created_at ON utterances(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_utterances_embedding ON utterances USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);  -- IVFFlat index for 768-dim BGE embeddings

-- ------------------------------------------------------------
-- 4. events: 提取事件
--    Events extracted from conversation analysis
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title TEXT NOT NULL,
    event_date TIMESTAMP,
    related_speaker_ids UUID[],
    source_utterance_ids UUID[],
    event_type TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'cancelled')),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Event indexes
CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_user_date ON events(user_id, event_date DESC);

-- ------------------------------------------------------------
-- 5. todos: 待办事项
--    Action items extracted from conversations
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS todos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title TEXT NOT NULL,
    due_date TIMESTAMP,
    source TEXT,
    related_speaker_id UUID REFERENCES speakers(id) ON DELETE SET NULL,
    webhook_url TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'cancelled')),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Todo indexes
CREATE INDEX IF NOT EXISTS idx_todos_user_id ON todos(user_id);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(user_id, status);
CREATE INDEX IF NOT EXISTS idx_todos_due_date ON todos(due_date);

-- ------------------------------------------------------------
-- 6. flash_memos: 闪念胶囊
--    Quick voice/text memos captured by the user
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flash_memos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    text TEXT NOT NULL,
    audio_url TEXT,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

-- Flash memo indexes
CREATE INDEX IF NOT EXISTS idx_flash_memos_user_id ON flash_memos(user_id);
CREATE INDEX IF NOT EXISTS idx_flash_memos_created_at ON flash_memos(created_at DESC);

-- ------------------------------------------------------------
-- 7. bill_notes: 账单速记
--    Quick expense/bill notes from conversations
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bill_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    amount FLOAT,
    currency TEXT DEFAULT 'CNY',
    category TEXT,
    related_speaker_id UUID REFERENCES speakers(id) ON DELETE SET NULL,
    context TEXT,
    bill_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Bill note indexes
CREATE INDEX IF NOT EXISTS idx_bill_notes_user_id ON bill_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_bill_notes_bill_date ON bill_notes(bill_date);
CREATE INDEX IF NOT EXISTS idx_bill_notes_category ON bill_notes(user_id, category);

-- ------------------------------------------------------------
-- 8. chat_sessions: 聊天会话
--    AI chat conversation sessions
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title TEXT,
    context_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Chat session indexes
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions(created_at DESC);

-- ------------------------------------------------------------
-- 9. chat_messages: 聊天消息
--    Individual messages within a chat session
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Chat message indexes
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);

-- ------------------------------------------------------------
-- 10. weekly_reports: 周报
--     Weekly summary reports generated from conversation data
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weekly_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    data_json JSONB NOT NULL,
    tts_audio_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Weekly report indexes
CREATE INDEX IF NOT EXISTS idx_weekly_reports_user_id ON weekly_reports(user_id);
CREATE INDEX IF NOT EXISTS idx_weekly_reports_week_start ON weekly_reports(week_start DESC);
CREATE INDEX IF NOT EXISTS idx_weekly_reports_user_week ON weekly_reports(user_id, week_start DESC);

-- Print summary
DO $$
BEGIN
    RAISE NOTICE 'All AILife tables created successfully.';
END $$;
