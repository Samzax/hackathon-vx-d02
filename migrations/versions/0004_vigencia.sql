-- Vigência e alterações das normas federais, lidas da ficha da Câmara (mitra/vigencia.py).
CREATE TABLE IF NOT EXISTS norma_vigencia (
    chave         TEXT COLLATE "C" PRIMARY KEY,
    titulo        TEXT COLLATE "C" NOT NULL,
    ementa        TEXT,
    situacao      TEXT,
    revogada      INTEGER NOT NULL DEFAULT 0,
    relacoes      TEXT NOT NULL DEFAULT '[]',
    ficha_url     TEXT,
    texto_url     TEXT,
    original_url  TEXT,
    fonte         TEXT COLLATE "C" NOT NULL,
    lida_em       TEXT COLLATE "C" NOT NULL
);
