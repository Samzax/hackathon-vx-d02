"""A API: sessão, CSRF, papéis, escopo por área, auditoria e os fluxos da torre ponta a ponta.

Roda no SQLite por padrão e no Postgres com REGULAIA_TESTE_PG (ver conftest.py)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.config import Config
from api.main import PREFIXO, criar_app
from regulaia import agenda, db, demo, evidencias, torre
from tests.conftest import URL_PG

SENHA = json.loads((db.ROOT / "data" / "usuarios_demo.json").read_text(encoding="utf-8"))["senha"]
_MODELO: dict[str, Path] = {}


def _banco_da_demo(tmp_path: Path) -> tuple[str, str]:
    """Banco montado uma vez (cadastro, histórico, radar) e copiado para cada teste."""
    if URL_PG:
        return str(tmp_path / "api.db"), str(tmp_path / "api.db")
    if "db" not in _MODELO:
        pasta = Path(tmp_path.parent / "modelo_api")
        pasta.mkdir(exist_ok=True)
        demo.preparar(pasta / "demo.db", cache=pasta / "cache.db")
        _MODELO["db"], _MODELO["cache"] = pasta / "demo.db", pasta / "cache.db"
    shutil.copy(_MODELO["db"], tmp_path / "api.db")
    shutil.copy(_MODELO["cache"], tmp_path / "cache.db")
    return str(tmp_path / "api.db"), str(tmp_path / "cache.db")


@pytest.fixture
def cfg(tmp_path):
    banco, cache = _banco_da_demo(tmp_path)
    return Config(banco=banco, banco_cache=cache, armazenamento=str(tmp_path / "uploads"),
                  token_servico="token-de-teste-do-agente")


@pytest.fixture
def cliente(cfg):
    with TestClient(criar_app(cfg)) as c:
        yield c


def _url(caminho: str) -> str:
    return PREFIXO + caminho


def entrar(c: TestClient, email: str | None = None) -> dict:
    r = c.post(_url("/auth/demo")) if email is None else c.post(_url("/auth/login"), json={"email": email, "senha": SENHA})
    assert r.status_code == 200, r.text
    c.headers["X-CSRF-Token"] = c.cookies["regulaia_csrf"]
    return r.json()


def _empresa(c) -> int:
    return c.get(_url("/empresas")).json()[0]["id"]


# ----------------------------------------------------------------- sessão e CSRF


def test_health_diz_o_banco(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["banco"] == ("postgres" if URL_PG else "sqlite") or r.json()["status"] == "ok"
    assert r.headers["X-Request-Id"]


def test_sem_sessao_nada_de_dado_regulatorio(cliente):
    assert cliente.get(_url("/empresas")).status_code == 401
    assert cliente.get(_url("/empresas/1/painel")).status_code == 401


def test_senha_errada_e_recusada_e_fica_na_auditoria(cliente):
    r = cliente.post(_url("/auth/login"), json={"email": "diretoria@serraazul.demo", "senha": "errada-123"})
    assert r.status_code == 401
    entrar(cliente, "diretoria@serraazul.demo")
    trilha = cliente.get(_url("/auditoria")).json()
    assert any(t["acao"] == "login" and t["resultado"] == "recusado" for t in trilha)


def test_cookie_de_sessao_e_httponly_e_o_banco_guarda_so_o_hash(cliente, cfg):
    r = cliente.post(_url("/auth/demo"))
    cookie = next(h for h in r.headers.get_list("set-cookie") if h.startswith("regulaia_sessao="))
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    token = cliente.cookies["regulaia_sessao"]
    conn = db.conectar(cfg.banco)
    hashes = [x[0] for x in conn.execute("SELECT token_hash FROM sessao").fetchall()]
    assert token not in hashes and len(hashes[0]) == 64


def test_escrita_sem_csrf_e_recusada(cliente):
    entrar(cliente)
    del cliente.headers["X-CSRF-Token"]
    r = cliente.post(_url("/comentarios"), json={"ativo_id": 1, "texto": "oi"})
    assert r.status_code == 403 and "CSRF" in r.json()["detail"]


def test_sair_derruba_a_sessao(cliente):
    entrar(cliente)
    assert cliente.post(_url("/auth/logout")).status_code == 204
    assert cliente.get(_url("/auth/me")).status_code == 401


def test_token_de_servico_le_a_torre_sem_cookie(cliente):
    h = {"Authorization": "Bearer token-de-teste-do-agente"}
    emp = cliente.get(_url("/empresas"), headers=h)
    assert emp.status_code == 200
    assert cliente.get(_url(f"/empresas/{emp.json()[0]['id']}/painel"), headers=h).status_code == 200
    assert cliente.get(_url("/empresas"), headers={"Authorization": "Bearer outro"}).status_code == 401


# ----------------------------------------------------------------- painel e escopo


def test_painel_da_api_e_o_mesmo_da_torre(cliente, cfg):
    entrar(cliente)
    emp = _empresa(cliente)
    p = cliente.get(_url(f"/empresas/{emp}/painel")).json()
    conn = db.conectar(cfg.banco)
    from api.config import desde_padrao, hoje_padrao
    e = dict(conn.execute("SELECT * FROM empresa WHERE id = ?", (emp,)).fetchone())
    esperado = torre.painel(conn, emp, hoje_padrao(), desde_padrao(e))
    assert len(p["linhas"]) == len(esperado)
    assert p["contagem"][agenda.ATRASADA] == 4          # README e roteiro: 4 atrasadas no dia da demo
    assert p["contagem"][torre.DADO_FALTANDO] == 1
    assert p["contagem"][agenda.VENCE_LOGO] == 3
    so = cliente.get(_url(f"/empresas/{emp}/painel"), params={"status": agenda.ATRASADA}).json()
    assert {l["status"] for l in so["linhas"]} == {agenda.ATRASADA} and len(so["linhas"]) == 4


def test_gestor_so_ve_a_propria_area(cliente):
    entrar(cliente, "geotecnia@serraazul.demo")
    emp = _empresa(cliente)
    ativos = cliente.get(_url(f"/empresas/{emp}/ativos")).json()
    assert ativos and all(a["responsavel"] == "Gerência de Geotecnia" for a in ativos)
    linhas = cliente.get(_url(f"/empresas/{emp}/painel")).json()["linhas"]
    assert {l["ativo"] for l in linhas} == {a["codigo"] for a in ativos}
    eu = cliente.get(_url("/auth/me")).json()
    assert eu["papel_efetivo"] == "gestor" and eu["visoes"] == ["Gerência de Geotecnia"]


def test_gestor_nao_abre_nem_mexe_em_ativo_de_outra_area(cliente):
    entrar(cliente)
    emp = _empresa(cliente)
    outro = next(a for a in cliente.get(_url(f"/empresas/{emp}/ativos")).json()
                 if a["responsavel"] != "Gerência de Geotecnia")
    cliente.cookies.clear()
    entrar(cliente, "geotecnia@serraazul.demo")
    assert cliente.get(_url(f"/ativos/{outro['id']}")).status_code == 403
    r = cliente.post(_url("/comentarios"), json={"ativo_id": outro["id"], "texto": "não é meu"})
    assert r.status_code == 403


def test_ti_nao_ve_dado_regulatorio_e_so_ela_cuida_das_contas(cliente):
    entrar(cliente, "ti@serraazul.demo")
    assert cliente.get(_url("/empresas")).status_code == 403
    contas = cliente.get(_url("/usuarios")).json()["contas"]
    assert all("senha" not in c for c in contas)
    cliente.cookies.clear()
    entrar(cliente, "diretoria@serraazul.demo")
    assert cliente.get(_url("/usuarios")).status_code == 403


def test_conta_de_teste_troca_de_visao_e_age_como_ela(cliente):
    eu = entrar(cliente)
    assert "Gerência de Geotecnia" in eu["visoes"]
    r = cliente.put(_url("/auth/visao"), json={"visao": "Gerência de Geotecnia"})
    assert r.status_code == 200 and r.json()["papel_efetivo"] == "gestor"
    emp = _empresa(cliente)
    assert all(a["responsavel"] == "Gerência de Geotecnia" for a in cliente.get(_url(f"/empresas/{emp}/ativos")).json())
    assert cliente.put(_url("/auth/visao"), json={"visao": "Inventada"}).status_code == 422


def test_ficha_do_ativo_traz_pendencias_evidencias_e_historico(cliente):
    entrar(cliente)
    emp = _empresa(cliente)
    b3 = next(a for a in cliente.get(_url(f"/empresas/{emp}/ativos")).json() if a["codigo"] == "B3")
    f = cliente.get(_url(f"/ativos/{b3['id']}")).json()
    assert f["ativo"]["codigo"] == "B3" and f["linhas"] and f["evidencias"]
    assert all(l["dispositivo"] for l in f["linhas"])


# ----------------------------------------------------------------- escrita


def test_entrega_tira_a_obrigacao_do_atraso_e_fica_no_historico_e_na_auditoria(cliente):
    entrar(cliente)
    emp = _empresa(cliente)
    antes = cliente.get(_url(f"/empresas/{emp}/painel"), params={"status": agenda.ATRASADA}).json()
    alvo = antes["linhas"][0]
    r = cliente.post(_url("/entregas"), json={"ativo_id": alvo["ativo_id"], "codigo": alvo["codigo"],
                                              "obs": "entregue pela API"})
    assert r.status_code == 201, r.text
    depois = cliente.get(_url(f"/empresas/{emp}/painel"), params={"status": agenda.ATRASADA}).json()
    mesma = [l for l in depois["linhas"] if (l["ativo"], l["codigo"]) == (alvo["ativo"], alvo["codigo"])]
    assert not mesma or len(mesma[0]["faltando"]) < len(alvo["faltando"])
    eventos = cliente.get(_url(f"/ativos/{alvo['ativo_id']}")).json()["eventos"]
    assert any(ev["tipo"] == "entrega" and "entregue pela API" in ev["texto"] for ev in eventos)
    assert any(t["acao"] == "entrega" for t in cliente.get(_url("/auditoria")).json())


def test_so_regulatorio_ou_diretoria_decidem_e_a_decisao_vale(cliente):
    entrar(cliente, "geotecnia@serraazul.demo")
    emp = _empresa(cliente)
    cliente.cookies.clear()
    entrar(cliente, "regulatorio@serraazul.demo")
    pendentes = cliente.get(_url(f"/empresas/{emp}/mudancas")).json()
    ob01 = next(m for m in pendentes if m["codigo"] == "OB-01")
    assert ob01["diferencas"]["prazo"][1] == "2029-12-26" and ob01["trecho"]
    cliente.cookies.clear()
    entrar(cliente, "geotecnia@serraazul.demo")
    assert cliente.post(_url(f"/mudancas/{ob01['versao_id']}/decisao"), json={"aprovar": True}).status_code == 403
    cliente.cookies.clear()
    entrar(cliente, "regulatorio@serraazul.demo")
    assert cliente.post(_url(f"/mudancas/{ob01['versao_id']}/decisao"), json={"aprovar": True}).status_code == 200
    assert not [m for m in cliente.get(_url(f"/empresas/{emp}/mudancas")).json() if m["codigo"] == "OB-01"]
    h = cliente.get(_url("/obrigacoes/OB-01/historico")).json()
    assert [v["status"] for v in h] == ["substituida", "vigente"] and h[-1]["decidida_por"] == "Paulo Ribeiro"


def test_correcao_invalida_e_recusada_e_auditada(cliente):
    entrar(cliente, "regulatorio@serraazul.demo")
    emp = _empresa(cliente)
    m = cliente.get(_url(f"/empresas/{emp}/mudancas")).json()[0]
    r = cliente.post(_url(f"/mudancas/{m['versao_id']}/decisao"),
                     json={"aprovar": True, "correcoes": {"prazo": "26/12/2029"}})
    assert r.status_code == 422
    assert any(t["acao"] == "decisao" and t["resultado"] == "recusado" for t in cliente.get(_url("/auditoria")).json())


def test_fir_em_pdf_vira_baixa_na_obrigacao_certa(cliente):
    entrar(cliente)
    emp = _empresa(cliente)
    pdf = evidencias.exemplo("FIR_B3_2026-10-1Q.pdf")
    r = cliente.post(_url("/evidencias/leitura"), params={"empresa_id": emp},
                     files={"arquivo": (pdf.name, pdf.read_bytes(), "application/pdf")})
    assert r.status_code == 200, r.text
    lido = r.json()
    assert lido["completa"] and lido["leitura"]["ativo"] == "B3" and lido["leitura"]["periodo"] == "2026-10-1Q"
    assert Path(lido["guardado_em"]).exists() and lido["sha256"] in lido["guardado_em"]
    r = cliente.post(_url("/evidencias/registro"), json={k: lido[k] for k in ("leitura", "arquivo", "guardado_em")})
    assert r.status_code == 201, r.text


def test_gestor_nao_registra_documento_de_ativo_alheio(cliente):
    entrar(cliente, "usina@serraazul.demo")
    emp = _empresa(cliente)
    pdf = evidencias.exemplo("FIR_B3_2026-10-1Q.pdf")
    lido = cliente.post(_url("/evidencias/leitura"), params={"empresa_id": emp},
                        files={"arquivo": (pdf.name, pdf.read_bytes(), "application/pdf")}).json()
    r = cliente.post(_url("/evidencias/registro"), json={k: lido[k] for k in ("leitura", "arquivo", "guardado_em")})
    assert r.status_code == 403


def test_downloads_boletim_pdf_ics_e_planilha(cliente):
    entrar(cliente)
    emp = _empresa(cliente)
    assert cliente.get(_url(f"/empresas/{emp}/boletim")).text.startswith("#")
    assert cliente.get(_url(f"/empresas/{emp}/boletim"), params={"formato": "pdf"}).content[:4] == b"%PDF"
    assert "BEGIN:VCALENDAR" in cliente.get(_url(f"/empresas/{emp}/calendario.ics")).text
    assert cliente.get(_url(f"/empresas/{emp}/planilha")).content[:2] == b"PK"


def test_transicao_e_linha_do_tempo(cliente):
    entrar(cliente)
    emp = _empresa(cliente)
    t = cliente.get(_url(f"/empresas/{emp}/transicao")).json()
    assert t and all(x["temas"] for x in t)
    assert any(f["dia"] == "2027-08-02" for f in cliente.get(_url(f"/empresas/{emp}/linha-do-tempo")).json())


# ----------------------------------------------------------------- contrato


def test_contrato_openapi_versionado_bate_com_a_api(cliente):
    """api/openapi.json é o contrato que o front e o agente usam. Mudou a API, regere com
    `uv run python -m api.contrato` e revise a diferença no PR."""
    atual = cliente.get(_url("/openapi.json")).json()
    salvo = json.loads((db.ROOT / "api" / "openapi.json").read_text(encoding="utf-8"))
    assert atual == salvo, "contrato desatualizado: rode uv run python -m api.contrato"
