"""Sessão, CSRF, papéis e o escopo do que cada pessoa vê.

- Sessão: cookie HttpOnly com um token aleatório de 256 bits; no banco fica só o SHA-256.
- CSRF: double submit. O login devolve também um cookie legível `regulaia_csrf`, e toda
  escrita (POST/PUT/PATCH/DELETE) precisa mandar o mesmo valor no cabeçalho X-CSRF-Token.
- Empresa: a Mitra é a plataforma; cada mineradora é uma cliente. A conta de cliente só vê a
  própria empresa (o que é de outra devolve 404, para não revelar que existe). A equipe da
  plataforma (`usuario.plataforma`) e o token de serviço veem todas.
- Papel: TI só administra contas; Diretoria e Regulatório veem toda a empresa; gestor vê a própria área.
- Mudança de norma pública (Res. ANM, NR...): quem aprova é a curadoria da plataforma, uma vez para
  todas as clientes. Obrigação própria da empresa (condicionante, TAC): quem aprova é ela mesma.
- Plataforma: nos dados operacionais da cliente (entrega, comprovante, evidência, comentário,
  atribuição, cadastro e responsável do ativo) só lê; quem escreve é a própria empresa. Escreve o que
  é dela: decisão de norma pública, radar, descoberta e curadoria, contas (TI da plataforma) e SIGBM.
- Conta de teste (demo e pitch): escolhe a visão (Diretoria, uma área, TI ou a curadoria da
  plataforma) e age como ela.
- Token de serviço (Bearer): o agente MCP e os jobs agem como Regulatório da plataforma, sem cookie.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response, status

from regulaia import db, usuarios

from .banco import conexao
from .config import Config

COOKIE_SESSAO = "regulaia_sessao"
COOKIE_CSRF = "regulaia_csrf"
CABECALHO_CSRF = "X-CSRF-Token"
VISAO_DIRETORIA = "Diretoria (todos os ativos)"
VISAO_TI = "TI (usuários e acessos)"
VISAO_CURADORIA = "Curadoria Mitra (plataforma)"
_ESCRITA = {"POST", "PUT", "PATCH", "DELETE"}
SO_LEITURA = "a equipe Mitra só lê os dados da empresa"


@dataclass(frozen=True)
class Escopo:
    """Quem está agindo e o que pode ver: vem da conta e, na conta de teste, da visão escolhida."""
    usuario: dict
    papel: str               # papel efetivo (na conta de teste, o da visão)
    area: str | None         # gestor: a área que ele vê
    visao: str
    assinante: str           # o nome que fica no histórico ("por")
    empresa_id: int | None = None    # cliente: a única empresa que vê; None na plataforma
    empresa: str | None = None       # o nome dela (é por ele que conta e obrigação própria se ligam)
    plataforma: bool = False         # equipe da Mitra ou token de serviço: vê todas as empresas

    @property
    def ve_tudo(self) -> bool:
        """Vê todos os ativos da empresa (na plataforma, de todas)."""
        return self.papel in usuarios.VE_TUDO

    @property
    def admin(self) -> bool:
        return self.papel == usuarios.ADMIN

    @property
    def so_leitura(self) -> bool:
        """Nos dados operacionais das clientes, só lê: a plataforma (curadoria, token de serviço)."""
        return self.plataforma

    def ve_empresa(self, empresa_id: int) -> bool:
        return self.plataforma or empresa_id == self.empresa_id

    def ve_obrigacao(self, dona: str | None) -> bool:
        """Norma pública todo mundo vê; obrigação própria, só a empresa dona (e a plataforma)."""
        return dona is None or self.plataforma or dona == self.empresa

    def decide(self, dona: str | None) -> bool:
        """Norma pública: a curadoria da plataforma. Obrigação própria: Regulatório ou Diretoria da dona."""
        if not self.ve_tudo:
            return False
        return self.plataforma if dona is None else (not self.plataforma and dona == self.empresa)

    def ve_ativo(self, ativo: dict) -> bool:
        return self.ve_tudo or (self.area is not None and ativo.get("responsavel") == self.area)

    def ve_linha(self, linha, dono_do_ativo: str | None) -> bool:
        return self.ve_tudo or (self.area is not None and self.area in (linha.responsavel, dono_do_ativo))


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(d: datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


def abrir_sessao(conn, cfg: Config, resposta: Response, usuario: dict) -> str:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    expira = _agora() + timedelta(hours=cfg.horas_sessao)
    visao = VISAO_DIRETORIA if usuario["teste"] else None
    with conn:
        conn.execute("DELETE FROM sessao WHERE expira_em < ?", (_fmt(_agora()),))
        conn.execute("INSERT INTO sessao (token_hash, usuario_id, expira_em, visao) VALUES (?, ?, ?, ?)",
                     (_hash(token), usuario["id"], _fmt(expira), visao))
    usuarios.registrar_acesso(conn, usuario["id"])
    idade = cfg.horas_sessao * 3600
    resposta.set_cookie(COOKIE_SESSAO, token, max_age=idade, httponly=True, secure=cfg.cookie_seguro,
                        samesite="lax", path="/")
    resposta.set_cookie(COOKIE_CSRF, csrf, max_age=idade, httponly=False, secure=cfg.cookie_seguro,
                        samesite="lax", path="/")
    return csrf


def fechar_sessao(conn, request: Request, resposta: Response) -> None:
    if token := request.cookies.get(COOKIE_SESSAO):
        with conn:
            conn.execute("DELETE FROM sessao WHERE token_hash = ?", (_hash(token),))
    resposta.delete_cookie(COOKIE_SESSAO, path="/")
    resposta.delete_cookie(COOKIE_CSRF, path="/")


def _sessao(conn, token: str) -> dict | None:
    r = conn.execute("SELECT * FROM sessao WHERE token_hash = ?", (_hash(token),)).fetchone()
    if r is None or r["expira_em"] < _fmt(_agora()):
        return None
    return dict(r)


def _conta_servico(conn) -> dict:
    return {"id": 0, "email": "servico@regulaia", "nome": "Agente Mitra", "papel": usuarios.REGULATORIO,
            "area": None, "teste": 0, "ativa": 1, "empresa": None, "plataforma": 1}


def empresa_da_conta(conn, u: dict) -> int | None:
    """Id da empresa da conta, pelo nome (o "Recriar demo" recria as empresas com outro id)."""
    if not u.get("empresa"):
        return None
    r = conn.execute("SELECT id FROM empresa WHERE nome = ?", (u["empresa"],)).fetchone()
    return r["id"] if r else None


def escopo_da_conta(conn, u: dict, visao: str | None = None) -> Escopo:
    """O que a conta vê e como age. Na conta de teste, `visao` é a escolhida no seletor."""
    if u["teste"] and visao == VISAO_CURADORIA:
        return Escopo(u, usuarios.REGULATORIO, None, VISAO_CURADORIA, VISAO_CURADORIA, plataforma=True)
    if u.get("plataforma"):
        rotulo = {usuarios.DIRETORIA: "Plataforma (todas as empresas)", usuarios.REGULATORIO: VISAO_CURADORIA,
                  usuarios.ADMIN: "TI da plataforma"}.get(u["papel"], u["area"] or "")
        return Escopo(u, u["papel"], u["area"], rotulo, u["nome"], plataforma=True)
    if not u.get("empresa"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "conta sem empresa: peça à TI da sua empresa para corrigir")
    eid = empresa_da_conta(conn, u)
    if eid is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"a empresa desta conta ({u['empresa']}) não está na torre")
    na_empresa = {"empresa_id": eid, "empresa": u["empresa"]}
    if u["teste"]:
        visao = visao or VISAO_DIRETORIA
        if visao == VISAO_DIRETORIA:
            return Escopo(u, usuarios.DIRETORIA, None, visao, visao, **na_empresa)
        if visao == VISAO_TI:
            return Escopo(u, usuarios.ADMIN, None, visao, visao, **na_empresa)
        return Escopo(u, usuarios.GESTOR, visao, visao, visao, **na_empresa)
    if u["papel"] == usuarios.GESTOR:
        return Escopo(u, u["papel"], u["area"], u["area"] or "", u["nome"], **na_empresa)
    rotulo = {usuarios.DIRETORIA: VISAO_DIRETORIA, usuarios.REGULATORIO: "Regulatório (todos os ativos)",
              usuarios.ADMIN: VISAO_TI}[u["papel"]]
    return Escopo(u, u["papel"], None, rotulo, u["nome"], **na_empresa)


def areas_da_empresa(conn, empresa_id: int | None) -> list[str]:
    """Áreas que respondem por algum ativo da empresa ou por alguma obrigação de um ativo dela."""
    if empresa_id is None:
        return []
    ativos = db.ativos(conn, empresa_id)
    ids = {a["id"] for a in ativos}
    return sorted({a["responsavel"] for a in ativos if a["responsavel"]}
                  | {v for (aid, _), v in db.responsaveis(conn).items() if aid in ids})


def empresa_visivel(conn, e: Escopo, empresa_id: int) -> dict:
    """A empresa, se a sessão pode vê-la. 404 também para a de outra cliente: não revela que existe."""
    r = conn.execute("SELECT * FROM empresa WHERE id = ?", (empresa_id,)).fetchone()
    if r is None or not e.ve_empresa(r["id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"empresa {empresa_id} não existe")
    return dict(r)


def escopo(request: Request, conn=Depends(conexao)) -> Escopo:
    cfg: Config = request.app.state.cfg
    autorizacao = request.headers.get("authorization", "")
    if cfg.token_servico and autorizacao.startswith("Bearer "):
        if hmac.compare_digest(autorizacao[7:].strip(), cfg.token_servico):
            u = _conta_servico(conn)
            request.state.usuario = u["email"]
            request.state.empresa = None
            return Escopo(u, u["papel"], None, "serviço", u["nome"], plataforma=True)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token de serviço inválido")
    token = request.cookies.get(COOKIE_SESSAO)
    sessao = _sessao(conn, token) if token else None
    if sessao is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "entre na torre para continuar")
    if request.method in _ESCRITA:
        enviado = request.headers.get(CABECALHO_CSRF, "")
        esperado = request.cookies.get(COOKIE_CSRF, "")
        if not enviado or not hmac.compare_digest(enviado, esperado):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "falta o cabeçalho X-CSRF-Token")
    r = conn.execute("SELECT * FROM usuario WHERE id = ?", (sessao["usuario_id"],)).fetchone()
    if r is None or not r["ativa"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "conta desativada")
    u = {k: r[k] for k in r.keys() if k != "senha"}
    request.state.usuario = u["email"]
    request.state.sessao = sessao["token_hash"]
    e = escopo_da_conta(conn, u, sessao["visao"])
    request.state.empresa = e.empresa     # a auditoria grava de qual cliente é a ação
    return e


def regulatorio(e: Escopo = Depends(escopo)) -> Escopo:
    """Dado regulatório: todo mundo menos a TI."""
    if e.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "a TI administra contas e não vê dado regulatório")
    return e


def decide_normas(e: Escopo = Depends(regulatorio)) -> Escopo:
    if not e.ve_tudo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "só Regulatório e Diretoria decidem mudanças de norma")
    return e


def plataforma(e: Escopo = Depends(regulatorio)) -> Escopo:
    """Trabalho interno da Mitra (a fila de normas candidatas): a cliente recebe 403."""
    if not e.plataforma:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "isto é trabalho da curadoria da Mitra (plataforma)")
    return e


def curadoria(e: Escopo = Depends(decide_normas)) -> Escopo:
    """O que muda o catálogo de todas as clientes (propor mudança de norma, importar empresa)."""
    if not e.plataforma:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "só a curadoria da Mitra (plataforma) mexe no que vale para todas as empresas")
    return e


def da_empresa(e: Escopo = Depends(regulatorio)) -> Escopo:
    """Escrita nos dados operacionais de uma cliente: só a própria empresa. A plataforma só lê."""
    if e.so_leitura:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"{SO_LEITURA}: quem registra entrega, comenta e corrige o cadastro é a própria empresa")
    return e


def diretoria(e: Escopo = Depends(da_empresa)) -> Escopo:
    if e.papel != usuarios.DIRETORIA:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "só a Diretoria decide qual área responde por um ativo")
    return e


def ti(e: Escopo = Depends(escopo)) -> Escopo:
    if not e.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "só a TI administra contas")
    return e
