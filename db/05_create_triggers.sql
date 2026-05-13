-- ============================================================
-- AILife Project - Database Migration: Step 05
-- Triggers and Auto-Update Logic
-- ============================================================
-- PostgreSQL 15 + pgvector

-- ------------------------------------------------------------
-- Trigger 1: Auto-update speakers.last_talk_at on new utterance
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_speaker_last_talk()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE speakers SET last_talk_at = NOW()
  WHERE id = NEW.speaker_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_speaker_last_talk ON utterances;
CREATE TRIGGER trigger_update_speaker_last_talk
  AFTER INSERT ON utterances
  FOR EACH ROW
  WHEN (NEW.speaker_id IS NOT NULL)
  EXECUTE FUNCTION update_speaker_last_talk();

-- ------------------------------------------------------------
-- Trigger 2: Auto-update speakers.first_met_at on first utterance
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_speaker_first_met()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE speakers
  SET first_met_at = COALESCE(first_met_at, NOW())
  WHERE id = NEW.speaker_id
    AND first_met_at IS NULL;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_speaker_first_met ON utterances;
CREATE TRIGGER trigger_update_speaker_first_met
  AFTER INSERT ON utterances
  FOR EACH ROW
  WHEN (NEW.speaker_id IS NOT NULL)
  EXECUTE FUNCTION update_speaker_first_met();

-- ------------------------------------------------------------
-- Trigger 3: Increment voice_sample_count on new utterance
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION increment_voice_sample_count()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE speakers
  SET voice_sample_count = voice_sample_count + 1
  WHERE id = NEW.speaker_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_increment_sample_count ON utterances;
CREATE TRIGGER trigger_increment_sample_count
  AFTER INSERT ON utterances
  FOR EACH ROW
  WHEN (NEW.speaker_id IS NOT NULL)
  EXECUTE FUNCTION increment_voice_sample_count();

-- Print summary
DO $$
BEGIN
    RAISE NOTICE 'All AILife triggers created successfully.';
END $$;
