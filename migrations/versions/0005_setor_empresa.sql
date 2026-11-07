-- O setor seleciona fluxos e vocabulário da torre sem misturar carteiras de clientes.
ALTER TABLE empresa ADD COLUMN IF NOT EXISTS setor TEXT COLLATE "C" NOT NULL DEFAULT 'mineracao';
