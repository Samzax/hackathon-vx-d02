"""Camada de dados da RegulaIA (SQLite).

Toda leitura e escrita passa por aqui, para que trocar SQLite por Postgres
no futuro mexa só neste arquivo.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import regras

SCHEMA = Path(__file__).with_name("schema.sql")
ROOT = Path(__file__).resolve().parent.parent
DB_PADRAO = ROOT / "data" / "regulaia.db"

# Campos de uma versão que uma mudança regulatória pode alterar.
CAMPOS_VERSAO = (
    "titulo", "artigo", "aplica_se_a", "regra", "periodicidade", "prazo",
    "vigencia_desde", "vigencia_ate", "responsavel", "evidencia",
)


class ErroCadastro(ValueError):
    pass


def conectar(caminho: str | Path = DB_PADRAO) -> sqlite3.Connection:
    """Abre (ou cria) o banco e aplica o esquema. Use ':memory:' nos testes."""
    if caminho != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


# --------------------------------------------------------------- empresa e ativo


def criar_empresa(conn, nome: str, ficticia: bool = True) -> int:
    cur = conn.execute(
        "INSERT INTO empresa (nome, ficticia) VALUES (?, ?)", (nome, int(ficticia))
    )
    return cur.lastrowid


def criar_ativo(conn, empresa_id: int, tipo: str, codigo: str, nome: str,
                atributos: dict, responsavel: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO ativo (empresa_id, tipo, codigo, nome, atributos, responsavel) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (empresa_id, tipo, codigo, nome, json.dumps(atributos, ensure_ascii=False), responsavel),
    )
    return cur.lastrowid


def ativos(conn, empresa_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM ativo WHERE empresa_id = ? ORDER BY codigo", (empresa_id,)
    ).fetchall()
    return [dict(r) | {"atributos": json.loads(r["atributos"])} for r in rows]


# -------------------------------------------------------------------------- ato


def registrar_ato(conn, fonte: str, identificador: str, titulo: str, *,
                  ementa: str | None = None, publicado_em: str | None = None,
                  url: str | None = None, texto: str | None = None) -> int:
    """Grava o ato uma vez só; chamadas repetidas devolvem o mesmo id."""
    sha = hashlib.sha256(texto.encode("utf-8")).hexdigest() if texto else None
    conn.execute(
        "INSERT INTO ato (fonte, identificador, titulo, ementa, publicado_em, url, texto, sha256) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(identificador) DO NOTHING",
        (fonte, identificador, titulo, ementa, publicado_em, url, texto, sha),
    )
    return conn.execute(
        "SELECT id FROM ato WHERE identificador = ?", (identificador,)
    ).fetchone()["id"]


# -------------------------------------------------------------------- obrigação


def carregar_obrigacoes_csv(conn, caminho: str | Path, tipo_ativo: str = "barragem",
                            norma: str | None = None) -> int:
    """Carrega um cadastro: cada linha vira a versão 1, já vigente.

    Colunas obrigatórias: id, artigo, obrigacao, aplica_se_a, regra, periodicidade,
    prazo, vigencia_desde, responsavel_ficticio, evidencia, fonte.
    Opcionais: vigencia_ate, area, norma, tipo_ativo.
    """
    n = 0
    with open(caminho, encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            regras.validar(linha["regra"])
            with conn:
                ob_id = conn.execute(
                    "INSERT INTO obrigacao (codigo, tipo_ativo, norma, area) VALUES (?, ?, ?, ?)",
                    (linha["id"], linha.get("tipo_ativo") or tipo_ativo,
                     linha.get("norma") or norma, linha.get("area") or None),
                ).lastrowid
                conn.execute(
                    "INSERT INTO obrigacao_versao (obrigacao_id, versao, titulo, artigo, "
                    "aplica_se_a, regra, periodicidade, prazo, vigencia_desde, vigencia_ate, "
                    "responsavel, evidencia, fonte, status, decidida_por, decidida_em) "
                    "VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'vigente', 'carga inicial', datetime('now'))",
                    (ob_id, linha["obrigacao"], linha["artigo"], linha["aplica_se_a"],
                     linha["regra"], linha["periodicidade"], linha["prazo"],
                     linha["vigencia_desde"] or None, linha.get("vigencia_ate") or None,
                     linha["responsavel_ficticio"], linha["evidencia"], linha["fonte"]),
                )
            n += 1
    return n


def vale_em(versao: dict, dia: str) -> bool:
    """A versão vale no dia (AAAA-MM-DD)? Janela fechada nas duas pontas."""
    desde, ate = versao.get("vigencia_desde"), versao.get("vigencia_ate")
    return (not desde or desde <= dia) and (not ate or dia <= ate)


def _obrigacao_id(conn, codigo: str) -> int:
    row = conn.execute("SELECT id FROM obrigacao WHERE codigo = ?", (codigo,)).fetchone()
    if row is None:
        raise ErroCadastro(f"obrigação {codigo} não existe")
    return row["id"]


def versao(conn, codigo: str, status: str = "vigente") -> dict | None:
    row = conn.execute(
        "SELECT v.*, o.codigo FROM obrigacao_versao v JOIN obrigacao o ON o.id = v.obrigacao_id "
        "WHERE o.codigo = ? AND v.status = ?",
        (codigo, status),
    ).fetchone()
    return dict(row) if row else None


def historico(conn, codigo: str) -> list[dict]:
    rows = conn.execute(
        "SELECT v.*, o.codigo FROM obrigacao_versao v JOIN obrigacao o ON o.id = v.obrigacao_id "
        "WHERE o.codigo = ? ORDER BY v.versao",
        (codigo,),
    ).fetchall()
    return [dict(r) for r in rows]


def propor_versao(conn, codigo: str, mudancas: dict, *, ato_id: int | None,
                  trecho: str | None, fonte: str | None = None) -> int:
    """Cria uma versão pendente: cópia da vigente com as mudanças aplicadas.

    Nada muda para a operação até alguém aprovar (decidir()).
    """
    invalidos = set(mudancas) - set(CAMPOS_VERSAO)
    if invalidos:
        raise ErroCadastro(f"campos que não podem mudar: {sorted(invalidos)}")
    atual = versao(conn, codigo)
    if atual is None:
        raise ErroCadastro(f"{codigo} não tem versão vigente")
    if versao(conn, codigo, "pendente") is not None:
        raise ErroCadastro(f"{codigo} já tem uma mudança aguardando decisão")
    if all(atual[c] == v for c, v in mudancas.items()):
        raise ErroCadastro(f"a mudança proposta para {codigo} não altera nada")
    if "regra" in mudancas:
        regras.validar(mudancas["regra"])

    nova = {c: atual[c] for c in CAMPOS_VERSAO} | mudancas
    proxima = conn.execute(
        "SELECT MAX(versao) + 1 FROM obrigacao_versao WHERE obrigacao_id = ?",
        (atual["obrigacao_id"],),
    ).fetchone()[0]
    with conn:
        cur = conn.execute(
            f"INSERT INTO obrigacao_versao (obrigacao_id, versao, {', '.join(CAMPOS_VERSAO)}, "
            "fonte, ato_id, trecho, status) "
            f"VALUES (?, ?, {', '.join('?' * len(CAMPOS_VERSAO))}, ?, ?, ?, 'pendente')",
            (atual["obrigacao_id"], proxima, *(nova[c] for c in CAMPOS_VERSAO),
             fonte, ato_id, trecho),
        )
    return cur.lastrowid


def decidir(conn, versao_id: int, aprovar: bool, por: str) -> None:
    """Aprova (a pendente vira vigente; a antiga, substituída) ou rejeita."""
    row = conn.execute(
        "SELECT obrigacao_id, status FROM obrigacao_versao WHERE id = ?", (versao_id,)
    ).fetchone()
    if row is None or row["status"] != "pendente":
        raise ErroCadastro(f"versão {versao_id} não está pendente")
    with conn:
        if aprovar:
            conn.execute(
                "UPDATE obrigacao_versao SET status = 'substituida' "
                "WHERE obrigacao_id = ? AND status = 'vigente'",
                (row["obrigacao_id"],),
            )
        conn.execute(
            "UPDATE obrigacao_versao SET status = ?, decidida_por = ?, decidida_em = datetime('now') "
            "WHERE id = ?",
            ("vigente" if aprovar else "rejeitada", por, versao_id),
        )


def diferencas(antes: dict, depois: dict) -> dict[str, tuple]:
    """Campos que mudaram entre duas versões: {campo: (antes, depois)}."""
    return {c: (antes[c], depois[c]) for c in CAMPOS_VERSAO if antes[c] != depois[c]}


# ------------------------------------------------------ obrigações de um ativo


@dataclass
class ObrigacaoDoAtivo:
    codigo: str
    vigente: dict
    pendente: dict | None          # mudança aguardando aprovação que afeta este ativo
    dados_faltando: list[str]      # atributos do ativo que a regra usa e não estão preenchidos


def obrigacoes_do_ativo(conn, ativo_id: int, em: str | None = None) -> list[ObrigacaoDoAtivo]:
    """Obrigações que se aplicam ao ativo. Com `em` (AAAA-MM-DD), só as que valem nesse dia
    pela versão vigente ou pela pendente."""
    a = conn.execute("SELECT tipo, atributos FROM ativo WHERE id = ?", (ativo_id,)).fetchone()
    if a is None:
        raise ErroCadastro(f"ativo {ativo_id} não existe")
    attrs = json.loads(a["atributos"])
    codigos = [r["codigo"] for r in conn.execute(
        "SELECT codigo FROM obrigacao WHERE tipo_ativo = ? ORDER BY codigo", (a["tipo"],)
    )]
    out = []
    for codigo in codigos:
        vig = versao(conn, codigo)
        pen = versao(conn, codigo, "pendente")
        if vig is None:
            continue
        if em and not (vale_em(vig, em) or (pen is not None and vale_em(pen, em))):
            continue
        aplica_vig = regras.aplica(vig["regra"], attrs)
        aplica_pen = pen is not None and regras.aplica(pen["regra"], attrs)
        falta = regras.faltantes(vig["regra"], attrs)
        if aplica_vig or aplica_pen or falta:
            out.append(ObrigacaoDoAtivo(
                codigo, vig, pen if aplica_pen or (pen and aplica_vig) else None, falta,
            ))
    return out
