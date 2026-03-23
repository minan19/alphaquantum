CREATE TABLE IF NOT EXISTS user_company_scopes (
    user_id INTEGER NOT NULL,
    company_scope TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, company_scope),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_company_scopes_scope
    ON user_company_scopes(company_scope);
