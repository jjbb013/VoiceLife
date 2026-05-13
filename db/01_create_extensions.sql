-- ============================================================
-- AILife Project - Database Migration: Step 01
-- Enable Extensions
-- ============================================================
-- PostgreSQL 15 + pgvector

-- Enable UUID generation extension (provides uuid-ossp functions)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgvector extension for vector types and similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable moddatetime extension for automatic timestamp management
CREATE EXTENSION IF NOT EXISTS moddatetime;

-- Verify extensions are installed
SELECT * FROM pg_extension WHERE extname IN ('uuid-ossp', 'vector', 'moddatetime');
