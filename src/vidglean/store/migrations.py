"""数据库结构迁移。"""

from __future__ import annotations

MIGRATIONS: list[str] = [
    # v1
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        platform TEXT NOT NULL,
        video_id TEXT NOT NULL,
        title TEXT NOT NULL,
        author TEXT NOT NULL DEFAULT '',
        cover_url TEXT NOT NULL DEFAULT '',
        duration INTEGER NOT NULL DEFAULT 0,
        source_url TEXT NOT NULL DEFAULT '',
        content_type TEXT NOT NULL DEFAULT '其他',
        summary_depth TEXT NOT NULL DEFAULT 'standard',
        template_id TEXT NOT NULL DEFAULT '',
        starred INTEGER NOT NULL DEFAULT 0,
        file_path TEXT NOT NULL,
        file_mtime REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'ready',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (platform, video_id)
    );
    CREATE INDEX IF NOT EXISTS idx_documents_created ON documents (created_at DESC);

    CREATE TABLE IF NOT EXISTS categories (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS document_categories (
        document_id TEXT NOT NULL,
        category_id TEXT NOT NULL,
        PRIMARY KEY (document_id, category_id)
    );

    CREATE TABLE IF NOT EXISTS tags (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS document_tags (
        document_id TEXT NOT NULL,
        tag_id TEXT NOT NULL,
        PRIMARY KEY (document_id, tag_id)
    );

    CREATE TABLE IF NOT EXISTS notes (
        document_id TEXT PRIMARY KEY,
        content TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_messages_doc ON messages (document_id, created_at);

    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        document_id TEXT,
        source_url TEXT NOT NULL,
        platform TEXT NOT NULL DEFAULT 'bilibili',
        video_id TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL,
        current_stage TEXT NOT NULL DEFAULT '',
        retry_count INTEGER NOT NULL DEFAULT 0,
        next_retry_at TEXT,
        error_code TEXT NOT NULL DEFAULT '',
        error_message TEXT NOT NULL DEFAULT '',
        options TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status, created_at);

    CREATE TABLE IF NOT EXISTS task_stages (
        task_id TEXT NOT NULL,
        stage TEXT NOT NULL,
        status TEXT NOT NULL,
        error_code TEXT,
        error_message TEXT,
        started_at TEXT,
        finished_at TEXT,
        PRIMARY KEY (task_id, stage)
    );

    CREATE TABLE IF NOT EXISTS models (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        base_url TEXT NOT NULL,
        model TEXT NOT NULL,
        temperature REAL NOT NULL DEFAULT 0.5,
        max_tokens INTEGER NOT NULL DEFAULT 4096,
        timeout INTEGER NOT NULL DEFAULT 120,
        is_current INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS templates (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL DEFAULT 'custom',
        description TEXT NOT NULL DEFAULT '',
        path TEXT NOT NULL DEFAULT '',
        is_default INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS usage_log (
        id TEXT PRIMARY KEY,
        document_id TEXT,
        task_id TEXT,
        kind TEXT NOT NULL,
        model_id TEXT,
        prompt_tokens INTEGER NOT NULL DEFAULT 0,
        completion_tokens INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        estimated_cost REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_log (created_at DESC);

    CREATE TABLE IF NOT EXISTS doc_versions (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        content TEXT NOT NULL,
        reason TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_versions_doc ON doc_versions (document_id, created_at DESC);

    CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
        doc_id UNINDEXED,
        title,
        body,
        tags,
        tokenize = 'unicode61'
    );
    """,
]
