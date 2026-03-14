-- servers: canonical list of known Minecraft servers
CREATE TABLE IF NOT EXISTS servers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    host            TEXT NOT NULL,
    port            INTEGER NOT NULL DEFAULT 25565,
    country_code    TEXT,
    city            TEXT,
    latitude        REAL,
    longitude       REAL,
    source          TEXT,
    first_seen      INTEGER NOT NULL,
    last_seen       INTEGER,
    is_active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(host, port)
);

CREATE INDEX IF NOT EXISTS idx_servers_country ON servers(country_code);
CREATE INDEX IF NOT EXISTS idx_servers_active ON servers(is_active);

-- scan_results: one row per scan attempt per server
CREATE TABLE IF NOT EXISTS scan_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id       INTEGER NOT NULL REFERENCES servers(id),
    scanned_at      INTEGER NOT NULL,
    is_online       INTEGER NOT NULL,
    latency_ms      REAL,
    players_online  INTEGER,
    players_max     INTEGER,
    version_name    TEXT,
    version_protocol INTEGER,
    motd            TEXT,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_results_server_time
    ON scan_results(server_id, scanned_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_results_time
    ON scan_results(scanned_at DESC);

-- lead_scores: computed scores, refreshed after each scan cycle
CREATE TABLE IF NOT EXISTS lead_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id       INTEGER NOT NULL REFERENCES servers(id) UNIQUE,
    score           REAL NOT NULL DEFAULT 0,
    downtime_pct    REAL NOT NULL DEFAULT 0,
    avg_latency_ms  REAL,
    p95_latency_ms  REAL,
    timeout_count   INTEGER NOT NULL DEFAULT 0,
    avg_players     REAL,
    max_players     INTEGER,
    score_details   TEXT,
    calculated_at   INTEGER NOT NULL,
    window_hours    INTEGER NOT NULL DEFAULT 168
);

CREATE INDEX IF NOT EXISTS idx_lead_scores_score
    ON lead_scores(score DESC);

-- scrape_log: track scraping runs
CREATE TABLE IF NOT EXISTS scrape_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name     TEXT NOT NULL,
    scraped_at      INTEGER NOT NULL,
    servers_found   INTEGER NOT NULL DEFAULT 0,
    servers_new     INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'success',
    error_message   TEXT
);

-- scan_cycles: track each full scan round
CREATE TABLE IF NOT EXISTS scan_cycles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      INTEGER NOT NULL,
    finished_at     INTEGER,
    servers_scanned INTEGER NOT NULL DEFAULT 0,
    servers_online  INTEGER NOT NULL DEFAULT 0,
    avg_latency_ms  REAL,
    status          TEXT NOT NULL DEFAULT 'running'
);
