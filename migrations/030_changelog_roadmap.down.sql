-- BZ3: Changelog + roadmap rollback
DROP INDEX IF EXISTS idx_roadmap_votes_user;
DROP INDEX IF EXISTS idx_roadmap_votes_item;
DROP TABLE IF EXISTS roadmap_votes;
DROP INDEX IF EXISTS idx_roadmap_category;
DROP INDEX IF EXISTS idx_roadmap_status_votes;
DROP TABLE IF EXISTS roadmap_items;
DROP INDEX IF EXISTS idx_changelog_category;
DROP INDEX IF EXISTS idx_changelog_published_time;
DROP TABLE IF EXISTS changelog_entries;
