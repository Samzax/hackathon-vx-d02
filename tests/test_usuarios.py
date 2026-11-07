"""Contas: senha, papéis, regras da TI e as contas da demo."""

import pytest

from regulaia import db, usuarios
from regulaia.usuarios import ErroConta


@pytest.fixture
def conn():
    c = db.conectar(":memory:")
    usuarios.semear(c)
    return c


def test_senha_guarda_hash_com_sal_e_confere():
    a, b = usuarios.hash_senha("segredo-123"), usuarios.hash_senha("segredo-123")
    assert a != b and "segredo" not in a                       # sal próprio, nada em claro
    assert usuarios.confere_senha("segredo-123", a)
    assert not usuarios.confere_senha("segredo-124", a)
    assert not usuarios.confere_senha("segredo-123", None)
    assert not usuarios.confere_senha("segredo-123", "lixo")


def test_entrar_com_email_em_qualquer_caixa(conn):
    usuarios.criar(conn, "Joana@Mina.com", "Joana", usuarios.GESTOR, area="Gerência de Geotecnia", senha="12345678")
    conta = usuarios.autenticar(conn, "  joana@MINA.com ", "12345678")
    assert conta and conta["nome"] == "Joana" and conta["ultimo_acesso"]
    assert "senha" not in conta and conta["tem_senha"]
    assert usuarios.autenticar(conn, "joana@mina.com", "errada!!") is None
    assert usuarios.autenticar(conn, "ninguem@mina.com", "12345678") is None
    assert usuarios.autenticar(conn, "sem-arroba", "12345678") is None


def test_conta_desativada_nao_entra(conn):
    uid = usuarios.criar(conn, "x@mina.com", "X", usuarios.DIRETORIA, senha="12345678")
    usuarios.editar(conn, uid, ativa=False)
    assert usuarios.autenticar(conn, "x@mina.com", "12345678") is None


@pytest.mark.parametrize("kw, erro", [
    ({"papel": usuarios.GESTOR, "senha": "12345678"}, "área"),
    ({"papel": "chefe", "senha": "12345678"}, "papel"),
    ({"papel": usuarios.DIRETORIA, "senha": "curta"}, "8 caracteres"),
    ({"papel": usuarios.DIRETORIA}, "precisa de senha"),
])
def test_regras_da_conta_nova(conn, kw, erro):
    with pytest.raises(ErroConta, match=erro):
        usuarios.criar(conn, "nova@mina.com", "Nova", **kw)


def test_email_repetido(conn):
    with pytest.raises(ErroConta, match="já existe"):
        usuarios.criar(conn, "TI@serraazul.demo", "Outra TI", usuarios.ADMIN, senha="12345678")


def test_nao_fica_sem_ti(conn):
    ti = usuarios.por_email(conn, "ti@serraazul.demo")
    for mudanca in ({"ativa": False}, {"papel": usuarios.DIRETORIA}, {"teste": True}):
        with pytest.raises(ErroConta, match="única conta de TI"):
            usuarios.editar(conn, ti["id"], **mudanca)
    usuarios.criar(conn, "ti@outra.com", "TI de outra empresa", usuarios.ADMIN, senha="12345678",
                   empresa="Outra Mineradora")
    with pytest.raises(ErroConta, match="única conta de TI"):     # cada cliente precisa da sua TI
        usuarios.editar(conn, ti["id"], ativa=False)
    usuarios.criar(conn, "ti2@mina.com", "TI 2", usuarios.ADMIN, senha="12345678", empresa=ti["empresa"])
    assert not usuarios.editar(conn, ti["id"], ativa=False)["ativa"]      # com outra TI da empresa, pode


def test_conta_sem_senha_so_de_teste(conn):
    demo = usuarios.conta_demo(conn)
    assert demo["teste"] and not demo["tem_senha"]
    with pytest.raises(ErroConta, match="sem senha"):
        usuarios.editar(conn, demo["id"], teste=False)
    usuarios.definir_senha(conn, demo["id"], "agora-tem")
    assert not usuarios.editar(conn, demo["id"], teste=False)["teste"]


def test_contas_da_demo_e_areas(conn, monkeypatch):
    contas = {u["email"]: u for u in usuarios.listar(conn)}
    assert {u["papel"] for u in contas.values()} == set(usuarios.PAPEIS)
    assert contas["geotecnia@serraazul.demo"]["area"] == "Gerência de Geotecnia"
    assert usuarios.listar(conn)[0]["papel"] == usuarios.ADMIN          # TI primeiro
    assert "Gerência de Geotecnia" in usuarios.areas(conn)
    # semear de novo não duplica nem desfaz o que a TI mudou
    ana = contas["geotecnia@serraazul.demo"]
    usuarios.editar(conn, ana["id"], nome="Ana S.")
    assert usuarios.semear(conn) == 0
    assert usuarios.por_email(conn, ana["email"])["nome"] == "Ana S."
    # no link público, a senha das contas da demo vem do ambiente
    monkeypatch.setenv("REGULAIA_SENHA_DEMO", "outra-senha-forte")
    c2 = db.conectar(":memory:")
    usuarios.semear(c2)
    assert usuarios.autenticar(c2, "diretoria@serraazul.demo", "outra-senha-forte")


def test_contas_sobrevivem_ao_recriar_demo(conn):
    usuarios.criar(conn, "fica@mina.com", "Fica", usuarios.DIRETORIA, senha="12345678")
    db.limpar(conn)
    assert usuarios.por_email(conn, "fica@mina.com")


def test_diretoria_troca_area_do_ativo_e_fica_no_historico():
    conn = db.conectar(":memory:")
    emp = db.criar_empresa(conn, "M")
    aid = db.criar_ativo(conn, emp, "barragem", "B1", "B1", {}, "Gerência A")
    assert db.definir_responsavel(conn, aid, "Gerência B", por="Carla")
    assert not db.definir_responsavel(conn, aid, "Gerência B", por="Carla")    # igual: nada muda
    assert db.ativos(conn, emp)[0]["responsavel"] == "Gerência B"
    ev = db.eventos(conn, aid)[0]
    assert ev["texto"] == "área responsável: Gerência A → Gerência B" and ev["por"] == "Carla"
