-- ============================================================
-- AILife Project - Database Migration: Step 04
-- Seed Data for Development & Testing
-- ============================================================
-- PostgreSQL 15 + pgvector

-- Test user UUID: 00000000-0000-0000-0000-000000000001

-- ------------------------------------------------------------
-- Seed 1: Master speaker (the user themselves)
-- ------------------------------------------------------------
INSERT INTO speakers (
    id,
    user_id,
    name,
    relation,
    is_master,
    voice_sample_count,
    summary,
    first_met_at,
    last_talk_at
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    '00000000-0000-0000-0000-000000000001',
    '我',
    '主人',
    TRUE,
    1,
    '这是您的主人声纹，所有对话将以您为锚点进行分析。',
    NOW(),
    NOW()
);

-- ------------------------------------------------------------
-- Seed 2: Sample speakers for testing
-- ------------------------------------------------------------
INSERT INTO speakers (
    id,
    user_id,
    name,
    relation,
    voice_sample_count,
    summary
) VALUES
    ('22222222-2222-2222-2222-222222222222', '00000000-0000-0000-0000-000000000001', '张三', '同事', 3, '公司负责运营商对接的同事'),
    ('33333333-3333-3333-3333-333333333333', '00000000-0000-0000-0000-000000000001', '李四', '家人', 5, '您的配偶，经常讨论家庭开支'),
    ('44444444-4444-4444-4444-444444444444', '00000000-0000-0000-0000-000000000001', NULL, '未知', 1, NULL);

-- ------------------------------------------------------------
-- Seed 3: Sample recordings
-- ------------------------------------------------------------
INSERT INTO recordings (
    id,
    user_id,
    audio_url,
    duration_sec,
    is_meeting_mode,
    location_name,
    summary,
    topics
) VALUES
    (
        '55555555-5555-5555-5555-555555555555',
        '00000000-0000-0000-0000-000000000001',
        'https://storage.example.com/audio/test-recording-001.mp3',
        180.5,
        TRUE,
        '公司会议室A',
        '与张三四就Q3项目排期进行讨论，确定了关键里程碑。',
        ARRAY['项目排期', 'Q3计划']
    ),
    (
        '66666666-6666-6666-6666-666666666666',
        '00000000-0000-0000-0000-000000000001',
        'https://storage.example.com/audio/test-recording-002.mp3',
        120.0,
        FALSE,
        '家中客厅',
        '与李四讨论周末家庭聚餐安排和超市采购清单。',
        ARRAY['家庭', '采购']
    );

-- ------------------------------------------------------------
-- Seed 4: Sample utterances
-- ------------------------------------------------------------
INSERT INTO utterances (
    id,
    recording_id,
    speaker_id,
    start_sec,
    end_sec,
    text,
    emotion,
    is_master
) VALUES
    (
        '77777777-7777-7777-7777-777777777777',
        '55555555-5555-5555-5555-555555555555',
        '11111111-1111-1111-1111-111111111111',
        0.0,
        15.2,
        '张三，我们先对齐一下Q3项目的时间线，你觉得开发排期怎么安排比较合适？',
        'neutral',
        TRUE
    ),
    (
        '88888888-8888-8888-8888-888888888888',
        '55555555-5555-5555-5555-555555555555',
        '22222222-2222-2222-2222-222222222222',
        15.5,
        45.0,
        '我觉得后端开发大概需要三周，前端两周联调一周，总共六周可以搞定。',
        'confident',
        FALSE
    ),
    (
        '99999999-9999-9999-9999-999999999999',
        '66666666-6666-6666-6666-666666666666',
        '33333333-3333-3333-3333-333333333333',
        0.0,
        20.0,
        '亲爱的，周末要不要叫上爸妈一起出来吃个饭？',
        'happy',
        FALSE
    ),
    (
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        '66666666-6666-6666-6666-666666666666',
        '11111111-1111-1111-1111-111111111111',
        20.5,
        40.0,
        '好啊，我来定餐厅，你去超市买点水果和饮料。',
        'happy',
        TRUE
    );

-- ------------------------------------------------------------
-- Seed 5: Sample events
-- ------------------------------------------------------------
INSERT INTO events (
    user_id,
    title,
    event_date,
    related_speaker_ids,
    source_utterance_ids,
    event_type,
    status
) VALUES
    (
        '00000000-0000-0000-0000-000000000001',
        'Q3项目启动会',
        NOW() + interval '3 days',
        ARRAY['22222222-2222-2222-2222-222222222222'::uuid],
        ARRAY['77777777-7777-7777-7777-777777777777'::uuid],
        'meeting',
        'active'
    ),
    (
        '00000000-0000-0000-0000-000000000001',
        '家庭周末聚餐',
        NOW() + interval '5 days',
        ARRAY['33333333-3333-3333-3333-333333333333'::uuid],
        ARRAY['99999999-9999-9999-9999-999999999999'::uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid],
        'social',
        'active'
    );

-- ------------------------------------------------------------
-- Seed 6: Sample todos
-- ------------------------------------------------------------
INSERT INTO todos (
    user_id,
    title,
    due_date,
    source,
    related_speaker_id,
    status
) VALUES
    (
        '00000000-0000-0000-0000-000000000001',
        '确认Q3项目排期文档',
        NOW() + interval '2 days',
        'conversation',
        '22222222-2222-2222-2222-222222222222',
        'pending'
    ),
    (
        '00000000-0000-0000-0000-000000000001',
        '预定周末聚餐餐厅',
        NOW() + interval '4 days',
        'conversation',
        '33333333-3333-3333-3333-333333333333',
        'pending'
    ),
    (
        '00000000-0000-0000-0000-000000000001',
        '超市采购水果和饮料',
        NOW() + interval '5 days',
        'conversation',
        '33333333-3333-3333-3333-333333333333',
        'pending'
    );

-- ------------------------------------------------------------
-- Seed 7: Sample flash memos
-- ------------------------------------------------------------
INSERT INTO flash_memos (user_id, text, tags) VALUES
    ('00000000-0000-0000-0000-000000000001', '记得给张三发项目文档链接', ARRAY['工作', '待发送']),
    ('00000000-0000-0000-0000-000000000001', '下周三下午三点有 dentist 预约', ARRAY['健康', '预约']);

-- ------------------------------------------------------------
-- Seed 8: Sample bill notes
-- ------------------------------------------------------------
INSERT INTO bill_notes (user_id, amount, currency, category, related_speaker_id, context, bill_date) VALUES
    ('00000000-0000-0000-0000-000000000001', 128.50, 'CNY', '餐饮', '33333333-3333-3333-3333-333333333333', '周末超市采购食材', CURRENT_DATE),
    ('00000000-0000-0000-0000-000000000001', 350.00, 'CNY', '交通', NULL, '加油费', CURRENT_DATE - interval '2 days');

-- ------------------------------------------------------------
-- Seed 9: Sample chat session and messages
-- ------------------------------------------------------------
INSERT INTO chat_sessions (id, user_id, title, context_summary) VALUES
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '00000000-0000-0000-0000-000000000001', 'AI助手初次对话', '用户与AI助手的首次对话，了解产品功能');

INSERT INTO chat_messages (session_id, role, content) VALUES
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'user', '你好，请介绍一下你能帮我做什么？'),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'assistant', '你好！我是你的AI生活助手。我可以帮你：1) 记录和分析日常对话 2) 提取待办事项和事件 3) 管理账单和开支 4) 生成周报回顾。请问有什么我可以帮你的吗？');

-- Print summary
DO $$
DECLARE
    table_count int;
BEGIN
    SELECT COUNT(*) INTO table_count FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name IN ('speakers', 'recordings', 'utterances', 'events', 'todos',
                         'flash_memos', 'bill_notes', 'chat_sessions', 'chat_messages', 'weekly_reports');
    RAISE NOTICE 'Seed data inserted. Tables present: %', table_count;
END $$;
