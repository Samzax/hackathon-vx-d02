-- Multiempresa: a RegulaIA é a plataforma; cada mineradora é uma cliente que só vê o que é dela.
-- A ligação é pelo nome da empresa (empresa.nome é UNIQUE), não pelo id: o "Recriar demo" apaga e
-- recria as empresas, e as contas ficam.
-- IF NOT EXISTS: um banco criado pelo schema_pg.sql novo (testes, primeiro start) já tem as colunas.

-- obrigação própria de uma cliente (condicionante da licença, TAC, procedimento interno);
-- vazio: norma pública, vale para todas
ALTER TABLE obrigacao ADD COLUMN IF NOT EXISTS empresa TEXT COLLATE "C";

-- de qual cliente é a conta; plataforma = 1: equipe da RegulaIA (curadoria), vê todas as empresas
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS empresa TEXT COLLATE "C";
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS plataforma INTEGER NOT NULL DEFAULT 0 CHECK (plataforma IN (0, 1));

-- de qual cliente é a ação (vazio: plataforma): cada cliente vê só a própria trilha
ALTER TABLE auditoria ADD COLUMN IF NOT EXISTS empresa TEXT COLLATE "C";
