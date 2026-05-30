-- BZ3: Public changelog + roadmap voting
--
-- 3 tablo:
--   * changelog_entries  — yayınlanmış sürüm notları
--   * roadmap_items      — fikir/planlanan/üretimde özellikler
--   * roadmap_votes      — kullanıcı oyları (toggle UNIQUE)
--
-- "Aidiyet hissi" pillar'ı: kullanıcı kendi yaptığı ürünün parçası
-- olduğunu hisseder. Oy verir → öncelik mantığı şeffaflaşır.

CREATE TABLE IF NOT EXISTS changelog_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,             -- ör. "0.7.0" veya "Mayıs 2026"
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'feature'
        CHECK (category IN ('feature', 'fix', 'improvement', 'security')),
    is_published INTEGER NOT NULL DEFAULT 1,
    released_at INTEGER NOT NULL,      -- unix epoch
    created_at INTEGER NOT NULL,
    created_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_changelog_published_time
    ON changelog_entries(is_published, released_at DESC);

CREATE INDEX IF NOT EXISTS idx_changelog_category
    ON changelog_entries(category, released_at DESC);


CREATE TABLE IF NOT EXISTS roadmap_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'feature'
        CHECK (category IN ('feature', 'integration', 'analytics', 'ux', 'security', 'mobile')),
    status TEXT NOT NULL DEFAULT 'idea'
        CHECK (status IN ('idea', 'planned', 'in_progress', 'shipped', 'declined')),
    upvotes INTEGER NOT NULL DEFAULT 0,  -- denormalized count for fast sort
    submitter TEXT,
    target_quarter TEXT,                 -- "Q3 2026" — admin ekler
    shipped_changelog_id INTEGER REFERENCES changelog_entries(id) ON DELETE SET NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_roadmap_status_votes
    ON roadmap_items(status, upvotes DESC);

CREATE INDEX IF NOT EXISTS idx_roadmap_category
    ON roadmap_items(category, upvotes DESC);


CREATE TABLE IF NOT EXISTS roadmap_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    item_id INTEGER NOT NULL REFERENCES roadmap_items(id) ON DELETE CASCADE,
    voted_at INTEGER NOT NULL,
    UNIQUE (user_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_roadmap_votes_item
    ON roadmap_votes(item_id);

CREATE INDEX IF NOT EXISTS idx_roadmap_votes_user
    ON roadmap_votes(user_id);
