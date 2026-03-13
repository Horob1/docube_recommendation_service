-- ============================================================
-- Docube Recommendation Service — Database Schema
-- PostgreSQL + pgvector
-- ============================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ──────────────────────────────────────────────────────────────
-- 1. users_profile
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users_profile (
    user_id       TEXT PRIMARY KEY,
    role          TEXT,                      -- STUDENT | TEACHER | ADMIN
    faculty       TEXT,                      -- e.g. "Khoa Công nghệ thông tin"
    interests     TEXT[],                    -- mảng tag quan tâm
    embedding     VECTOR(384),
    ab_group      TEXT DEFAULT 'A',
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────────
-- 2. documents
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    document_id       TEXT PRIMARY KEY,
    title             TEXT,
    description       TEXT,
    content           TEXT,
    tags              TEXT[],
    categories        TEXT[],
    language          TEXT,
    faculty           TEXT,                  -- e.g. "Khoa Công nghệ thông tin"
    author_id         TEXT,
    author_role       TEXT,                  -- STUDENT | TEACHER
    embedding         VECTOR(384),
    popularity_score  FLOAT DEFAULT 0,
    updated_at        TIMESTAMP DEFAULT NOW()
);

-- GIN index on tags for fast array lookups
CREATE INDEX IF NOT EXISTS idx_documents_tags
    ON documents USING GIN(tags);

-- ──────────────────────────────────────────────────────────────
-- 3. ANN Index (IVFFLAT) on document embeddings
-- ──────────────────────────────────────────────────────────────
-- NOTE: Run ANALYZE documents; after bulk-inserting data
--       before creating this index for optimal clustering.
CREATE INDEX IF NOT EXISTS idx_documents_embedding_ivfflat
    ON documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

ANALYZE documents;

-- ──────────────────────────────────────────────────────────────
-- 4. user_interactions
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_interactions (
    id                UUID PRIMARY KEY,
    user_id           TEXT NOT NULL,
    document_id       TEXT NOT NULL,
    interaction_type  TEXT CHECK (
        interaction_type IN ('view', 'read', 'download', 'buy', 'bookmark')
    ),
    created_at        TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interactions_user_id
    ON user_interactions(user_id);

CREATE INDEX IF NOT EXISTS idx_interactions_document_id
    ON user_interactions(document_id);

-- ──────────────────────────────────────────────────────────────
-- 5. search_history
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS search_history (
    id          UUID PRIMARY KEY,
    user_id     TEXT NOT NULL,
    query       TEXT NOT NULL,
    embedding   VECTOR(384),
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_search_history_user_id
    ON search_history(user_id);

-- ──────────────────────────────────────────────────────────────
-- 6. Migration — add new columns to existing tables
--    (safe to re-run; ADD COLUMN IF NOT EXISTS is idempotent)
-- ──────────────────────────────────────────────────────────────

-- documents: faculty
ALTER TABLE documents ADD COLUMN IF NOT EXISTS faculty TEXT;

-- users_profile: faculty + interests
ALTER TABLE users_profile ADD COLUMN IF NOT EXISTS faculty    TEXT;
ALTER TABLE users_profile ADD COLUMN IF NOT EXISTS interests  TEXT[];

-- user_interactions: add 'read' to CHECK constraint
ALTER TABLE user_interactions DROP CONSTRAINT IF EXISTS user_interactions_interaction_type_check;
ALTER TABLE user_interactions ADD CONSTRAINT user_interactions_interaction_type_check
    CHECK (interaction_type IN ('view', 'read', 'download', 'buy', 'bookmark'));
