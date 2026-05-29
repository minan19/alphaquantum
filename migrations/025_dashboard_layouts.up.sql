-- F4: Dashboard widget customization — kullanıcı bazlı layout persist.
--
-- Kullanıcı dashboard'da hangi widget'lar görünür, hangi sırada, hangi
-- boyutta — kayıt edilir. "Bana özel pano" aidiyet hissi için.
--
-- Layout JSON formatı (frontend tarafı sözleşme):
--   [
--     {"widget_id": "balance",     "size": "md", "hidden": false, "order": 0},
--     {"widget_id": "fx_position", "size": "lg", "hidden": false, "order": 1},
--     ...
--   ]

CREATE TABLE IF NOT EXISTS user_dashboard_layouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL UNIQUE,           -- her user'ın bir layout'u (last write wins)
    layout_json TEXT NOT NULL DEFAULT '[]', -- JSON string (frontend doğrular)
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_dashboard_layouts_user_id
    ON user_dashboard_layouts(user_id);
