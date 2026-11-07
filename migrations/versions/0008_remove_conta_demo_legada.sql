-- 0008: apaga a conta da demo do nome antigo (curadoria@regulaia.demo), pedido do usuário em 7/11/2026.
-- Só a do seed (criado_por = 'demo'). A sessão aponta para o usuário por chave estrangeira e vai antes;
-- a auditoria guarda o e-mail como texto e fica. Não muda tabela nem coluna (o schema_pg.sql não muda).
DELETE FROM sessao WHERE usuario_id IN (
    SELECT id FROM usuario WHERE email = 'curadoria@regulaia.demo' AND criado_por = 'demo');
DELETE FROM usuario WHERE email = 'curadoria@regulaia.demo' AND criado_por = 'demo';
