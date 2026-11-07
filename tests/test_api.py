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
from regulaia import agenda, db, demo, evidencias, torre, usuarios
from tests.conftest import URL_PG

_CONTAS = json.loads((db.ROOT / "data" / "usuarios_demo.json").read_text(encoding="utf-8"))
SENHA = _CONTAS["senha"]
SERRA_AZUL = _CONTAS["empresa"]
CURADORIA = "curadoria@regulaia.demo"       # equipe da RegulaIA: aprova mudança de norma pública
OUTRA = "Mineradora Morro Alto (fictícia)"  # segunda cliente dos testes de isolamento
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


def como(c: TestClient, email: str | None = None) -> dict:
    """Sai da sessão atual e entra com outra conta (sem e-mail: a conta de teste da demo)."""
    c.cookies.clear()
    c.headers.pop("X-CSRF-Token", None)
    return entrar(c, email)


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


def test_norma_publica_so_a_curadoria_decide_e_a_decisao_vale(cliente):
    entrar(cliente, "geotecnia@serraazul.demo")
    emp = _empresa(cliente)
    como(cliente, "regulatorio@serraazul.demo")
    pendentes = cliente.get(_url(f"/empresas/{emp}/mudancas")).json()
    ob01 = next(m for m in pendentes if m["codigo"] == "OB-01")
    assert ob01["diferencas"]["prazo"][1] == "2029-12-26" and ob01["trecho"]
    assert ob01["escopo"] == "norma pública" and not ob01["decide"] and ob01["quem_decide"] == "curadoria RegulaIA"
    decisao = _url(f"/mudancas/{ob01['versao_id']}/decisao")
    como(cliente, "geotecnia@serraazul.demo")
    assert cliente.post(decisao, json={"aprovar": True}).status_code == 403
    como(cliente, "regulatorio@serraazul.demo")         # a cliente não decide norma pública por todas
    r = cliente.post(decisao, json={"aprovar": True})
    assert r.status_code == 403 and "curadoria" in r.json()["detail"]
    como(cliente, CURADORIA)
    assert cliente.post(decisao, json={"aprovar": True}).status_code == 200
    assert not [m for m in cliente.get(_url(f"/empresas/{emp}/mudancas")).json() if m["codigo"] == "OB-01"]
    h = cliente.get(_url("/obrigacoes/OB-01/historico")).json()
    assert [v["status"] for v in h] == ["substituida", "vigente"] and h[-1]["decidida_por"] == "Curadoria RegulaIA"


def test_correcao_invalida_e_recusada_e_auditada(cliente):
    entrar(cliente, CURADORIA)
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


# ----------------------------------------------------------------- multiempresa
# A RegulaIA é a plataforma; cada mineradora é uma cliente. A segunda cliente tem ativos com os
# mesmos códigos da Serra Azul (B1, B3, L1) e a mesma área ("Gerência de Geotecnia").


@pytest.fixture
def outra(cliente, cfg) -> dict:
    """Depois que a API subiu (no Postgres é ela que monta a demo), a segunda cliente e as contas dela."""
    conn = db.conectar(cfg.banco)
    base = {a["codigo"]: a for a in json.loads(demo.SERRA_AZUL.read_text(encoding="utf-8"))["ativos"]}
    serra = conn.execute("SELECT id FROM empresa WHERE nome = ?", (SERRA_AZUL,)).fetchone()["id"]
    with conn:
        eid = db.criar_empresa(conn, OUTRA, ficticia=True)
        ids = {c: db.criar_ativo(conn, eid, base[c].get("tipo", "barragem"), c, f"{base[c]['nome']} (Morro Alto)",
                                 base[c]["atributos"], base[c]["responsavel"]) for c in ("B1", "B3", "L1")}
    for email, nome, papel, area in (("diretoria@morroalto.demo", "Diretoria Morro Alto", "diretoria", None),
                                     ("geotecnia@morroalto.demo", "Geotecnia Morro Alto", "gestor", "Gerência de Geotecnia"),
                                     ("ti@morroalto.demo", "TI Morro Alto", "admin", None)):
        usuarios.criar(conn, email, nome, papel, area=area, senha=SENHA, empresa=OUTRA)
    dados = {"id": eid, "ativos": ids, "serra": serra,
             "serra_ativos": {c: db.ativo_por_codigo(conn, serra, c)["id"] for c in ("B1", "B3", "L1")}}
    conn.close()
    return dados


def _ids(c) -> list[int]:
    return [e["id"] for e in c.get(_url("/empresas")).json()]


def test_cliente_nao_ve_nem_mexe_em_nada_da_outra(cliente, outra):
    como(cliente, "diretoria@serraazul.demo")
    assert _ids(cliente) == [outra["serra"]]
    eid, b3 = outra["id"], outra["ativos"]["B3"]
    for caminho in ("painel", "ativos", "mudancas", "transicao", "linha-do-tempo", "boletim", "calendario.ics",
                    "planilha"):
        assert cliente.get(_url(f"/empresas/{eid}/{caminho}")).status_code == 404, caminho
    assert cliente.get(_url(f"/empresas/{eid}/calendario"), params={"ano": 2026, "mes": 11}).status_code == 404
    assert cliente.get(_url(f"/ativos/{b3}")).status_code == 404       # 404, não 403: nem revela que existe
    escritas = [
        cliente.post(_url("/entregas"), json={"ativo_id": b3, "codigo": "R95-01"}),
        cliente.request("DELETE", _url("/entregas"), params={"ativo_id": b3, "codigo": "R95-01", "periodo": "2026-10-1Q"}),
        cliente.post(_url("/atribuicoes"), json={"ativo_id": b3, "codigo": "R95-01", "responsavel": "Outra área"}),
        cliente.post(_url("/comentarios"), json={"ativo_id": b3, "texto": "não é meu"}),
        cliente.patch(_url(f"/ativos/{b3}/atributos"), json={"atributos": {"dpa2": 9}}),
        cliente.put(_url(f"/ativos/{b3}/responsavel"), json={"area": "Gerência de Geotecnia"}),
    ]
    assert [r.status_code for r in escritas] == [404] * len(escritas)
    pdf = evidencias.exemplo("FIR_B3_2026-10-1Q.pdf")
    r = cliente.post(_url("/evidencias/leitura"), params={"empresa_id": eid},
                     files={"arquivo": (pdf.name, pdf.read_bytes(), "application/pdf")})
    assert r.status_code == 404
    como(cliente, "diretoria@morroalto.demo")       # e do outro lado também
    assert _ids(cliente) == [eid]
    assert cliente.get(_url(f"/empresas/{outra['serra']}/painel")).status_code == 404
    assert cliente.get(_url(f"/ativos/{outra['serra_ativos']['B3']}")).status_code == 404


def test_mesma_area_em_duas_empresas_nao_se_mistura(cliente, outra):
    eu = como(cliente, "geotecnia@morroalto.demo")
    assert eu["empresa"] == OUTRA and not eu["plataforma"] and eu["visoes"] == ["Gerência de Geotecnia"]
    ativos = cliente.get(_url(f"/empresas/{outra['id']}/ativos")).json()
    assert {a["id"] for a in ativos} == {outra["ativos"]["B1"], outra["ativos"]["B3"]}
    linhas = cliente.get(_url(f"/empresas/{outra['id']}/painel")).json()["linhas"]
    assert linhas and {l["ativo_id"] for l in linhas} <= set(outra["ativos"].values())
    assert cliente.get(_url(f"/empresas/{outra['serra']}/ativos")).status_code == 404
    assert cliente.get(_url(f"/ativos/{outra['serra_ativos']['B1']}")).status_code == 404


def test_condicionante_da_licenca_de_uma_nao_vale_para_a_licenca_da_outra(cliente, outra):
    como(cliente, "diretoria@serraazul.demo")
    linhas = cliente.get(_url(f"/empresas/{outra['serra']}/painel")).json()["linhas"]
    assert {l["codigo"] for l in linhas if l["ativo"] == "L1"} >= {"LO-01", "LO-02"}
    assert cliente.get(_url("/obrigacoes/LO-01/historico")).status_code == 200
    como(cliente, "diretoria@morroalto.demo")
    linhas = cliente.get(_url(f"/empresas/{outra['id']}/painel")).json()["linhas"]
    assert linhas and not [l for l in linhas if l["codigo"].startswith("LO-")]
    assert cliente.get(_url("/obrigacoes/LO-01/historico")).status_code == 404    # obrigação própria da Serra Azul
    assert cliente.get(_url("/obrigacoes/OB-01/historico")).status_code == 200    # norma pública: todas veem


def test_fir_da_b3_lida_pela_serra_azul_cai_na_b3_da_serra_azul(cliente, outra, cfg):
    como(cliente, "diretoria@serraazul.demo")
    pdf = evidencias.exemplo("FIR_B3_2026-10-1Q.pdf")
    lido = cliente.post(_url("/evidencias/leitura"), params={"empresa_id": outra["serra"]},
                        files={"arquivo": (pdf.name, pdf.read_bytes(), "application/pdf")}).json()
    assert lido["leitura"]["ativo"] == "B3" and lido["leitura"]["empresa_id"] == outra["serra"]
    corpo = {k: lido[k] for k in ("leitura", "arquivo", "guardado_em")}
    trocada = {**corpo, "leitura": {**lido["leitura"], "empresa_id": outra["id"]}}     # leitura adulterada
    assert cliente.post(_url("/evidencias/registro"), json=trocada).status_code == 404
    sem = {**corpo, "leitura": {**lido["leitura"], "empresa_id": None}}
    assert cliente.post(_url("/evidencias/registro"), json=sem).status_code == 422
    r = cliente.post(_url("/evidencias/registro"), json=corpo)
    assert r.status_code == 201, r.text
    conn = db.conectar(cfg.banco)
    dono = conn.execute("SELECT ativo_id FROM evidencia WHERE id = ?", (r.json()["evidencia_id"],)).fetchone()[0]
    assert dono == outra["serra_ativos"]["B3"]
    assert db.evidencias_do_ativo(conn, outra["ativos"]["B3"]) == []


def test_norma_publica_decide_a_curadoria_e_obrigacao_propria_decide_a_dona(cliente, outra, cfg):
    conn = db.conectar(cfg.banco)
    lo02 = db.propor_versao(conn, "LO-02", {"prazo": "Até 20 dias após o fim do mês"}, ato_id=None,
                            trecho="(aditivo fictício da licença)", fonte="Aditivo à LO 000/2023 (fictício)")
    conn.close()
    como(cliente, "regulatorio@serraazul.demo")
    ms = {m["codigo"]: m for m in cliente.get(_url(f"/empresas/{outra['serra']}/mudancas")).json()}
    assert ms["OB-01"]["escopo"] == "norma pública" and not ms["OB-01"]["decide"]
    assert ms["LO-02"]["escopo"] == "empresa" and ms["LO-02"]["decide"] and ms["LO-02"]["empresa"] == SERRA_AZUL
    assert cliente.post(_url(f"/mudancas/{ms['OB-01']['versao_id']}/decisao"), json={"aprovar": True}).status_code == 403
    como(cliente, "diretoria@morroalto.demo")       # a outra vê a norma pública, não a condicionante da Serra Azul
    deles = {m["codigo"]: m for m in cliente.get(_url(f"/empresas/{outra['id']}/mudancas")).json()}
    assert "OB-01" in deles and "LO-02" not in deles
    assert cliente.post(_url(f"/mudancas/{lo02}/decisao"), json={"aprovar": True}).status_code == 404
    como(cliente, CURADORIA)
    assert cliente.post(_url(f"/mudancas/{lo02}/decisao"), json={"aprovar": True}).status_code == 403
    assert cliente.post(_url(f"/mudancas/{ms['OB-01']['versao_id']}/decisao"), json={"aprovar": True}).status_code == 200
    for emp in (outra["serra"], outra["id"]):       # aprovada uma vez, vale para todas as clientes
        assert "OB-01" not in {m["codigo"] for m in cliente.get(_url(f"/empresas/{emp}/mudancas")).json()}
    como(cliente, "regulatorio@serraazul.demo")
    assert cliente.post(_url(f"/mudancas/{lo02}/decisao"), json={"aprovar": True}).status_code == 200
    h = cliente.get(_url("/obrigacoes/LO-02/historico")).json()
    assert h[-1]["status"] == "vigente" and h[-1]["decidida_por"] == "Paulo Ribeiro"


def test_so_a_curadoria_mexe_no_que_vale_para_todas(cliente):
    como(cliente, "regulatorio@serraazul.demo")
    ato = {"identificacao": "RESOLUÇÃO FICTÍCIA Nº 1", "texto": "Texto de um ato qualquer, com mais de vinte letras."}
    assert cliente.post(_url("/radar/propor"), json=ato).status_code == 403
    r = cliente.post(_url("/sigbm/importar"), json={"cnpj": "00.000.000/0001-00", "monitorado_desde": "2026-05-01"})
    assert r.status_code == 403


def test_ti_cuida_so_das_contas_da_propria_empresa(cliente, outra, cfg):
    como(cliente, "ti@serraazul.demo")
    assert CURADORIA not in {c["email"] for c in cliente.get(_url("/usuarios")).json()["contas"]}
    como(cliente, "ti@morroalto.demo")
    d = cliente.get(_url("/usuarios")).json()
    assert {c["email"] for c in d["contas"]} == {"diretoria@morroalto.demo", "geotecnia@morroalto.demo",
                                                 "ti@morroalto.demo"}
    assert "Manutenção da Usina" not in d["areas"]      # área de gestor da Serra Azul
    nova = {"email": "meio.ambiente@morroalto.demo", "nome": "Meio Ambiente", "papel": "gestor",
            "area": "Gerência de Meio Ambiente", "senha": "senha-nova-123"}
    assert cliente.post(_url("/usuarios"), json=nova).status_code == 201
    outra_empresa = {**nova, "email": "intrusa@morroalto.demo", "empresa": SERRA_AZUL}
    assert cliente.post(_url("/usuarios"), json=outra_empresa).status_code == 403
    conn = db.conectar(cfg.banco)
    assert usuarios.por_email(conn, "meio.ambiente@morroalto.demo")["empresa"] == OUTRA
    for email in ("geotecnia@serraazul.demo", CURADORIA):
        alheia = usuarios.por_email(conn, email)["id"]
        assert cliente.patch(_url(f"/usuarios/{alheia}"), json={"ativa": False}).status_code == 404
        assert cliente.put(_url(f"/usuarios/{alheia}/senha"), json={"senha": "tomada-1234"}).status_code == 404
    assert usuarios.por_email(conn, "geotecnia@serraazul.demo")["ativa"]


def test_cada_cliente_ve_so_a_propria_trilha_e_a_plataforma_ve_todas(cliente, outra):
    como(cliente, "diretoria@serraazul.demo")
    cliente.post(_url("/comentarios"), json={"ativo_id": outra["serra_ativos"]["B3"], "texto": "da Serra Azul"})
    como(cliente, "diretoria@morroalto.demo")
    cliente.post(_url("/comentarios"), json={"ativo_id": outra["ativos"]["B3"], "texto": "da Morro Alto"})
    trilha = cliente.get(_url("/auditoria")).json()
    assert trilha and {t["empresa"] for t in trilha} == {OUTRA}
    assert not [t for t in trilha if t["usuario"].endswith("@serraazul.demo")]
    como(cliente, CURADORIA)
    empresas = {t["empresa"] for t in cliente.get(_url("/auditoria")).json()}
    assert {SERRA_AZUL, OUTRA} <= empresas


def test_conta_de_teste_olha_como_a_curadoria_e_o_token_de_servico_ve_todas(cliente, outra):
    eu = como(cliente)
    assert eu["empresa"] == SERRA_AZUL and eu["visoes"][-1] == "Curadoria RegulaIA (plataforma)"
    assert _ids(cliente) == [outra["serra"]]
    r = cliente.put(_url("/auth/visao"), json={"visao": "Curadoria RegulaIA (plataforma)"})
    assert r.status_code == 200 and r.json()["plataforma"] and r.json()["empresa"] is None
    assert set(_ids(cliente)) == {outra["serra"], outra["id"]}
    h = {"Authorization": "Bearer token-de-teste-do-agente"}
    assert {e["id"] for e in cliente.get(_url("/empresas"), headers=h).json()} == {outra["serra"], outra["id"]}


def test_conta_sem_empresa_nao_entra(cliente, cfg):
    conn = db.conectar(cfg.banco)
    usuarios.criar(conn, "solta@exemplo.demo", "Conta Solta", "diretoria", senha=SENHA)
    conn.close()
    cliente.cookies.clear()
    r = cliente.post(_url("/auth/login"), json={"email": "solta@exemplo.demo", "senha": SENHA})
    assert r.status_code == 403 and "regulaia_sessao" not in cliente.cookies


# ----------------------------------------------------------------- o que o front usa


def _ativo_id(c, emp: int, codigo: str) -> int:
    return next(a["id"] for a in c.get(_url(f"/empresas/{emp}/ativos")).json() if a["codigo"] == codigo)


def test_eu_traz_o_hoje_da_torre(cliente):
    assert entrar(cliente)["hoje"] == "2026-11-07"


def test_painel_traz_o_trecho_literal_e_os_periodos_em_portugues(cliente):
    entrar(cliente)
    linhas = cliente.get(_url(f"/empresas/{_empresa(cliente)}/painel")).json()["linhas"]
    fir = next(l for l in linhas if (l["ativo"], l["codigo"]) == ("B1", "R95-01"))
    assert fir["trecho"].startswith("I - preencher, quinzenalmente")
    assert fir["ultima_rotulo"] == agenda.rotulo_humano(fir["ultima"]) and "quinzena" in fir["ultima_rotulo"]
    assert fir["agenda_descricao"] == "quinzenal, até o fim de cada quinzena"
    falta = next(l for l in linhas if l["status"] == torre.DADO_FALTANDO)
    assert falta["dados_faltando_rotulos"] == [torre.campo_legivel(c) for c in falta["dados_faltando"]]
    atrasada = next(l for l in linhas if l["status"] == agenda.ATRASADA and l["faltando"])
    assert atrasada["faltando_rotulos"] == [agenda.rotulo_humano(p) for p in atrasada["faltando"]]


def test_mapa_so_na_demo_e_licenca_sem_posicao(cliente):
    entrar(cliente)
    ativos = {a["codigo"]: a for a in cliente.get(_url(f"/empresas/{_empresa(cliente)}/ativos")).json()}
    pos = json.loads((db.ROOT / "data" / "posicoes_demo.json").read_text(encoding="utf-8"))
    assert ativos["B3"]["posicao"] == pos["B3"] and ativos["L1"]["posicao"] is None


def test_resumo_areas_e_campos_do_cadastro(cliente, cfg):
    entrar(cliente)
    emp = _empresa(cliente)
    r = cliente.get(_url(f"/empresas/{emp}/resumo")).json()
    conn = db.conectar(cfg.banco)
    n_ob, n_normas = conn.execute("SELECT COUNT(*), COUNT(DISTINCT norma) FROM obrigacao").fetchone()
    n_ev = conn.execute("SELECT COUNT(*) FROM evidencia").fetchone()[0]
    conn.close()
    assert (r["ativos"], r["obrigacoes"], r["normas"], r["evidencias"]) == (8, n_ob, n_normas, n_ev) and n_ev
    a = cliente.get(_url(f"/empresas/{emp}/areas")).json()
    assert "Gerência de Geotecnia" in a["areas"] and "Gerência de Geotecnia" in a["com_conta"]
    campos = {c["campo"]: c for c in cliente.get(_url("/cadastro/campos")).json()}
    assert campos["trabalhadores_zas"]["tipo"] == "booleano" and "Autossalvamento" in campos["trabalhadores_zas"]["pergunta"]
    assert {"valor": "etapa_unica", "rotulo": "etapa única"} in campos["metodo_construtivo"]["opcoes"]


def test_entrega_com_comprovante_mostra_o_periodo_antes_e_o_arquivo_depois(cliente):
    entrar(cliente)
    emp = _empresa(cliente)
    b3 = _ativo_id(cliente, emp, "B3")
    atrasada = next(l for l in cliente.get(_url(f"/ativos/{b3}")).json()["linhas"] if l["status"] == agenda.ATRASADA)
    p = cliente.get(_url("/entregas/periodo"), params={"ativo_id": b3, "codigo": atrasada["codigo"]}).json()
    assert p["rotulo"] == agenda.rotulo_humano(p["periodo"])
    up = cliente.post(_url("/comprovantes"), params={"ativo_id": b3},
                      files={"arquivo": ("laudo.pdf", b"%PDF-1.4 laudo", "application/pdf")})
    assert up.status_code == 201, up.text
    assert Path(up.json()["guardado_em"]).read_bytes() == b"%PDF-1.4 laudo"
    r = cliente.post(_url("/entregas"), json={"ativo_id": b3, "codigo": atrasada["codigo"],
                                              "arquivo": up.json()["guardado_em"]})
    assert r.status_code == 201 and r.json()["periodo"] == p["periodo"]
    h = cliente.get(_url(f"/ativos/{b3}/obrigacoes/{atrasada['codigo']}/historico")).json()
    assert any(e["arquivo_nome"] == "laudo.pdf" and e["baixa_manual"] for e in h["evidencias"])
    assert any(e["tipo"] == "entrega" for e in h["eventos"])
    como(cliente, "usina@serraazul.demo")       # ativo de outra área: nem o comprovante
    assert cliente.post(_url("/comprovantes"), params={"ativo_id": b3},
                        files={"arquivo": ("x.pdf", b"x", "application/pdf")}).status_code == 403


def test_mudanca_traz_a_analise_o_tamanho_e_a_decisao_fica_registrada(cliente):
    entrar(cliente, CURADORIA)
    emp = _empresa(cliente)
    ob01 = next(m for m in cliente.get(_url(f"/empresas/{emp}/mudancas")).json() if m["codigo"] == "OB-01")
    assert ob01["decide"] and ob01["norma"] == "Res. ANM 220/2025" and ob01["analise"]["candidatas"]
    assert ob01["tamanho"].startswith("Muda 1 obrigação (OB-01). As outras 23 da Res. ANM 220/2025 ficam iguais.")
    assert "as datas propostas aparecem no trecho" in ob01["conferencia"]
    prazo = next(c for c in ob01["campos"] if c["campo"] == "prazo")
    assert prazo["data"] and (prazo["vigente_texto"], prazo["proposto_texto"]) == ("02/08/2027", "26/12/2029")
    assert not cliente.get(_url(f"/empresas/{emp}/decisoes")).json()
    assert cliente.post(_url(f"/mudancas/{ob01['versao_id']}/decisao"), json={"aprovar": True}).status_code == 200
    d = cliente.get(_url(f"/empresas/{emp}/decisoes")).json()
    assert [(x["codigo"], x["aprovada"], x["corrigida"]) for x in d] == [("OB-01", True, False)]
    assert d[0]["decidida_por"] == "Curadoria RegulaIA" and d[0]["ato_nome"].startswith("Resolução ANM nº 245")
    obs = cliente.get(_url(f"/empresas/{emp}/obrigacoes")).json()
    assert obs[0]["codigo"] == "OB-01" and obs[0]["mudou"]
    h = cliente.get(_url("/obrigacoes/OB-01/historico")).json()
    assert h[-1]["ato_nome"] == d[0]["ato_nome"] and h[-1]["dispositivo"] == "Res. ANM 220/2025 art. 7 §1"


def test_radar_traz_o_funil_e_o_ato_de_exemplo_e_analisado_do_cache(cliente):
    entrar(cliente)
    r = cliente.get(_url("/radar")).json()
    funil = json.loads((db.ROOT / "data" / "funil_dou.json").read_text(encoding="utf-8"))
    assert (r["funil"]["atos"], r["funil"]["anm"]) == (funil["atos"], funil["anm"])
    assert r["funil"]["normativos"] == len(r["analises"]) and r["funil"]["mudam"] == 1
    ex = cliente.get(_url("/radar/exemplo")).json()
    an = cliente.post(_url("/radar/analise"), json={"texto": ex["texto"]})
    assert an.status_code == 200, an.text
    an = an.json()
    assert an["ato"] == ex["identificacao"] and an["aprovadas"] >= 1
    assert an["candidatas"][0]["motivos"] and all(m["trecho"] for m in an["mudancas"])


def test_transicao_vigencias_e_plano(cliente):
    entrar(cliente)
    emp = _empresa(cliente)
    t = cliente.get(_url(f"/empresas/{emp}/transicao")).json()
    assert all(x["ativo_nome"] and x["saem"] + x["entram"] for x in t)
    assert any(p["so_para_outros"] for x in t for p in x["temas"])     # "só para DPA2 ≥ 4"
    faixas = {(f["ativo"], f["norma"]): f for f in cliente.get(_url(f"/empresas/{emp}/vigencias")).json()}
    assert faixas[("B1", "Res. ANM 95/2022")]["ate"] == "2027-08-01"
    assert faixas[("B1", "Res. ANM 220/2025")]["desde"] == "2027-08-02"
    assert cliente.get(_url(f"/empresas/{emp}/plano-transicao")).text.startswith("# Plano de transição")
    assert cliente.get(_url(f"/empresas/{emp}/plano-transicao"), params={"formato": "pdf"}).content[:4] == b"%PDF"


def test_documentos_de_exemplo_so_os_da_lista(cliente):
    entrar(cliente)
    nomes = [x["nome"] for x in cliente.get(_url("/evidencias/exemplos")).json()]
    assert "FIR_B3_2026-10-1Q.pdf" in nomes
    assert cliente.get(_url("/evidencias/exemplos/FIR_B3_2026-10-1Q.pdf")).content[:4] == b"%PDF"
    assert cliente.get(_url("/evidencias/exemplos/..%2F..%2Fpyproject.toml")).status_code == 404
    lido = cliente.post(_url("/evidencias/leitura"), params={"empresa_id": _empresa(cliente)},
                        files={"arquivo": ("FIR_B2_2026-11-1Q_anomalia.pdf",
                                           evidencias.exemplo("FIR_B2_2026-11-1Q_anomalia.pdf").read_bytes(),
                                           "application/pdf")}).json()
    assert lido["leitura"]["gatilhos"] and lido["abre"] and lido["periodo_rotulo"]


def test_sigbm_busca_diz_alertas_e_ufs(cliente):
    entrar(cliente)
    r = cliente.get(_url("/sigbm/busca"), params={"termo": "33.592.510/0001-54"}).json()
    vale = r["achadas"][0]
    assert vale["nome"] == "VALE S.A." and vale["na_pnsb"] and "MG" in vale["ufs"] and r["exportado_em"]


def test_api_serve_o_front_na_mesma_origem(cfg, tmp_path):
    front = tmp_path / "front"
    (front / "caixa").mkdir(parents=True)
    (front / "index.html").write_text("<html>torre</html>", encoding="utf-8")
    (front / "caixa" / "index.html").write_text("<html>caixa</html>", encoding="utf-8")
    from dataclasses import replace
    with TestClient(criar_app(replace(cfg, front=str(front)))) as c:
        assert c.get("/").text == "<html>torre</html>" and "caixa" in c.get("/caixa/").text
        assert c.get("/health").json()["status"] == "ok"
        r = c.get(_url("/nao-existe"))
        assert r.status_code == 404 and r.json()["detail"] == "Not Found"
        assert c.post(_url("/auth/demo")).status_code == 200


# ----------------------------------------------------------------- descoberta de normas
# A fila da demo (data/descoberta_demo.json) vem das fontes de verdade: Senado, ANMlegis e Assembleia de Minas.

CAUCAO = "MG:DEC:48747/2023"        # regulamenta a caução da Lei MG 23.291 (que está no catálogo)


def _cobertura(c, emp: int) -> dict:
    r = c.get(_url(f"/empresas/{emp}/cobertura"))
    assert r.status_code == 200, r.text
    return {(i["jurisdicao"], i["tipo_ativo"]): i for i in r.json()}


def test_cobertura_mostra_catalogo_fontes_lidas_lacunas_e_o_que_espera(cliente):
    entrar(cliente)
    itens = _cobertura(cliente, _empresa(cliente))
    assert set(itens) == {("BR", "barragem"), ("BR", "equipamento"), ("BR", "unidade"), ("MG", "barragem"),
                          ("MG", "unidade")}
    mg = itens[("MG", "barragem")]
    assert mg["jurisdicao_nome"] == "Minas Gerais" and mg["ativos"] == ["B1", "B2", "B3", "B4"]
    assert mg["estado"] == "curadoria_pendente" and mg["verificada"]
    assert mg["estado_rotulo"] == "normas relevantes esperando a curadoria"
    assert [(f["nome"], f["desde"], f["ate"]) for f in mg["fontes"]] == [("Assembleia de Minas", 1989, 2026)]
    assert "Lei MG 23.291/2019" in mg["catalogadas"] and any("Copam" in lac for lac in mg["lacunas"])
    caucao = next(n for n in mg["em_curadoria"] if n["chave"] == CAUCAO)
    assert caucao["cita_catalogo"] == ["Lei MG 23.291/2019"] and caucao["deveres"] and caucao["url"]
    assert mg["aprovadas"] == []
    br = itens[("BR", "equipamento")]
    assert br["estado"] == "coberta" and br["catalogadas"] == ["NR-13"] and br["lacunas"]     # coberta, com as lacunas
    assert {f["nome"] for f in br["fontes"]} == {"Senado Federal", "ANMlegis (ANM)"}


def test_cobertura_cliente_ve_so_a_dela_e_estado_sem_fonte_nunca_e_verificado(cliente, outra, cfg):
    conn = db.conectar(cfg.banco)
    with conn:
        db.criar_ativo(conn, outra["id"], "barragem", "P1", "Barragem no Pará (Morro Alto)", {"uf": "PA"},
                       "Gerência de Geotecnia")
    conn.close()
    como(cliente, "diretoria@serraazul.demo")
    assert cliente.get(_url(f"/empresas/{outra['id']}/cobertura")).status_code == 404
    como(cliente, "diretoria@morroalto.demo")
    assert cliente.get(_url(f"/empresas/{outra['serra']}/cobertura")).status_code == 404
    pa = _cobertura(cliente, outra["id"])[("PA", "barragem")]
    assert pa["estado"] == "sem_fonte" and not pa["verificada"] and pa["fontes"] == []
    assert "cobertura não verificada" in pa["estado_rotulo"] and pa["jurisdicao_nome"] == "Pará"
    como(cliente, CURADORIA)                            # a plataforma vê a de qualquer cliente
    assert ("PA", "barragem") in _cobertura(cliente, outra["id"])
    assert ("PA", "barragem") not in _cobertura(cliente, outra["serra"])


def test_cobertura_do_gestor_so_com_os_ativos_da_area(cliente):
    como(cliente, "geotecnia@serraazul.demo")
    itens = _cobertura(cliente, _empresa(cliente))
    assert set(itens) == {("BR", "barragem"), ("MG", "barragem")}
    assert all(i["ativos"] == ["B1", "B3"] for i in itens.values())


def test_fila_de_normas_candidatas_e_so_da_plataforma(cliente):
    caminhos = [("GET", "/normas-candidatas"), ("GET", f"/normas-candidatas/{CAUCAO}"),
                ("POST", f"/normas-candidatas/{CAUCAO}/decisao")]
    for email in ("diretoria@serraazul.demo", "regulatorio@serraazul.demo", "ti@serraazul.demo"):
        como(cliente, email)
        for metodo, caminho in caminhos:
            r = cliente.request(metodo, _url(caminho), json={"decisao": "aprovar"} if metodo == "POST" else None)
            assert r.status_code == 403, (email, caminho)
    como(cliente, CURADORIA)
    assert cliente.get(_url(f"/normas-candidatas/{CAUCAO}")).json()["status"] == "relevante"     # nada mudou


def test_fila_filtra_por_jurisdicao_e_status_com_o_que_a_ia_disse(cliente):
    como(cliente, CURADORIA)
    f = cliente.get(_url("/normas-candidatas"), params={"jurisdicao": "MG"}).json()
    assert f["decide"] and f["normas"] and {(n["jurisdicao"], n["status"]) for n in f["normas"]} == {("MG", "relevante")}
    assert f["contagem"]["relevante"] == len(f["normas"]) and f["contagem"]["irrelevante"] > 0
    assert [j["sigla"] for j in f["jurisdicoes"]] == ["BR", "MG"] and f["status_rotulos"]["aprovada"]
    confs = [n["triagem"]["confianca"] for n in f["normas"]]
    assert confs == sorted(confs)                       # as que mais precisam de olho primeiro
    caucao = next(n for n in f["normas"] if n["chave"] == CAUCAO)
    assert caucao["fonte_nome"] == "Assembleia de Minas" and caucao["status_rotulo"] == "esperando curadoria"
    assert caucao["url"].startswith("https://www.almg.gov.br/") and caucao["cita_catalogo"] == ["Lei MG 23.291/2019"]
    t = caucao["triagem"]
    assert t["relevante"] and "barragem" in t["tipos_ativo"] and t["deveres"] and t["motivo"] and t["modelo"]
    assert t["leu_texto"] is False and caucao["indexacao"] is None      # a lista não traz a indexação
    lidas = cliente.get(_url("/normas-candidatas"), params={"status": "relevante", "jurisdicao": "mg"}).json()["normas"]
    assert any(n["triagem"]["leu_texto"] for n in lidas)
    duas = cliente.get(_url("/normas-candidatas"), params=[("status", "irrelevante"), ("status", "aprovada")]).json()
    assert duas["normas"] and {n["status"] for n in duas["normas"]} == {"irrelevante"}
    assert cliente.get(_url("/normas-candidatas"), params={"status": "talvez"}).status_code == 422


def test_norma_candidata_pela_chave_com_dois_pontos_e_barra(cliente):
    como(cliente, CURADORIA)
    for caminho in (CAUCAO, "MG%3ADEC%3A48747%2F2023"):     # o front manda a chave codificada
        n = cliente.get(_url(f"/normas-candidatas/{caminho}"))
        assert n.status_code == 200, n.text
        assert n.json()["chave"] == CAUCAO and n.json()["indexacao"]
    assert cliente.get(_url("/normas-candidatas/MG:DEC:1/1900")).status_code == 404


def test_curadoria_aprova_com_o_email_na_auditoria_e_a_cobertura_da_cliente_muda(cliente):
    como(cliente, CURADORIA)
    emp = _empresa(cliente)
    r = cliente.post(_url(f"/normas-candidatas/{CAUCAO}/decisao"),
                     json={"decisao": "aprovar", "nota": "extrair a caução do art. 7º"})
    assert r.status_code == 200, r.text
    n = r.json()
    assert (n["status"], n["status_rotulo"]) == ("aprovada", "aprovada, falta extrair")
    assert n["decidida_por"] == CURADORIA and n["decidida_em"] and n["nota"] == "extrair a caução do art. 7º"
    trilha = cliente.get(_url("/auditoria")).json()
    a = next(t for t in trilha if t["acao"] == "descoberta.decidir")
    assert (a["alvo"], a["usuario"], a["empresa"], a["resultado"]) == (CAUCAO, CURADORIA, None, "ok")
    assert a["detalhe"] == {"decisao": "aprovar", "nota": "extrair a caução do art. 7º"}
    como(cliente, "diretoria@serraazul.demo")           # a cliente vê: aprovada, falta extrair
    mg = _cobertura(cliente, emp)[("MG", "barragem")]
    assert CAUCAO in {x["chave"] for x in mg["aprovadas"]} and CAUCAO not in {x["chave"] for x in mg["em_curadoria"]}


def test_curadoria_reabre_o_que_a_ia_descartou_e_o_que_nao_se_decide_e_recusado(cliente):
    como(cliente, CURADORIA)
    descartada = cliente.get(_url("/normas-candidatas"), params={"status": "irrelevante"}).json()["normas"][0]
    r = cliente.post(_url(f"/normas-candidatas/{descartada['chave']}/decisao"), json={"decisao": "aprovar"})
    assert r.status_code == 200 and r.json()["status"] == "aprovada"
    catalogada = cliente.get(_url("/normas-candidatas"), params={"status": "catalogada"}).json()["normas"][0]
    r = cliente.post(_url(f"/normas-candidatas/{catalogada['chave']}/decisao"), json={"decisao": "descartar"})
    assert r.status_code == 422 and "catálogo" in r.json()["detail"]
    assert cliente.get(_url("/auditoria")).json()[0]["resultado"] == "recusado"
    assert cliente.post(_url("/normas-candidatas/MG:DEC:1/1900/decisao"), json={"decisao": "aprovar"}).status_code == 404
    assert cliente.post(_url(f"/normas-candidatas/{CAUCAO}/decisao"), json={"decisao": "talvez"}).status_code == 422


def test_job_da_descoberta_busca_tria_e_nao_mexe_no_que_a_curadoria_decidiu(cliente, cfg, tmp_path):
    """python -m api.jobs descoberta, com os trechos reais das fontes e uma IA roteirizada (sem internet)."""
    from api import jobs
    from regulaia.ia import Roteador
    from tests.test_descoberta import IRRELEVANTE, BaixadorFixo, IAFalsa

    como(cliente, CURADORIA)
    assert cliente.post(_url(f"/normas-candidatas/{CAUCAO}/decisao"), json={"decisao": "aprovar"}).status_code == 200
    conn = db.conectar(cfg.banco)
    with conn:      # como se a fonte tivesse publicado de novo: a Res. 127 volta a ser candidata nova
        conn.execute("UPDATE norma_candidata SET status = 'nova', triagem = NULL WHERE chave = 'BR:RES-ANM:127/2022'")
    conn.close()
    ia = IAFalsa({}, IRRELEVANTE)
    resumo = jobs.descoberta(cfg, desde=2010, baixador=BaixadorFixo(tmp_path / "fontes"), paralelo=1,
                             roteador=Roteador(db.conectar(cfg.cache), provedores={"opencode": ia}))
    assert {r["fonte"] for r in resumo["busca"]} == {"senado", "anm", "almg"} and not jobs.falhou(resumo)
    assert all(r["lidas"] for r in resumo["busca"]) and resumo["triagem"]["erro"] is None
    assert (resumo["triagem"]["triadas"], resumo["triagem"]["restam"]) == (1, 0) and "nova" not in resumo["fila"]
    assert [c[0] for c in ia.chamadas] == ["RESOLUÇÃO ANM Nº 127, DE 22 DE DEZEMBRO DE 2022"]   # só a nova vai à IA
    assert cliente.get(_url("/normas-candidatas/BR:RES-ANM:127/2022")).json()["status"] == "irrelevante"
    assert cliente.get(_url(f"/normas-candidatas/{CAUCAO}")).json()["status"] == "aprovada"      # decisão fica
    mg = _cobertura(cliente, _empresa(cliente))[("MG", "barragem")]
    assert [(f["desde"], f["ate"]) for f in mg["fontes"]] == [(2010, 2026)]     # a cobertura diz o que foi lido
    assert jobs.falhou({"busca": [{"falhas": ["2020: ConnectError"]}]})
    assert jobs.falhou({"busca": [], "triagem": {"erro": "nenhum provedor"}})
    assert jobs.main(["descoberta", "--fontes", "planalto"]) == 2


def test_status_da_fila_na_api_sao_os_do_dominio():
    from typing import get_args

    from api.rotas.descoberta import StatusCandidata
    from regulaia import descoberta
    assert get_args(StatusCandidata) == descoberta.STATUS


# ----------------------------------------------------------------- contrato


def test_contrato_openapi_versionado_bate_com_a_api(cliente):
    """api/openapi.json é o contrato que o front e o agente usam. Mudou a API, regere com
    `uv run python -m api.contrato` e revise a diferença no PR."""
    atual = cliente.get(_url("/openapi.json")).json()
    salvo = json.loads((db.ROOT / "api" / "openapi.json").read_text(encoding="utf-8"))
    assert atual == salvo, "contrato desatualizado: rode uv run python -m api.contrato"
