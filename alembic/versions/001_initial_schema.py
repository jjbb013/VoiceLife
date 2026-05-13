"""AILife 初始数据库 Schema

创建所有核心表：
    - speakers: 说话人档案（含 vector(192) 声纹向量）
    - recordings: 录音会话
    - utterances: 语音片段（含 vector(768) 语义向量）
    - events: 提取事件
    - todos: 待办事项
    - flash_memos: 闪念胶囊
    - bill_notes: 账单速记
    - chat_sessions: 聊天会话
    - chat_messages: 聊天消息
    - weekly_reports: 周报

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ================================================================
    # 1. 启用 pgvector 扩展
    # ================================================================
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ================================================================
    # 2. speakers: 说话人档案（含 VECTOR(192) 声纹向量）
    #    使用原生 SQL 创建以保留 pgvector 类型
    # ================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS speakers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            name TEXT,
            relation TEXT,
            is_master BOOLEAN DEFAULT FALSE,
            embedding VECTOR(192),
            voice_sample_count INT DEFAULT 0,
            first_met_at TIMESTAMP WITH TIME ZONE,
            last_talk_at TIMESTAMP WITH TIME ZONE,
            summary TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Speaker indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_speakers_user_id ON speakers(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_speakers_is_master ON speakers(user_id, is_master)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_speakers_embedding ON speakers
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
    """)

    # ================================================================
    # 3. recordings: 录音会话
    # ================================================================
    op.execute("""
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
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Recording indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_recordings_user_id ON recordings(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_recordings_created_at ON recordings(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_recordings_user_created ON recordings(user_id, created_at DESC)")

    # ================================================================
    # 4. utterances: 语音片段（含 VECTOR(768) 语义向量）
    # ================================================================
    op.execute("""
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
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Utterance indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_utterances_recording_id ON utterances(recording_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_utterances_speaker_id ON utterances(speaker_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_utterances_created_at ON utterances(created_at DESC)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_utterances_embedding ON utterances
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
    """)

    # ================================================================
    # 5. events: 提取事件
    # ================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            title TEXT NOT NULL,
            event_date TIMESTAMP WITH TIME ZONE,
            related_speaker_ids UUID[],
            source_utterance_ids UUID[],
            event_type TEXT,
            status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'cancelled')),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Event indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_user_date ON events(user_id, event_date DESC)")

    # ================================================================
    # 6. todos: 待办事项
    # ================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            title TEXT NOT NULL,
            due_date TIMESTAMP WITH TIME ZONE,
            source TEXT,
            related_speaker_id UUID REFERENCES speakers(id) ON DELETE SET NULL,
            webhook_url TEXT,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'cancelled')),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Todo indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_todos_user_id ON todos(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(user_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_todos_due_date ON todos(due_date)")

    # ================================================================
    # 7. flash_memos: 闪念胶囊
    # ================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS flash_memos (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            text TEXT NOT NULL,
            audio_url TEXT,
            tags TEXT[],
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Flash memo indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_flash_memos_user_id ON flash_memos(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_flash_memos_created_at ON flash_memos(created_at DESC)")

    # ================================================================
    # 8. bill_notes: 账单速记
    # ================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS bill_notes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            amount FLOAT,
            currency TEXT DEFAULT 'CNY',
            category TEXT,
            related_speaker_id UUID REFERENCES speakers(id) ON DELETE SET NULL,
            context TEXT,
            bill_date DATE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Bill note indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_bill_notes_user_id ON bill_notes(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_bill_notes_bill_date ON bill_notes(bill_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_bill_notes_category ON bill_notes(user_id, category)")

    # ================================================================
    # 8b. bills: 账单（兼容路由代码，与 bill_notes 冗余）
    # ================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            amount FLOAT,
            currency TEXT DEFAULT 'CNY',
            category TEXT,
            context TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_bills_user_id ON bills(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_bills_created_at ON bills(created_at DESC)")

    # ================================================================
    # 8c. meetings: 会议（兼容路由代码）
    # ================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            recording_id UUID REFERENCES recordings(id) ON DELETE CASCADE,
            title TEXT,
            summary TEXT,
            action_items JSONB DEFAULT '[]'::jsonb,
            participants TEXT[],
            status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_meetings_user_id ON meetings(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meetings_recording_id ON meetings(recording_id)")

    # ================================================================
    # 9. chat_sessions: 聊天会话
    # ================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            title TEXT,
            context_summary TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Chat session indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions(created_at DESC)")

    # ================================================================
    # 10. chat_messages: 聊天消息
    # ================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Chat message indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at)")

    # ================================================================
    # 11. weekly_reports: 周报
    # ================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS weekly_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            week_start DATE NOT NULL,
            week_end DATE NOT NULL,
            data_json JSONB NOT NULL,
            tts_audio_url TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Weekly report indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_weekly_reports_user_id ON weekly_reports(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_weekly_reports_week_start ON weekly_reports(week_start DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_weekly_reports_user_week ON weekly_reports(user_id, week_start DESC)")

    # ================================================================
    # 12. 创建向量搜索函数
    # ================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION match_speakers(
            query_embedding vector(192),
            match_threshold float,
            match_count int,
            p_user_id uuid
        ) RETURNS TABLE(id uuid, name text, similarity float) AS $$
        BEGIN
            RETURN QUERY
            SELECT s.id, s.name, (1 - (s.embedding <=> query_embedding))::float as similarity
            FROM speakers s
            WHERE s.user_id = p_user_id AND s.embedding IS NOT NULL
              AND 1 - (s.embedding <=> query_embedding) > match_threshold
            ORDER BY s.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION match_utterances(
            query_embedding vector(768),
            match_threshold float,
            match_count int,
            p_user_id uuid
        ) RETURNS TABLE(id uuid, text text, speaker_name text, created_at timestamp with time zone, similarity float) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                u.id,
                u.text,
                s.name as speaker_name,
                u.created_at,
                (1 - (u.embedding <=> query_embedding))::float as similarity
            FROM utterances u
            JOIN recordings r ON u.recording_id = r.id
            LEFT JOIN speakers s ON u.speaker_id = s.id
            WHERE r.user_id = p_user_id
              AND u.embedding IS NOT NULL
              AND 1 - (u.embedding <=> query_embedding) > match_threshold
            ORDER BY u.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION get_user_weekly_stats(
            p_user_id uuid,
            p_week_start date,
            p_week_end date
        ) RETURNS jsonb AS $$
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
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION get_speaker_timeline(
            p_speaker_id uuid,
            p_limit int DEFAULT 50
        ) RETURNS TABLE(
            utterance_id uuid,
            text text,
            recording_id uuid,
            start_sec float,
            end_sec float,
            emotion text,
            created_at timestamp with time zone
        ) AS $$
        BEGIN
            RETURN QUERY
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
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION search_speaker_utterances(
            query_embedding vector(768),
            match_threshold float,
            match_count int,
            p_speaker_id uuid
        ) RETURNS TABLE(
            id uuid,
            text text,
            similarity float,
            created_at timestamp with time zone
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                u.id,
                u.text,
                (1 - (u.embedding <=> query_embedding))::float as similarity,
                u.created_at
            FROM utterances u
            WHERE u.speaker_id = p_speaker_id
              AND u.embedding IS NOT NULL
              AND 1 - (u.embedding <=> query_embedding) > match_threshold
            ORDER BY u.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION get_recent_events(
            p_user_id uuid,
            p_days int DEFAULT 7
        ) RETURNS TABLE(
            event_id uuid,
            title text,
            event_date timestamp with time zone,
            event_type text,
            status text,
            related_speaker_ids uuid[]
        ) AS $$
        BEGIN
            RETURN QUERY
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
              AND e.event_date BETWEEN NOW() - interval '1 day' * p_days
                                   AND NOW() + interval '1 day' * p_days
            ORDER BY e.event_date;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade():
    """回滚：删除所有创建的表和函数。"""
    # 删除函数（按依赖顺序）
    op.execute("DROP FUNCTION IF EXISTS get_recent_events(uuid, int)")
    op.execute("DROP FUNCTION IF EXISTS search_speaker_utterances(vector, float, int, uuid)")
    op.execute("DROP FUNCTION IF EXISTS get_speaker_timeline(uuid, int)")
    op.execute("DROP FUNCTION IF EXISTS get_user_weekly_stats(uuid, date, date)")
    op.execute("DROP FUNCTION IF EXISTS match_utterances(vector, float, int, uuid)")
    op.execute("DROP FUNCTION IF EXISTS match_speakers(vector, float, int, uuid)")

    # 删除表（按依赖顺序，先删有外键的）
    op.execute("DROP TABLE IF EXISTS chat_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS chat_sessions CASCADE")
    op.execute("DROP TABLE IF EXISTS weekly_reports CASCADE")
    op.execute("DROP TABLE IF EXISTS meetings CASCADE")
    op.execute("DROP TABLE IF EXISTS bill_notes CASCADE")
    op.execute("DROP TABLE IF EXISTS bills CASCADE")
    op.execute("DROP TABLE IF EXISTS flash_memos CASCADE")
    op.execute("DROP TABLE IF EXISTS todos CASCADE")
    op.execute("DROP TABLE IF EXISTS events CASCADE")
    op.execute("DROP TABLE IF EXISTS utterances CASCADE")
    op.execute("DROP TABLE IF EXISTS recordings CASCADE")
    op.execute("DROP TABLE IF EXISTS speakers CASCADE")
