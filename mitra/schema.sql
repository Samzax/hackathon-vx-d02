-- Modelo de dados da Mitra.
-- Genérico de propósito: "ativo" pode ser barragem, obra, equipamento ou licença.
-- Obrigações nunca são sobrescritas: cada mudança cria uma versão nova,
-- ligada ao ato que a causou, e só vale depois de aprovada por uma pessoa.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS empresa (
    id        INTEGER PRIMARY KEY,
    nome      TEXT NOT NULL UNIQUE,
    ficticia  INTEGER NOT NULL DEFAULT 1 CHECK (ficticia IN (0, 1)),
    setor     TEXT NOT NULL DEFAULT 'mineracao'
);

CREATE TABLE IF NOT EXISTS ativo (
    id           INTEGER PRIMARY KEY,
    empresa_id   INTEGER NOT NULL REFERENCES empresa(id),
    tipo         TEXT NOT NULL,                 -- barragem, obra, equipamento...
    codigo       TEXT NOT NULL,                 -- B1, B2...
    nome         TEXT NOT NULL,
    atributos    TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(atributos)),
    responsavel  TEXT,
    unidade      TEXT,                          -- a operação a que pertence ("Mina Serra Azul"): unidade.nome
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

-- Resumo da análise de cada ato (candidatas, motivo, custo e mudanças propostas): é o que o cartão de
-- Mudanças mostra. Fica no banco, e não num arquivo do container, para um deploy novo não apagar.
CREATE TABLE IF NOT EXISTS analise_ato (
    id        INTEGER PRIMARY KEY,
    ato       TEXT NOT NULL UNIQUE,             -- identificação do ato (a mesma de ato.titulo)
    registro  TEXT NOT NULL,                    -- JSON de impacto.resumo
    em        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- O código é único por empresa (índice obrigacao_empresa_codigo, abaixo), não global: duas clientes
-- têm cada uma a sua "LO-01", e as normas públicas (empresa vazia) continuam únicas entre si.
CREATE TABLE IF NOT EXISTS obrigacao (
    id          INTEGER PRIMARY KEY,
    codigo      TEXT NOT NULL,                  -- OB-01, R95-03...
    tipo_ativo  TEXT NOT NULL,
    norma       TEXT,                           -- Res. ANM 220/2025, NR-13...
    area        TEXT,                           -- barragem, emergencia, ambiental, equipamento...
    empresa     TEXT                            -- vazio: norma pública (vale para todas); senão, só desta empresa
                                                -- (condicionante de licença, TAC, procedimento interno)
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
    correcao        TEXT,                       -- JSON {campo: [proposto, aprovado]} quando quem aprovou corrigiu a proposta
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

-- Dia a dia: quem responde por uma obrigação de um ativo (sobrepõe o responsável do ativo).
CREATE TABLE IF NOT EXISTS responsavel_obrigacao (
    ativo_id      INTEGER NOT NULL REFERENCES ativo(id),
    obrigacao_id  INTEGER NOT NULL REFERENCES obrigacao(id),
    responsavel   TEXT NOT NULL,
    PRIMARY KEY (ativo_id, obrigacao_id)
);

-- Histórico de uma obrigação num ativo: entrega, troca de responsável, comentário, dado preenchido.
CREATE TABLE IF NOT EXISTS evento (
    id            INTEGER PRIMARY KEY,
    ativo_id      INTEGER NOT NULL REFERENCES ativo(id),
    obrigacao_id  INTEGER REFERENCES obrigacao(id),   -- vazio: evento do ativo (cadastro)
    tipo          TEXT NOT NULL,                      -- entrega, responsavel, comentario, cadastro
    texto         TEXT NOT NULL,
    por           TEXT,
    em            TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Quem entra na torre. A área é o mesmo texto do responsável do cadastro: é ela que diz
-- o que um gestor vê. Fica fora do "Recriar demo": conta criada pela TI não some com os dados.
CREATE TABLE IF NOT EXISTS usuario (
    id             INTEGER PRIMARY KEY,
    email          TEXT NOT NULL UNIQUE,              -- sempre minúsculo
    nome           TEXT NOT NULL,
    papel          TEXT NOT NULL CHECK (papel IN ('admin', 'diretoria', 'regulatorio', 'gestor')),
    area           TEXT,                              -- obrigatória para gestor
    senha          TEXT,                              -- scrypt$sal$hash; vazio: conta de teste da demo
    teste          INTEGER NOT NULL DEFAULT 0 CHECK (teste IN (0, 1)),   -- troca de visão à vontade
    ativa          INTEGER NOT NULL DEFAULT 1 CHECK (ativa IN (0, 1)),
    criado_por     TEXT,
    criado_em      TEXT NOT NULL DEFAULT (datetime('now')),
    ultimo_acesso  TEXT,
    empresa        TEXT,                              -- nome da empresa cliente: só vê o que é dela
    plataforma     INTEGER NOT NULL DEFAULT 0 CHECK (plataforma IN (0, 1)),  -- equipe da Mitra (curadoria)
    trocar_senha   INTEGER NOT NULL DEFAULT 0 CHECK (trocar_senha IN (0, 1)),  -- senha provisória: troca no 1º acesso
    unidades       TEXT NOT NULL DEFAULT '[]'         -- escopo por unidade (JSON); '[]' = todas as da empresa
);

-- Trilha de auditoria da API: toda escrita, com quem, quando, de onde e o resultado.
CREATE TABLE IF NOT EXISTS auditoria (
    id          INTEGER PRIMARY KEY,
    em          TEXT NOT NULL DEFAULT (datetime('now')),
    usuario     TEXT,
    acao        TEXT NOT NULL,
    alvo        TEXT,
    detalhe     TEXT,
    request_id  TEXT,
    resultado   TEXT NOT NULL,
    empresa     TEXT                -- de qual cliente é a ação (vazio: plataforma)
);
CREATE INDEX IF NOT EXISTS auditoria_em ON auditoria(em);

-- Sessões da API (cookie HttpOnly): só o hash do token fica no banco.
CREATE TABLE IF NOT EXISTS sessao (
    token_hash  TEXT PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id),
    criada_em   TEXT NOT NULL DEFAULT (datetime('now')),
    expira_em   TEXT NOT NULL,
    visao       TEXT
);

-- Descoberta de normas (descoberta.py): normas já publicadas que podem valer para os ativos da carteira.
-- É trabalho da plataforma (curadoria Mitra), não de uma cliente: fica fora do "Recriar demo".
CREATE TABLE IF NOT EXISTS norma_candidata (
    id            INTEGER PRIMARY KEY,
    chave         TEXT NOT NULL UNIQUE,         -- BR:LEI:12334/2010, MG:DEC:48078/2020, BR:RES-ANM:95/2022
    jurisdicao    TEXT NOT NULL,                -- BR ou a UF
    fonte         TEXT NOT NULL,                -- senado, anm, almg
    tipo          TEXT NOT NULL,
    numero        TEXT NOT NULL,
    ano           INTEGER NOT NULL,
    titulo        TEXT NOT NULL,
    ementa        TEXT,
    indexacao     TEXT,
    data          TEXT,                         -- AAAA-MM-DD
    url           TEXT,
    situacao      TEXT,                         -- como a fonte diz (VIGENTE...); vazio: a fonte não diz
    temas         TEXT NOT NULL DEFAULT '[]',   -- tipos de ativo cujos termos a norma cita (JSON)
    triagem       TEXT,                         -- o que a IA respondeu (JSON); vazio: ainda não triada
    status        TEXT NOT NULL DEFAULT 'nova'
                  CHECK (status IN ('nova', 'relevante', 'irrelevante', 'catalogada', 'aprovada', 'descartada')),
    decidida_por  TEXT,
    decidida_em   TEXT,
    nota          TEXT,
    vista_em      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Até onde cada fonte foi lida: a cobertura só diz "verificada" do que foi lido de fato.
CREATE TABLE IF NOT EXISTS descoberta_busca (
    fonte       TEXT PRIMARY KEY,
    jurisdicao  TEXT NOT NULL,
    desde       INTEGER NOT NULL,
    ate         INTEGER NOT NULL,
    lidas       INTEGER NOT NULL,
    candidatas  INTEGER NOT NULL,
    em          TEXT NOT NULL
);

-- Vigência e alterações das normas federais, lidas da ficha da Câmara (mitra/vigencia.py).
CREATE TABLE IF NOT EXISTS norma_vigencia (
    chave         TEXT PRIMARY KEY,
    titulo        TEXT NOT NULL,
    ementa        TEXT,
    situacao      TEXT,
    revogada      INTEGER NOT NULL DEFAULT 0,
    relacoes      TEXT NOT NULL DEFAULT '[]',
    ficha_url     TEXT,
    texto_url     TEXT,
    original_url  TEXT,
    fonte         TEXT NOT NULL,
    lida_em       TEXT NOT NULL
);

-- Instanciação (mitra/instanciacao.py): levar uma cliente nova do zero até a torre funcionando.
-- Uma por empresa. O estado de cada etapa sai dos dados; quem fez o quê e quando fica em instanciacao_evento.
CREATE TABLE IF NOT EXISTS instanciacao (
    empresa_id    INTEGER PRIMARY KEY REFERENCES empresa(id),
    cnpj          TEXT UNIQUE,                  -- 14 dígitos; vazio: empreendedor pessoa física
    razao_social  TEXT NOT NULL,
    ufs           TEXT NOT NULL DEFAULT '[]',   -- UFs em que opera (JSON)
    no_sigbm      INTEGER NOT NULL DEFAULT 0,   -- o CNPJ tem barragem no SIGBM público
    criada_por    TEXT NOT NULL,
    criada_em     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS instanciacao_evento (
    id          INTEGER PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    etapa       TEXT NOT NULL,                  -- cadastro, ativos, dados, cobertura, licencas, responsaveis, contas, operacao
    acao        TEXT NOT NULL,
    detalhe     TEXT,                           -- JSON
    por         TEXT NOT NULL,
    em          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS instanciacao_evento_empresa ON instanciacao_evento(empresa_id, etapa);

-- A operação da empresa ("Mina Serra Azul", com as barragens e os equipamentos dela). O ativo aponta pelo nome.
CREATE TABLE IF NOT EXISTS unidade (
    id          INTEGER PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    nome        TEXT NOT NULL,
    uf          TEXT,
    municipio   TEXT,
    criada_por  TEXT,
    criada_em   TEXT NOT NULL,
    UNIQUE (empresa_id, nome)
);

-- A licença (LP, LI, LO, LAC, outorga, autorização) que a empresa enviou em PDF; o texto lido fica
-- aqui para o Python conferir o trecho literal de cada condicionante.
CREATE TABLE IF NOT EXISTS licenca (
    id            INTEGER PRIMARY KEY,
    empresa_id    INTEGER NOT NULL REFERENCES empresa(id),
    tipo          TEXT NOT NULL,                 -- LP, LI, LO, LAC, outorga, autorizacao
    numero        TEXT NOT NULL,
    orgao         TEXT,
    emitida_em    TEXT,
    validade      TEXT,                          -- AAAA-MM-DD: vira obrigação de renovação
    renovar_dias  INTEGER NOT NULL DEFAULT 120,  -- quantos dias antes do vencimento pedir a renovação
    unidade       TEXT,                          -- a que unidade se aplica (vazio: a empresa)
    ativo_codigo  TEXT,                          -- ou a um ativo
    arquivo       TEXT,                          -- o nome que as pessoas veem
    guardado_em   TEXT,                          -- onde o original ficou (pasta ou S3)
    sha256        TEXT,
    texto         TEXT,                          -- o texto lido do PDF (conferência do trecho)
    enviada_por   TEXT NOT NULL,
    enviada_em    TEXT NOT NULL,
    UNIQUE (empresa_id, tipo, numero)
);

-- Condicionante proposta pela IA com o trecho literal conferido pelo Python; quem aprova é o
-- Regulatório (ou a Diretoria) da própria empresa, e aprovada vira obrigação própria.
CREATE TABLE IF NOT EXISTS condicionante (
    id             INTEGER PRIMARY KEY,
    licenca_id     INTEGER NOT NULL REFERENCES licenca(id),
    empresa_id     INTEGER NOT NULL REFERENCES empresa(id),
    titulo         TEXT NOT NULL,
    prazo          TEXT,
    periodicidade  TEXT,
    agenda         TEXT,                         -- a agenda que a torre usa (ver mitra/agenda.py)
    evidencia      TEXT,
    aplica_a       TEXT,                         -- unidade | ativo | empresa
    alvo           TEXT,                         -- o nome da unidade ou o código do ativo
    trecho         TEXT NOT NULL,                -- literal, conferido no texto do PDF
    pagina         INTEGER,
    status         TEXT NOT NULL DEFAULT 'pendente',   -- pendente | aprovada | rejeitada
    codigo         TEXT,                         -- a obrigação criada na aprovação
    proposta_em    TEXT NOT NULL,
    decidida_por   TEXT,
    decidida_em    TEXT,
    nota           TEXT
);
CREATE INDEX IF NOT EXISTS condicionante_empresa ON condicionante(empresa_id, status);

-- Checklist da etapa 5: os alvarás e as exigências municipais da sede e de cada unidade. Não há fonte
-- automática de legislação municipal: quem confirma é a própria empresa, na implantação. local vazio é
-- a sede; os demais são unidade.nome. Sem linha aqui, o local está pendente.
CREATE TABLE IF NOT EXISTS exigencia_municipal (
    id          INTEGER PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresa(id),
    local       TEXT NOT NULL DEFAULT '',        -- '' = sede; senão o nome da unidade
    situacao    TEXT NOT NULL CHECK (situacao IN ('confirmado', 'nao_se_aplica')),
    nota        TEXT,                            -- obrigatória em "não se aplica" e na confirmação sem alvará
    por         TEXT NOT NULL,
    em          TEXT NOT NULL,
    UNIQUE (empresa_id, local)
);

-- Responsável técnico e coordenador do PAEBM. O CPF é dado pessoal: cifrado por campo
-- (mitra/pessoal.py), mascarado pela API, e ver o CPF inteiro vai para a auditoria.
CREATE TABLE IF NOT EXISTS responsavel_tecnico (
    id                INTEGER PRIMARY KEY,
    empresa_id        INTEGER NOT NULL REFERENCES empresa(id),
    papel             TEXT NOT NULL,             -- responsavel_tecnico | coordenador_paebm | ...
    nome              TEXT NOT NULL,
    cpf_cifrado       TEXT,                      -- Fernet; nunca o CPF em claro
    cpf_fim           TEXT,                      -- os dígitos do meio, para a máscara
    registro          TEXT,                      -- conselho (CREA MG-123456)
    art_numero        TEXT,
    art_vigencia_ate  TEXT,                      -- ART vencendo vira obrigação
    unidade           TEXT,
    ativo_codigo      TEXT,
    consentimento     TEXT,                      -- JSON: quem, quando, para quê (empreendedor PF)
    ficticio          INTEGER NOT NULL DEFAULT 0,-- na demo, só CPF fictício e marcado como tal
    criado_por        TEXT NOT NULL,
    criado_em         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS responsavel_tecnico_empresa ON responsavel_tecnico(empresa_id);

-- A empresa pode adiantar o prazo de uma obrigação sem mudar a norma: a torre mostra os dois.
CREATE TABLE IF NOT EXISTS prazo_interno (
    empresa_id    INTEGER NOT NULL REFERENCES empresa(id),
    codigo        TEXT NOT NULL,
    dias_antes    INTEGER NOT NULL,
    definido_por  TEXT NOT NULL,
    definido_em   TEXT NOT NULL,
    PRIMARY KEY (empresa_id, codigo)
);

-- Responsável padrão por área: obrigação nova da empresa já nasce com responsável.
CREATE TABLE IF NOT EXISTS responsavel_padrao (
    empresa_id    INTEGER NOT NULL REFERENCES empresa(id),
    area          TEXT NOT NULL,
    responsavel   TEXT NOT NULL,
    definido_por  TEXT NOT NULL,
    definido_em   TEXT NOT NULL,
    PRIMARY KEY (empresa_id, area)
);

-- O código da obrigação é único por empresa: COALESCE porque em SQL NULL não é igual a NULL.
CREATE UNIQUE INDEX IF NOT EXISTS obrigacao_empresa_codigo ON obrigacao (COALESCE(empresa, ''), codigo);
