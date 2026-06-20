-- Skema DuckDB Project Bandar.
-- Prinsip: setiap tabel punya kolom waktu yang JUJUR ("kapan data tersedia"),
-- dan PK yang membuat job idempotent (UPSERT, bukan append buta).

-- 1) Harga harian (EOD). available_at = kapan baris ini bisa diketahui publik.
CREATE TABLE IF NOT EXISTS prices (
    symbol       VARCHAR NOT NULL,
    date         DATE    NOT NULL,
    open         DOUBLE,
    high         DOUBLE,
    low          DOUBLE,
    close        DOUBLE,
    adj_close    DOUBLE,
    volume       BIGINT,
    market       VARCHAR,           -- 'US' | 'IDX'
    available_at TIMESTAMP,
    PRIMARY KEY (symbol, date)
);

-- 2) Fundamental (dari SEC EDGAR). period = akhir periode laporan.
CREATE TABLE IF NOT EXISTS fundamentals (
    symbol       VARCHAR NOT NULL,
    period       DATE    NOT NULL,  -- akhir kuartal/tahun fiskal
    metric       VARCHAR NOT NULL,  -- 'revenue','net_income','roe',...
    value        DOUBLE,
    filed_at     TIMESTAMP,         -- kapan laporan dirilis (anti look-ahead)
    PRIMARY KEY (symbol, period, metric)
);

-- 3) Berita mentah. available_at = timestamp publikasi.
CREATE TABLE IF NOT EXISTS news (
    id           VARCHAR NOT NULL,  -- hash url+title (dedup)
    symbol       VARCHAR,           -- saham terkait (boleh NULL = makro)
    title        VARCHAR,
    url          VARCHAR,
    source       VARCHAR,
    available_at TIMESTAMP NOT NULL,
    event_type   VARCHAR,           -- diisi oleh nlp/classify.py
    sentiment    DOUBLE,            -- diisi oleh nlp/sentiment.py
    PRIMARY KEY (id)
);

-- 4) Fitur terhitung (feature store). Cache agar tak hitung ulang.
CREATE TABLE IF NOT EXISTS features (
    symbol  VARCHAR NOT NULL,
    date    DATE    NOT NULL,
    name    VARCHAR NOT NULL,       -- 'rsi_14','sma_50','piotroski',...
    value   DOUBLE,
    PRIMARY KEY (symbol, date, name)
);

-- 5) Skor per engine (Lapisan 5).
CREATE TABLE IF NOT EXISTS engine_scores (
    symbol      VARCHAR NOT NULL,
    as_of       DATE    NOT NULL,
    engine      VARCHAR NOT NULL,
    score       DOUBLE,
    sample_size INTEGER,
    confidence  VARCHAR,
    components  JSON,
    PRIMARY KEY (symbol, as_of, engine)
);

-- 6) Composite score (Lapisan 6).
CREATE TABLE IF NOT EXISTS composite_scores (
    symbol     VARCHAR NOT NULL,
    as_of      DATE    NOT NULL,
    market     VARCHAR,
    total      DOUBLE,
    breakdown  JSON,
    confidence VARCHAR,
    PRIMARY KEY (symbol, as_of)
);

-- 7) Prediksi (untuk Track Record). realized_* diisi setelah horizon lewat.
CREATE TABLE IF NOT EXISTS predictions (
    symbol          VARCHAR NOT NULL,
    as_of           DATE    NOT NULL,
    horizon_days    INTEGER NOT NULL,
    prob_up         DOUBLE,
    ci_low          DOUBLE,
    ci_high         DOUBLE,
    median_return   DOUBLE,
    sample_size     INTEGER,
    rationale       VARCHAR,
    confidence      VARCHAR,
    realized_return DOUBLE,          -- NULL sampai dievaluasi
    was_correct     BOOLEAN,
    PRIMARY KEY (symbol, as_of, horizon_days)
);

-- 8) Vonis backtest per engine: apakah skornya PUNYA EDGE TERUKUR?
--    Sebuah engine hanya diberi bobot di composite bila validated = TRUE.
CREATE TABLE IF NOT EXISTS validation (
    engine       VARCHAR NOT NULL,
    horizon_days INTEGER NOT NULL,
    as_of        DATE,
    n_obs        INTEGER,
    top_mean     DOUBLE,            -- mean fwd return kuantil skor tertinggi (%)
    bottom_mean  DOUBLE,            -- mean fwd return kuantil skor terendah (%)
    spread       DOUBLE,            -- top - bottom (edge); harus > 0 utk valid
    t_stat       DOUBLE,
    validated    BOOLEAN,
    note         VARCHAR,
    PRIMARY KEY (engine, horizon_days)
);
