CREATE TABLE IF NOT EXISTS procurement_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    title TEXT NOT NULL,
    strategy TEXT NOT NULL,
    budget_limit REAL,
    currency TEXT NOT NULL DEFAULT 'TRY',
    tender_reference TEXT,
    tender_requirements TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'open',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS procurement_request_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    specification TEXT NOT NULL DEFAULT '',
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    min_quality_score REAL NOT NULL DEFAULT 0,
    max_unit_price REAL,
    required_by_date TEXT,
    must_comply_tender INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    FOREIGN KEY(request_id) REFERENCES procurement_requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_procurement_items_request_id
    ON procurement_request_items(request_id);

CREATE TABLE IF NOT EXISTS procurement_vendor_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    vendor_name TEXT NOT NULL,
    vendor_rating REAL NOT NULL DEFAULT 60,
    delivery_days INTEGER NOT NULL DEFAULT 7,
    warranty_months INTEGER NOT NULL DEFAULT 0,
    compliance_score REAL NOT NULL DEFAULT 80,
    status TEXT NOT NULL DEFAULT 'submitted',
    created_at INTEGER NOT NULL,
    FOREIGN KEY(request_id) REFERENCES procurement_requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_procurement_quotes_request_id
    ON procurement_vendor_quotes(request_id);

CREATE TABLE IF NOT EXISTS procurement_quote_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL,
    request_item_id INTEGER NOT NULL,
    unit_price REAL NOT NULL CHECK(unit_price > 0),
    available_quantity INTEGER NOT NULL CHECK(available_quantity >= 0),
    quality_score REAL NOT NULL DEFAULT 0,
    brand TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    UNIQUE(quote_id, request_item_id),
    FOREIGN KEY(quote_id) REFERENCES procurement_vendor_quotes(id) ON DELETE CASCADE,
    FOREIGN KEY(request_item_id) REFERENCES procurement_request_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_procurement_quote_items_request_item_id
    ON procurement_quote_items(request_item_id);

CREATE TABLE IF NOT EXISTS procurement_purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    vendor_name TEXT NOT NULL,
    currency TEXT NOT NULL,
    total_amount REAL NOT NULL CHECK(total_amount >= 0),
    status TEXT NOT NULL DEFAULT 'draft',
    created_at INTEGER NOT NULL,
    approved_at INTEGER,
    FOREIGN KEY(request_id) REFERENCES procurement_requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_procurement_po_request_id
    ON procurement_purchase_orders(request_id);

CREATE TABLE IF NOT EXISTS procurement_purchase_order_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_order_id INTEGER NOT NULL,
    request_item_id INTEGER,
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    line_total REAL NOT NULL CHECK(line_total >= 0),
    FOREIGN KEY(purchase_order_id) REFERENCES procurement_purchase_orders(id) ON DELETE CASCADE,
    FOREIGN KEY(request_item_id) REFERENCES procurement_request_items(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_procurement_po_lines_po_id
    ON procurement_purchase_order_lines(purchase_order_id);
