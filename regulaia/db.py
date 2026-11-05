"""Camada de dados da RegulaIA (SQLite).

Toda leitura e escrita passa por aqui, para que trocar SQLite por Postgres
no futuro mexa só neste arquivo.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from . import agenda as agenda_, regras

SCHEMA = Path(__file__).with_name("schema.sql")
ROOT = Path(__file__).resolve().parent.parent
DB_PADRAO = ROOT / "data" / "regulaia.db"

# Campos de uma versão que uma mudança regulatória pode alterar.
CAMPOS_VERSAO = (
    "titulo", "artigo", "aplica_se_a", "regra", "periodicidade", "agenda", "prazo",
    "vigencia_desde", "vigencia_ate", "responsavel", "evidencia",
)


class ErroCadastro(ValueError):
    pass


def conectar(caminho: str | Path = DB_PADRAO) -> sqlite3.Connection:
    """Abre (ou cria) o banco e aplica o esquema. Use ':memory:' nos testes."""
    if caminho != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: a interface (Streamlit) usa a conexão em outra thread
    conn = sqlite3.connect(caminho, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


@contextmanager
def sem_sincronizar(conn):
    """Para montar um banco que se recria do zero: sem esperar o disco a cada commit
    (2,7 s -> ~1,3 s na demo). Se a máquina cair no meio, é só montar de novo."""
    antes = conn.execute("PRAGMA synchronous").fetchone()[0]
    conn.execute("PRAGMA synchronous = OFF")
    try:
        yield conn
    finally:
        conn.execute(f"PRAGMA synchronous = {int(antes)}")


def limpar(conn) -> None:
    """Apaga todos os dados (menos o cache de IA), mantendo o arquivo e as conexões abertas."""
    with conn:
        for tabela in ("acionamento", "evidencia", "obrigacao_versao", "obrigacao", "ato", "ativo", "empresa"):
            conn.execute(f"DELETE FROM {tabela}")


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
    with conn:
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
    Opcionais: agenda (padrão "evento"), vigencia_ate, area, norma, tipo_ativo, trecho.
    """
    n = 0
    with open(caminho, encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            regras.validar(linha["regra"])
            agenda = (linha.get("agenda") or "evento").strip()
            agenda_.validar(agenda)
            with conn:
                ob_id = conn.execute(
                    "INSERT INTO obrigacao (codigo, tipo_ativo, norma, area) VALUES (?, ?, ?, ?)",
                    (linha["id"], linha.get("tipo_ativo") or tipo_ativo,
                     linha.get("norma") or norma, linha.get("area") or None),
                ).lastrowid
                conn.execute(
                    "INSERT INTO obrigacao_versao (obrigacao_id, versao, titulo, artigo, "
                    "aplica_se_a, regra, periodicidade, agenda, prazo, vigencia_desde, vigencia_ate, "
                    "responsavel, evidencia, fonte, trecho, status, decidida_por, decidida_em) "
                    "VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'vigente', 'carga inicial', datetime('now'))",
                    (ob_id, linha["obrigacao"], linha["artigo"], linha["aplica_se_a"],
                     linha["regra"], linha["periodicidade"], agenda, linha["prazo"],
                     linha["vigencia_desde"] or None, linha.get("vigencia_ate") or None,
                     linha["responsavel_ficticio"], linha["evidencia"], linha["fonte"],
                     linha.get("trecho") or None),
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
    """Todas as versões de uma obrigação, da primeira à mais nova, com o título do ato que a originou."""
    rows = conn.execute(
        "SELECT v.*, o.codigo, a.titulo AS ato FROM obrigacao_versao v "
        "JOIN obrigacao o ON o.id = v.obrigacao_id LEFT JOIN ato a ON a.id = v.ato_id "
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
    if "agenda" in mudancas:
        agenda_.validar(mudancas["agenda"])

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


# ------------------------------------------------------------------ evidência


def registrar_evidencia(conn, ativo_id: int, codigo: str, periodo: str, *,
                        arquivo: str | None = None, recebida_em: str | None = None,
                        extraido: dict | None = None) -> int:
    """Grava a comprovação de um período (idempotente por ativo + obrigação + período)."""
    ob = _obrigacao_id(conn, codigo)
    with conn:
        conn.execute(
            "INSERT INTO evidencia (ativo_id, obrigacao_id, periodo, arquivo, recebida_em, extraido) "
            "VALUES (?, ?, ?, ?, COALESCE(?, datetime('now')), ?) "
            "ON CONFLICT(ativo_id, obrigacao_id, periodo) DO UPDATE SET arquivo = excluded.arquivo",
            (ativo_id, ob, periodo, arquivo, recebida_em,
             json.dumps(extraido, ensure_ascii=False) if extraido else None),
        )
    return conn.execute(
        "SELECT id FROM evidencia WHERE ativo_id = ? AND obrigacao_id = ? AND periodo = ?",
        (ativo_id, ob, periodo),
    ).fetchone()["id"]


def evidencias_do_ativo(conn, ativo_id: int, limite: int = 10) -> list[dict]:
    """As evidências mais recentes de um ativo (as que chegaram por último primeiro), com o
    que o leitor extraiu do documento, para responder 'o que comprova isto?'."""
    rows = conn.execute(
        "SELECT e.id, o.codigo, e.periodo, e.arquivo, e.recebida_em, e.extraido FROM evidencia e "
        "JOIN obrigacao o ON o.id = e.obrigacao_id WHERE e.ativo_id = ? ORDER BY e.id DESC LIMIT ?",
        (ativo_id, limite),
    ).fetchall()
    return [dict(r) | {"extraido": json.loads(r["extraido"]) if r["extraido"] else None} for r in rows]


def acionar(conn, ativo_id: int, codigo: str, dia: str, prazo: str, motivo: str,
            origem: str | None = None) -> None:
    """Abre uma obrigação por evento (idempotente por ativo + obrigação + dia)."""
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO acionamento (ativo_id, obrigacao_id, dia, prazo, motivo, origem) "
            "VALUES (?, ?, ?, ?, ?, ?)", (ativo_id, _obrigacao_id(conn, codigo), dia, prazo, motivo, origem))


def encerrar_acionamentos(conn, ativo_id: int, codigo: str, dia: str) -> int:
    """A evidência da obrigação acionada, feita em `dia`, encerra o que foi aberto até esse dia."""
    with conn:
        return conn.execute(
            "UPDATE acionamento SET encerrado_em = ? WHERE ativo_id = ? AND obrigacao_id = ? "
            "AND dia <= ? AND encerrado_em IS NULL", (dia, ativo_id, _obrigacao_id(conn, codigo), dia)).rowcount


def acionamentos_abertos(conn, em: str) -> dict[tuple[int, str], list[dict]]:
    """{(ativo_id, código): [acionamentos]} abertos no dia `em` (já acionados e ainda não encerrados)."""
    out: dict[tuple[int, str], list[dict]] = {}
    for r in conn.execute(
        "SELECT a.*, o.codigo FROM acionamento a JOIN obrigacao o ON o.id = a.obrigacao_id "
        "WHERE a.dia <= ? AND (a.encerrado_em IS NULL OR a.encerrado_em > ?) ORDER BY a.dia", (em, em)):
        out.setdefault((r["ativo_id"], r["codigo"]), []).append(dict(r))
    return out


def evidencias(conn, ativo_id: int, codigo: str) -> list[str]:
    """Períodos já comprovados, em ordem."""
    return [r["periodo"] for r in conn.execute(
        "SELECT e.periodo FROM evidencia e JOIN obrigacao o ON o.id = e.obrigacao_id "
        "WHERE e.ativo_id = ? AND o.codigo = ? ORDER BY e.periodo", (ativo_id, codigo),
    )]


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
    # uma consulta só: vigente e pendente de todas as obrigações do tipo do ativo
    versoes: dict[str, dict[str, dict]] = {}
    for r in conn.execute(
        "SELECT v.*, o.codigo FROM obrigacao_versao v JOIN obrigacao o ON o.id = v.obrigacao_id "
        "WHERE o.tipo_ativo = ? AND v.status IN ('vigente', 'pendente')", (a["tipo"],)
    ):
        versoes.setdefault(r["codigo"], {})[r["status"]] = dict(r)
    out = []
    for codigo in sorted(versoes):
        vig = versoes[codigo].get("vigente")
        pen = versoes[codigo].get("pendente")
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
