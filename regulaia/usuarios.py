"""Contas de quem usa a torre: entrar, papel e área.

Papéis:
- admin (TI): cria, edita e desativa contas. Não vê a torre: dado regulatório não é assunto da TI.
- diretoria: vê todos os ativos e decide qual área responde por cada um.
- regulatorio: vê todos os ativos (é quem aprova as mudanças de norma).
- gestor: vê os ativos e as obrigações da sua área.

A área é o mesmo texto do "responsável" do cadastro ("Gerência de Geotecnia"): o filtro da torre
continua o de sempre, só que agora quem diz a área é a conta, e não um seletor livre.

Conta de teste: entra com o seletor "Quem está olhando" e troca de visão à vontade (demo e pitch).
A conta da demo não tem senha: só entra pelo botão "Entrar na demo".

Senha: scrypt (biblioteca padrão) com sal próprio por conta; a comparação é em tempo constante.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "usuarios_demo.json"

ADMIN, DIRETORIA, REGULATORIO, GESTOR = "admin", "diretoria", "regulatorio", "gestor"
PAPEIS = {ADMIN: "TI (administra contas)", DIRETORIA: "Diretoria", REGULATORIO: "Regulatório", GESTOR: "Gestor de área"}
VE_TUDO = (DIRETORIA, REGULATORIO)
SENHA_MINIMA = 8
_N, _R, _P = 2 ** 14, 8, 1     # scrypt: ~50 ms por senha, 16 MB de memória


class ErroConta(ValueError):
    """Pedido que deixaria as contas num estado ruim (sem TI, gestor sem área, e-mail repetido...)."""


# --------------------------------------------------------------------- senha


def hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(senha.encode("utf-8"), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${sal.hex()}${h.hex()}"


def confere_senha(senha: str, guardado: str | None) -> bool:
    if not guardado or not senha:
        return False
    try:
        _, sal, h = guardado.split("$")
        calc = hashlib.scrypt(senha.encode("utf-8"), salt=bytes.fromhex(sal), n=_N, r=_R, p=_P, dklen=32)
    except ValueError:
        return False
    return hmac.compare_digest(calc.hex(), h)


# --------------------------------------------------------------------- contas


def _email(email: str) -> str:
    e = (email or "").strip().lower()
    if "@" not in e or e.startswith("@") or e.endswith("@"):
        raise ErroConta("e-mail inválido")
    return e


def _sem_senha_dict(r) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    d["tem_senha"] = bool(d.pop("senha"))
    d["teste"], d["ativa"] = bool(d["teste"]), bool(d["ativa"])
    d["plataforma"] = bool(d.get("plataforma"))
    return d


def _validar(papel: str, area: str | None, senha: str | None) -> None:
    if papel not in PAPEIS:
        raise ErroConta(f"papel desconhecido: {papel}")
    if papel == GESTOR and not (area or "").strip():
        raise ErroConta("gestor precisa de uma área: é ela que diz quais ativos ele vê")
    if senha is not None and len(senha) < SENHA_MINIMA:
        raise ErroConta(f"a senha precisa de pelo menos {SENHA_MINIMA} caracteres")


def criar(conn, email: str, nome: str, papel: str, *, area: str | None = None, senha: str | None = None,
          teste: bool = False, por: str | None = None, empresa: str | None = None,
          plataforma: bool = False) -> int:
    """Conta nova. Sem senha, só entra pelo botão da demo (vale para conta de teste)."""
    e, nome = _email(email), (nome or "").strip()
    if not nome:
        raise ErroConta("a conta precisa de um nome")
    _validar(papel, area, senha)
    if senha is None and not teste:
        raise ErroConta("conta normal precisa de senha")
    if conn.execute("SELECT 1 FROM usuario WHERE email = ?", (e,)).fetchone():
        raise ErroConta(f"já existe uma conta com o e-mail {e}")
    with conn:
        cur = conn.execute(
            "INSERT INTO usuario (email, nome, papel, area, senha, teste, criado_por, empresa, plataforma) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (e, nome, papel, (area or "").strip() or None, hash_senha(senha) if senha else None, int(teste), por,
             (empresa or "").strip() or None, int(plataforma)))
    return cur.lastrowid


def por_email(conn, email: str) -> dict | None:
    return _sem_senha_dict(conn.execute("SELECT * FROM usuario WHERE email = ?",
                                        ((email or "").strip().lower(),)).fetchone())


def listar(conn, empresa: str | None = None) -> list[dict]:
    """Ativas primeiro; dentro delas, TI, Diretoria, Regulatório, gestores; depois por nome.
    Com `empresa`, só as contas daquela empresa (a TI de uma cliente não vê as contas de outra)."""
    ordem = {p: i for i, p in enumerate(PAPEIS)}
    if empresa is None:
        rows = conn.execute("SELECT * FROM usuario")
    else:
        rows = conn.execute("SELECT * FROM usuario WHERE empresa = ?", (empresa,))
    contas = [_sem_senha_dict(r) for r in rows]
    return sorted(contas, key=lambda u: (not u["ativa"], ordem[u["papel"]], u["nome"].lower()))


def _admins_ativos(conn, exceto: int | None = None, empresa: str | None = None) -> int:
    """Contas de TI ativas da mesma empresa (cada cliente precisa da sua)."""
    return conn.execute("SELECT COUNT(*) FROM usuario WHERE papel = ? AND ativa = 1 AND teste = 0 "
                        "AND id IS DISTINCT FROM ? AND empresa IS NOT DISTINCT FROM ?",
                        (ADMIN, exceto, empresa)).fetchone()[0]


def editar(conn, usuario_id: int, *, nome: str | None = None, papel: str | None = None, area: str | None = None,
           teste: bool | None = None, ativa: bool | None = None) -> dict:
    """Muda o que vier preenchido. Não deixa a empresa sem nenhuma conta de TI ativa."""
    r = conn.execute("SELECT * FROM usuario WHERE id = ?", (usuario_id,)).fetchone()
    if r is None:
        raise ErroConta(f"conta {usuario_id} não existe")
    novo = dict(r) | {k: v for k, v in {"nome": nome, "papel": papel, "teste": teste, "ativa": ativa}.items()
                      if v is not None}
    if area is not None:
        novo["area"] = area.strip() or None
    if not (novo["nome"] or "").strip():
        raise ErroConta("a conta precisa de um nome")
    _validar(novo["papel"], novo["area"], None)
    era_admin = r["papel"] == ADMIN and r["ativa"] and not r["teste"]
    continua_admin = novo["papel"] == ADMIN and novo["ativa"] and not novo["teste"]
    if era_admin and not continua_admin and not _admins_ativos(conn, exceto=usuario_id, empresa=r["empresa"]):
        raise ErroConta("esta é a única conta de TI ativa: crie outra antes de mudar ou desativar esta")
    if not novo["senha"] and not novo["teste"]:
        raise ErroConta("conta sem senha só pode ser de teste: defina uma senha antes")
    with conn:
        conn.execute("UPDATE usuario SET nome = ?, papel = ?, area = ?, teste = ?, ativa = ? WHERE id = ?",
                     (novo["nome"].strip(), novo["papel"], novo["area"], int(novo["teste"]), int(novo["ativa"]),
                      usuario_id))
    return _sem_senha_dict(conn.execute("SELECT * FROM usuario WHERE id = ?", (usuario_id,)).fetchone())


def definir_senha(conn, usuario_id: int, senha: str) -> None:
    _validar(GESTOR, "x", senha)
    with conn:
        n = conn.execute("UPDATE usuario SET senha = ? WHERE id = ?", (hash_senha(senha), usuario_id)).rowcount
    if not n:
        raise ErroConta(f"conta {usuario_id} não existe")


def autenticar(conn, email: str, senha: str) -> dict | None:
    """A conta, se e-mail e senha conferem e ela está ativa; senão None (sem dizer qual dos dois errou)."""
    try:
        e = _email(email)
    except ErroConta:
        return None
    r = conn.execute("SELECT * FROM usuario WHERE email = ?", (e,)).fetchone()
    if r is None:
        hash_senha(senha or "x")       # mesmo tempo de resposta para e-mail que não existe
        return None
    if not r["ativa"] or not confere_senha(senha, r["senha"]):
        return None
    registrar_acesso(conn, r["id"])
    return por_email(conn, e)


def registrar_acesso(conn, usuario_id: int) -> None:
    with conn:
        conn.execute("UPDATE usuario SET ultimo_acesso = ? WHERE id = ?", (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), usuario_id))


def conta_demo(conn) -> dict | None:
    """A conta de teste sem senha que o botão "Entrar na demo" usa (a primeira, se houver mais)."""
    r = conn.execute("SELECT * FROM usuario WHERE teste = 1 AND senha IS NULL AND ativa = 1 ORDER BY id").fetchone()
    return _sem_senha_dict(r)


def areas(conn, empresa: str | None = None) -> list[str]:
    """Áreas conhecidas: as dos gestores ativos e as que já respondem por algum ativo ou obrigação.
    Com `empresa`, só as daquela empresa: "Gerência de Geotecnia" de uma cliente não é a de outra."""
    if empresa is None:
        nomes = {r[0] for r in conn.execute(
            "SELECT area FROM usuario WHERE ativa = 1 AND area IS NOT NULL "
            "UNION SELECT responsavel FROM ativo WHERE responsavel IS NOT NULL "
            "UNION SELECT responsavel FROM responsavel_obrigacao")}
    else:
        nomes = {r[0] for r in conn.execute(
            "SELECT area FROM usuario WHERE ativa = 1 AND area IS NOT NULL AND empresa = ? "
            "UNION SELECT a.responsavel FROM ativo a JOIN empresa e ON e.id = a.empresa_id "
            "WHERE a.responsavel IS NOT NULL AND e.nome = ? "
            "UNION SELECT ro.responsavel FROM responsavel_obrigacao ro JOIN ativo a ON a.id = ro.ativo_id "
            "JOIN empresa e ON e.id = a.empresa_id WHERE e.nome = ?", (empresa, empresa, empresa))}
    return sorted(n for n in nomes if n and n.strip())


def ve_tudo(usuario: dict) -> bool:
    return usuario["papel"] in VE_TUDO


# --------------------------------------------------------------------- demo


def semear(conn, origem: Path = SEED, com_senha_apenas: bool = False) -> int:
    """Contas da demo (fictícias). Não sobrescreve conta que já existe: o que a TI mudou fica.
    A senha das contas da demo vem do arquivo, ou de REGULAIA_SENHA_DEMO no link público.
    `com_senha_apenas` (produção, sem demo): a conta de teste sem senha, que entra por /auth/demo
    sem credencial e troca para a visão da curadoria, fica de fora."""
    if not origem.exists():
        return 0
    dados = json.loads(origem.read_text(encoding="utf-8"))
    senha = os.environ.get("REGULAIA_SENHA_DEMO") or dados.get("senha")
    n = 0
    for c in dados["contas"]:
        if com_senha_apenas and c.get("sem_senha"):
            continue
        empresa = None if c.get("plataforma") else c.get("empresa", dados.get("empresa"))
        if existente := por_email(conn, c["email"]):
            if existente.get("empresa") is None and empresa and not existente.get("plataforma"):
                with conn:      # banco de antes do multiempresa: a conta da demo ganha a empresa dela
                    conn.execute("UPDATE usuario SET empresa = ? WHERE id = ?", (empresa, existente["id"]))
            continue
        criar(conn, c["email"], c["nome"], c["papel"], area=c.get("area"), teste=c.get("teste", False),
              senha=None if c.get("sem_senha") else senha, por="demo", empresa=empresa,
              plataforma=bool(c.get("plataforma")))
        n += 1
    return n
