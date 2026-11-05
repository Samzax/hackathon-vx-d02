-- Modelo de dados da RegulaIA.
-- Genérico de propósito: "ativo" pode ser barragem, obra, equipamento ou licença.
-- Obrigações nunca são sobrescritas: cada mudança cria uma versão nova,
-- ligada ao ato que a causou, e só vale depois de aprovada por uma pessoa.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS empresa (
    id        INTEGER PRIMARY KEY,
    nome      TEXT NOT NULL UNIQUE,
    ficticia  INTEGER NOT NULL DEFAULT 1 CHECK (ficticia IN (0, 1))
);

CREATE TABLE IF NOT EXISTS ativo (
    id           INTEGER PRIMARY KEY,
    empresa_id   INTEGER NOT NULL REFERENCES empresa(id),
    tipo         TEXT NOT NULL,                 -- barragem, obra, equipamento...
    codigo       TEXT NOT NULL,                 -- B1, B2...
    nome         TEXT NOT NULL,
    atributos    TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(atributos)),
    responsavel  TEXT,
    UNIQUE (empresa_id, codigo)
);

-- Publicação oficial (DOU, diário estadual, portal da agência).
CREATE TABLE IF NOT EXISTS ato (
    id             INTEGER PRIMARY KEY,
    fonte          TEXT NOT NULL,               -- dou, anmlegis, upload...
    identificador  TEXT NOT NULL UNIQUE,        -- urlTitle do DOU ou equivalente
    titulo         TEXT NOT NULL,
    ementa         TEXT,
    publicado_em   TEXT,                        -- AAAA-MM-DD
    url            TEXT,
    texto          TEXT,
    sha256         TEXT
);

CREATE TABLE IF NOT EXISTS obrigacao (
    id          INTEGER PRIMARY KEY,
    codigo      TEXT NOT NULL UNIQUE,           -- OB-01, R95-03...
    tipo_ativo  TEXT NOT NULL,
    norma       TEXT,                           -- Res. ANM 220/2025, NR-13...
    area        TEXT                            -- barragem, emergencia, ambiental, equipamento...
);

CREATE TABLE IF NOT EXISTS obrigacao_versao (
    id              INTEGER PRIMARY KEY,
    obrigacao_id    INTEGER NOT NULL REFERENCES obrigacao(id),
    versao          INTEGER NOT NULL,
    titulo          TEXT NOT NULL,
    artigo          TEXT NOT NULL,
    aplica_se_a     TEXT NOT NULL,              -- texto para pessoas
    regra           TEXT NOT NULL,              -- texto para a máquina (ver regras.py)
    periodicidade   TEXT,                       -- texto para pessoas
    agenda          TEXT NOT NULL DEFAULT 'evento', -- texto para a máquina (ver agenda.py)
    prazo           TEXT,
    vigencia_desde  TEXT,                       -- AAAA-MM-DD: a partir de quando vale
    vigencia_ate    TEXT,                       -- AAAA-MM-DD: último dia em que vale (vazio = sem fim)
    responsavel     TEXT,
    evidencia       TEXT,
    fonte           TEXT,                       -- de onde veio esta versão
    ato_id          INTEGER REFERENCES ato(id), -- ato que originou a mudança
    trecho          TEXT,                       -- citação literal que sustenta a mudança
    status          TEXT NOT NULL CHECK (status IN ('vigente', 'pendente', 'substituida', 'rejeitada')),
    criada_em       TEXT NOT NULL DEFAULT (datetime('now')),
    decidida_por    TEXT,
    decidida_em     TEXT,
    UNIQUE (obrigacao_id, versao)
);

-- No máximo uma versão vigente e uma pendente por obrigação.
CREATE UNIQUE INDEX IF NOT EXISTS uma_vigente
    ON obrigacao_versao(obrigacao_id) WHERE status = 'vigente';
CREATE UNIQUE INDEX IF NOT EXISTS uma_pendente
    ON obrigacao_versao(obrigacao_id) WHERE status = 'pendente';

-- Documento produzido pela operação que comprova uma obrigação (FIR, laudo...).
CREATE TABLE IF NOT EXISTS evidencia (
    id            INTEGER PRIMARY KEY,
    ativo_id      INTEGER NOT NULL REFERENCES ativo(id),
    obrigacao_id  INTEGER NOT NULL REFERENCES obrigacao(id),
    periodo       TEXT NOT NULL,                -- 2026-08-1Q, 2026-S2, 2026...
    arquivo       TEXT,
    recebida_em   TEXT NOT NULL DEFAULT (datetime('now')),
    extraido      TEXT CHECK (extraido IS NULL OR json_valid(extraido)),
    UNIQUE (ativo_id, obrigacao_id, periodo)
);

-- Obrigação por evento que um documento acionou (ex.: anomalia que obriga ISE).
-- Fica aberta até chegar a evidência da própria obrigação acionada.
CREATE TABLE IF NOT EXISTS acionamento (
    id            INTEGER PRIMARY KEY,
    ativo_id      INTEGER NOT NULL REFERENCES ativo(id),
    obrigacao_id  INTEGER NOT NULL REFERENCES obrigacao(id),
    dia           TEXT NOT NULL,                -- AAAA-MM-DD do fato que acionou
    prazo         TEXT NOT NULL,                -- AAAA-MM-DD
    motivo        TEXT NOT NULL,
    origem        TEXT,                         -- arquivo que acionou
    encerrado_em  TEXT,                         -- AAAA-MM-DD da evidência que encerrou
    UNIQUE (ativo_id, obrigacao_id, dia)
);

-- Toda chamada de IA fica guardada: a mesma entrada nunca é paga duas vezes,
-- e o custo do sistema pode ser medido.
CREATE TABLE IF NOT EXISTS analise_ia (
    chave       TEXT PRIMARY KEY,               -- sha256(tarefa + modelo + prompt + entrada)
    tarefa      TEXT NOT NULL,
    provedor    TEXT NOT NULL,
    modelo      TEXT NOT NULL,
    resposta    TEXT NOT NULL,
    tokens_in   INTEGER,
    tokens_out  INTEGER,
    custo_usd   REAL,
    criada_em   TEXT NOT NULL DEFAULT (datetime('now'))
);
