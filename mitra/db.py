"""Camada de dados da Mitra: SQLite (testes, demo offline) ou Postgres (API, AWS RDS).

Toda leitura e escrita passa por aqui, com SQL portátil. As diferenças entre os dois
bancos ficam em banco.py.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from . import agenda as agenda_, banco, regras

SCHEMA = Path(__file__).with_name("schema.sql")
ROOT = Path(__file__).resolve().parent.parent
DB_PADRAO = ROOT / "data" / "mitra.db"

# Campos de uma versão que uma mudança regulatória pode alterar.
CAMPOS_VERSAO = (
    "titulo", "artigo", "aplica_se_a", "regra", "periodicidade", "agenda", "prazo",
    "vigencia_desde", "vigencia_ate", "responsavel", "evidencia",
)


class ErroCadastro(ValueError):
    pass


def agora() -> str:
    """AAAA-MM-DD HH:MM:SS em UTC, o mesmo formato do datetime('now') do SQLite."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def conectar(caminho: str | Path = DB_PADRAO):
    """Abre (ou cria) o banco e aplica o esquema. Use ':memory:' nos testes.

    `caminho` pode ser um arquivo SQLite ou uma URL `postgresql://...` (API e AWS RDS);
    sem argumento, vale MITRA_DATABASE_URL se estiver definida."""
    if caminho is DB_PADRAO and os.environ.get("MITRA_DATABASE_URL"):
        caminho = os.environ["MITRA_DATABASE_URL"]
    if banco.eh_url_postgres(caminho):
        return banco.ConexaoPostgres(caminho)
    if caminho != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: a interface (Streamlit) usa a conexão em outra thread
    conn = sqlite3.connect(caminho, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    # bancos criados antes da coluna de correção
    if "correcao" not in {r["name"] for r in conn.execute("PRAGMA table_info(obrigacao_versao)")}:
        conn.execute("ALTER TABLE obrigacao_versao ADD COLUMN correcao TEXT")
    # colunas da importação do SIGBM (empresa real): ficam aqui para bancos antigos e novos
    colunas = {r["name"] for r in conn.execute("PRAGMA table_info(empresa)")}
    for col in ("monitorado_desde", "origem"):
        if col not in colunas:
            conn.execute(f"ALTER TABLE empresa ADD COLUMN {col} TEXT")
    # multiempresa: bancos criados antes de conta e obrigação terem empresa
    # e instanciação: a unidade (operação) do ativo e a senha provisória da conta
    for tabela, col, tipo in (("obrigacao", "empresa", "TEXT"), ("usuario", "empresa", "TEXT"),
                              ("usuario", "plataforma", "INTEGER NOT NULL DEFAULT 0"), ("auditoria", "empresa", "TEXT"),
                              ("ativo", "unidade", "TEXT"), ("usuario", "trocar_senha", "INTEGER NOT NULL DEFAULT 0"),
                              ("usuario", "unidades", "TEXT NOT NULL DEFAULT '[]'")):
        if col not in {r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})")}:
            conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}")
    if "setor" not in colunas:
        conn.execute("ALTER TABLE empresa ADD COLUMN setor TEXT NOT NULL DEFAULT 'mineracao'")
    _codigo_por_empresa(conn)
    return conn


def _codigo_por_empresa(conn) -> None:
    """Banco criado quando `obrigacao.codigo` era UNIQUE global: refaz a tabela sem esse UNIQUE (duas
    clientes têm cada uma a sua "LO-01"). No SQLite não há DROP CONSTRAINT: recria e copia."""
    autoindex = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'obrigacao' "
        "AND name LIKE 'sqlite_autoindex%'").fetchone()
    if autoindex is None:
        return
    conn.executescript("""
        PRAGMA foreign_keys = OFF;
        BEGIN;
        CREATE TABLE obrigacao_nova (
            id          INTEGER PRIMARY KEY,
            codigo      TEXT NOT NULL,
            tipo_ativo  TEXT NOT NULL,
            norma       TEXT,
            area        TEXT,
            empresa     TEXT
        );
        INSERT INTO obrigacao_nova SELECT id, codigo, tipo_ativo, norma, area, empresa FROM obrigacao;
        DROP TABLE obrigacao;
        ALTER TABLE obrigacao_nova RENAME TO obrigacao;
        CREATE UNIQUE INDEX IF NOT EXISTS obrigacao_empresa_codigo
            ON obrigacao (COALESCE(empresa, ''), codigo);
        COMMIT;
        PRAGMA foreign_keys = ON;
    """)


@contextmanager
def sem_sincronizar(conn):
    """Para montar um banco que se recria do zero: sem esperar o disco a cada commit
    (2,7 s -> ~1,3 s na demo). Se a máquina cair no meio, é só montar de novo."""
    if getattr(conn, "dialeto", "sqlite") != "sqlite":
        yield conn
        return
    antes = conn.execute("PRAGMA synchronous").fetchone()[0]
    conn.execute("PRAGMA synchronous = OFF")
    try:
        yield conn
    finally:
        conn.execute(f"PRAGMA synchronous = {int(antes)}")


def limpar(conn) -> None:
    """Apaga todos os dados (menos o cache de IA), mantendo o arquivo e as conexões abertas."""
    with conn:
        for tabela in ("evento", "responsavel_obrigacao", "acionamento", "evidencia", "obrigacao_versao", "obrigacao",
                       "ato", "instanciacao_evento", "instanciacao", "unidade", "ativo", "empresa"):
            conn.execute(f"DELETE FROM {tabela}")


# --------------------------------------------------------------- empresa e ativo


def criar_empresa(conn, nome: str, ficticia: bool = True, monitorado_desde: str | None = None,
                  origem: str | None = None, setor: str = "mineracao") -> int:
    """`monitorado_desde`: a partir de quando a torre cobra (o que venceu antes não vira atraso)."""
    cur = conn.execute(
        "INSERT INTO empresa (nome, ficticia, monitorado_desde, origem, setor) VALUES (?, ?, ?, ?, ?)",
        (nome, int(ficticia), monitorado_desde, origem, setor),
    )
    return cur.lastrowid


def empresas(conn) -> list[dict]:
    """Fictícias primeiro (a demo), depois as importadas, na ordem em que entraram."""
    return [dict(r) for r in conn.execute("SELECT * FROM empresa ORDER BY ficticia DESC, id")]


def atualizar_atributos(conn, ativo_id: int, novos: dict, por: str | None = None) -> dict:
    """Preenche ou corrige atributos de um ativo (ex.: o dado que faltava). Fica no histórico."""
    r = conn.execute("SELECT atributos FROM ativo WHERE id = ?", (ativo_id,)).fetchone()
    if r is None:
        raise ErroCadastro(f"ativo {ativo_id} não existe")
    atual = json.loads(r["atributos"])
    mudou = {k: v for k, v in novos.items() if atual.get(k) != v}
    if not mudou:
        return atual
    atual |= mudou
    with conn:
        conn.execute("UPDATE ativo SET atributos = ? WHERE id = ?",
                     (json.dumps(atual, ensure_ascii=False), ativo_id))
        conn.execute("INSERT INTO evento (ativo_id, tipo, texto, por) VALUES (?, 'cadastro', ?, ?)",
                     (ativo_id, "; ".join(f"{k} = {_legivel(v)}" for k, v in mudou.items()), por))
    return atual


def definir_responsavel(conn, ativo_id: int, area: str | None, por: str | None = None) -> bool:
    """Qual área responde pelo ativo (a Diretoria decide). Fica no histórico; True se mudou."""
    r = conn.execute("SELECT responsavel FROM ativo WHERE id = ?", (ativo_id,)).fetchone()
    if r is None:
        raise ErroCadastro(f"ativo {ativo_id} não existe")
    nova = (area or "").strip() or None
    if nova == r["responsavel"]:
        return False
    with conn:
        conn.execute("UPDATE ativo SET responsavel = ? WHERE id = ?", (nova, ativo_id))
        conn.execute("INSERT INTO evento (ativo_id, tipo, texto, por) VALUES (?, 'cadastro', ?, ?)",
                     (ativo_id, f"área responsável: {r['responsavel'] or 'ninguém'} → {nova or 'ninguém'}", por))
    return True


def _legivel(v) -> str:
    if isinstance(v, bool):
        return "sim" if v else "não"
    return str(v)


def criar_ativo(conn, empresa_id: int, tipo: str, codigo: str, nome: str,
                atributos: dict, responsavel: str | None = None, unidade: str | None = None) -> int:
    """`unidade`: a operação a que o ativo pertence (unidade.nome da mesma empresa)."""
    cur = conn.execute(
        "INSERT INTO ativo (empresa_id, tipo, codigo, nome, atributos, responsavel, unidade) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (empresa_id, tipo, codigo, nome, json.dumps(atributos, ensure_ascii=False), responsavel, unidade),
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
                            norma: str | None = None, empresa: str | None = None) -> int:
    """Carrega um cadastro: cada linha vira a versão 1, já vigente.

    Colunas obrigatórias: id, artigo, obrigacao, aplica_se_a, regra, periodicidade,
    prazo, vigencia_desde, responsavel_ficticio, evidencia, fonte.
    Opcionais: agenda (padrão "evento"), vigencia_ate, area, norma, tipo_ativo, trecho e empresa
    (obrigação própria de uma empresa cliente; vazio: norma pública, vale para todas).
    """
    n = 0
    with open(caminho, encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            regras.validar(linha["regra"])
            agenda = (linha.get("agenda") or "evento").strip()
            agenda_.validar(agenda)
            with conn:
                ob_id = conn.execute(
                    "INSERT INTO obrigacao (codigo, tipo_ativo, norma, area, empresa) VALUES (?, ?, ?, ?, ?)",
                    (linha["id"], linha.get("tipo_ativo") or tipo_ativo,
                     linha.get("norma") or norma, linha.get("area") or None,
                     (linha.get("empresa") or "").strip() or empresa),
                ).lastrowid
                conn.execute(
                    "INSERT INTO obrigacao_versao (obrigacao_id, versao, titulo, artigo, "
                    "aplica_se_a, regra, periodicidade, agenda, prazo, vigencia_desde, vigencia_ate, "
                    "responsavel, evidencia, fonte, trecho, status, decidida_por, decidida_em) "
                    "VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'vigente', 'carga inicial', ?)",
                    (ob_id, linha["obrigacao"], linha["artigo"], linha["aplica_se_a"],
                     linha["regra"], linha["periodicidade"], agenda, linha["prazo"],
                     linha["vigencia_desde"] or None, linha.get("vigencia_ate") or None,
                     linha["responsavel_ficticio"], linha["evidencia"], linha["fonte"],
                     linha.get("trecho") or None, agora()),
                )
            n += 1
    return n


def vale_em(versao: dict, dia: str) -> bool:
    """A versão vale no dia (AAAA-MM-DD)? Janela fechada nas duas pontas."""
    desde, ate = versao.get("vigencia_desde"), versao.get("vigencia_ate")
    return (not desde or desde <= dia) and (not ate or dia <= ate)


def ativo_por_codigo(conn, empresa_id: int, codigo: str) -> dict | None:
    """O código (B1, L1) só é único dentro da empresa: a busca sempre leva a empresa."""
    r = conn.execute("SELECT * FROM ativo WHERE empresa_id = ? AND codigo = ?", (empresa_id, codigo)).fetchone()
    return dict(r) if r else None


QUALQUER = "*qualquer empresa*"
"""Busca por código sem filtrar a empresa (radar e curadoria da plataforma). Como o código só é único
por empresa, a busca assim **erra** se o mesmo código existir em mais de uma dona, em vez de escolher
uma por acaso: quem chama passa a empresa, ou usa o id da obrigação."""


def _obrigacoes_com_codigo(conn, codigo: str, empresa: str | None) -> list[dict]:
    """As obrigações com esse código visíveis para `empresa` (as dela e as públicas), a dela primeiro.
    Com `QUALQUER`, todas as donas — e aí duas clientes com a mesma "LO-01" é ambiguidade, não escolha."""
    rows = [dict(r) for r in conn.execute(
        "SELECT id, codigo, empresa, norma, tipo_ativo, area FROM obrigacao WHERE codigo = ?", (codigo,))]
    if empresa == QUALQUER:
        return rows
    return sorted((r for r in rows if r["empresa"] in (None, empresa)), key=lambda r: r["empresa"] is None)


def obrigacao_por_codigo(conn, codigo: str, empresa: str | None = QUALQUER) -> dict:
    """A obrigação do código no escopo de `empresa` (a própria dela ou a norma pública)."""
    achadas = _obrigacoes_com_codigo(conn, codigo, empresa)
    if not achadas:
        raise ErroCadastro(f"obrigação {codigo} não existe")
    if len(achadas) > 1 and empresa == QUALQUER:
        donas = ", ".join(sorted(r["empresa"] or "norma pública" for r in achadas))
        raise ErroCadastro(f"o código {codigo} existe em mais de uma empresa ({donas}): diga de qual")
    return achadas[0]


def _obrigacao_id(conn, codigo: str, empresa: str | None = QUALQUER) -> int:
    return obrigacao_por_codigo(conn, codigo, empresa)["id"]


def _empresa_do_ativo(conn, ativo_id: int) -> str:
    """O nome da dona do ativo: é o escopo de toda busca de obrigação por código a partir do ativo
    (a condicionante de outra cliente nunca entra na evidência, no acionamento nem na atribuição)."""
    r = conn.execute("SELECT e.nome FROM ativo a JOIN empresa e ON e.id = a.empresa_id WHERE a.id = ?",
                     (ativo_id,)).fetchone()
    if r is None:
        raise ErroCadastro(f"ativo {ativo_id} não existe")
    return r["nome"]


def _uma(conn, codigo: str, empresa: str | None) -> dict | None:
    """Como `obrigacao_por_codigo`, mas código que não existe é None (não erro): quem pergunta "qual é a
    versão vigente de X?" aceita "nenhuma". Ambiguidade continua sendo erro."""
    achadas = _obrigacoes_com_codigo(conn, codigo, empresa)
    if len(achadas) > 1 and empresa == QUALQUER:
        donas = ", ".join(sorted(r["empresa"] or "norma pública" for r in achadas))
        raise ErroCadastro(f"o código {codigo} existe em mais de uma empresa ({donas}): diga de qual")
    return achadas[0] if achadas else None


def versao(conn, codigo: str, status: str = "vigente", empresa: str | None = QUALQUER) -> dict | None:
    ob = _uma(conn, codigo, empresa)
    if ob is None:
        return None
    row = conn.execute(
        "SELECT v.*, o.codigo FROM obrigacao_versao v JOIN obrigacao o ON o.id = v.obrigacao_id "
        "WHERE o.id = ? AND v.status = ?",
        (ob["id"], status),
    ).fetchone()
    return dict(row) if row else None


def historico(conn, codigo: str, empresa: str | None = QUALQUER) -> list[dict]:
    """Todas as versões de uma obrigação, da primeira à mais nova, com o título do ato que a originou."""
    ob = _uma(conn, codigo, empresa)
    if ob is None:
        return []
    rows = conn.execute(
        "SELECT v.*, o.codigo, a.titulo AS ato FROM obrigacao_versao v "
        "JOIN obrigacao o ON o.id = v.obrigacao_id LEFT JOIN ato a ON a.id = v.ato_id "
        "WHERE o.id = ? ORDER BY v.versao",
        (ob["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


def propor_versao(conn, codigo: str, mudancas: dict, *, ato_id: int | None,
                  trecho: str | None, fonte: str | None = None, empresa: str | None = QUALQUER) -> int:
    """Cria uma versão pendente: cópia da vigente com as mudanças aplicadas.

    Nada muda para a operação até alguém aprovar (decidir()). `empresa` é o escopo da busca do código
    (o mesmo código pode ser de uma cliente e de outra).
    """
    invalidos = set(mudancas) - set(CAMPOS_VERSAO)
    if invalidos:
        raise ErroCadastro(f"campos que não podem mudar: {sorted(invalidos)}")
    atual = versao(conn, codigo, empresa=empresa)
    if atual is None:
        raise ErroCadastro(f"{codigo} não tem versão vigente")
    if versao(conn, codigo, "pendente", empresa=empresa) is not None:
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


CAMPOS_DATA = ("prazo", "vigencia_desde", "vigencia_ate")


def _validar_correcoes(conn, row, correcoes: dict) -> dict:
    """Confere a correção de quem aprova e devolve {campo: [proposto, aprovado]} só do que mudou.
    Mesmas regras da proposta: campo que pode mudar, data AAAA-MM-DD, regra e agenda válidas;
    e a versão corrigida ainda tem de mudar alguma coisa (senão é caso de rejeitar)."""
    invalidos = set(correcoes) - set(CAMPOS_VERSAO)
    if invalidos:
        raise ErroCadastro(f"campos que não podem mudar: {sorted(invalidos)}")
    feitas = {}
    for campo, valor in correcoes.items():
        valor = (str(valor).strip() or None) if valor is not None else None
        if valor and campo in CAMPOS_DATA:
            try:
                date.fromisoformat(valor)
            except ValueError:
                raise ErroCadastro(f"{campo}: {valor!r} não é data AAAA-MM-DD") from None
        if campo == "regra" and valor:
            regras.validar(valor)
        if campo == "agenda" and valor:
            agenda_.validar(valor)
        if valor != row[campo]:
            feitas[campo] = [row[campo], valor]
    vigente = conn.execute("SELECT * FROM obrigacao_versao WHERE obrigacao_id = ? AND status = 'vigente'",
                           (row["obrigacao_id"],)).fetchone()
    if vigente is not None:
        final = {c: row[c] for c in CAMPOS_VERSAO} | {c: v[1] for c, v in feitas.items()}
        if all(final[c] == vigente[c] for c in CAMPOS_VERSAO):
            raise ErroCadastro("com a correção a obrigação fica igual à vigente: rejeite a mudança")
    return feitas


def decidir(conn, versao_id: int, aprovar: bool, por: str, correcoes: dict | None = None) -> None:
    """Aprova (a pendente vira vigente; a antiga, substituída) ou rejeita.

    `correcoes` ({campo: valor}) é o que quem aprova corrigiu na proposta antes de aprovar:
    a versão vigente fica com o valor corrigido, e o proposto fica guardado em `correcao`."""
    row = conn.execute("SELECT * FROM obrigacao_versao WHERE id = ?", (versao_id,)).fetchone()
    if row is None or row["status"] != "pendente":
        raise ErroCadastro(f"versão {versao_id} não está pendente")
    if correcoes and not aprovar:
        raise ErroCadastro("correção só vale para aprovar")
    feitas = _validar_correcoes(conn, row, correcoes) if correcoes else {}
    with conn:
        if feitas:
            conn.execute(
                f"UPDATE obrigacao_versao SET {', '.join(f'{c} = ?' for c in feitas)}, correcao = ? WHERE id = ?",
                (*(v[1] for v in feitas.values()), json.dumps(feitas, ensure_ascii=False), versao_id),
            )
        if aprovar:
            conn.execute(
                "UPDATE obrigacao_versao SET status = 'substituida' "
                "WHERE obrigacao_id = ? AND status = 'vigente'",
                (row["obrigacao_id"],),
            )
        conn.execute(
            "UPDATE obrigacao_versao SET status = ?, decidida_por = ?, decidida_em = ? "
            "WHERE id = ?",
            ("vigente" if aprovar else "rejeitada", por, agora(), versao_id),
        )


def diferencas(antes: dict, depois: dict) -> dict[str, tuple]:
    """Campos que mudaram entre duas versões: {campo: (antes, depois)}."""
    return {c: (antes[c], depois[c]) for c in CAMPOS_VERSAO if antes[c] != depois[c]}


# ------------------------------------------------------------------ evidência


def registrar_evidencia(conn, ativo_id: int, codigo: str, periodo: str, *,
                        arquivo: str | None = None, recebida_em: str | None = None,
                        extraido: dict | None = None) -> int:
    """Grava a comprovação de um período (idempotente por ativo + obrigação + período)."""
    ob = _obrigacao_id(conn, codigo, _empresa_do_ativo(conn, ativo_id))
    with conn:
        conn.execute(
            "INSERT INTO evidencia (ativo_id, obrigacao_id, periodo, arquivo, recebida_em, extraido) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(ativo_id, obrigacao_id, periodo) DO UPDATE SET arquivo = excluded.arquivo",
            (ativo_id, ob, periodo, arquivo, recebida_em or agora(),
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


def entregar(conn, ativo_id: int, codigo: str, periodo: str, *, dia: str, por: str | None = None,
             arquivo: str | None = None, obs: str | None = None) -> int:
    """Baixa manual: alguém diz que entregou o período, com ou sem arquivo. Encerra o que a
    obrigação tinha acionado até o dia da entrega e fica no histórico."""
    eid = registrar_evidencia(conn, ativo_id, codigo, periodo, arquivo=arquivo, recebida_em=dia,
                              extraido={"baixa_manual": True, "por": por, "obs": obs})
    encerrar_acionamentos(conn, ativo_id, codigo, dia)
    texto = f"entregue {periodo}" + (f" ({arquivo})" if arquivo else "") + (f": {obs}" if obs else "")
    registrar_evento(conn, ativo_id, codigo, "entrega", texto, por, em=dia)
    return eid


def desfazer_entrega(conn, ativo_id: int, codigo: str, periodo: str, por: str | None = None) -> bool:
    with conn:
        n = conn.execute("DELETE FROM evidencia WHERE ativo_id = ? AND obrigacao_id = ? AND periodo = ?",
                         (ativo_id, _obrigacao_id(conn, codigo, _empresa_do_ativo(conn, ativo_id)), periodo)).rowcount
    if n:
        registrar_evento(conn, ativo_id, codigo, "entrega", f"entrega de {periodo} desfeita", por)
    return bool(n)


def registrar_evento(conn, ativo_id: int, codigo: str | None, tipo: str, texto: str,
                     por: str | None = None, em: str | None = None) -> None:
    ob = _obrigacao_id(conn, codigo, _empresa_do_ativo(conn, ativo_id)) if codigo else None
    with conn:
        conn.execute("INSERT INTO evento (ativo_id, obrigacao_id, tipo, texto, por, em) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (ativo_id, ob, tipo, texto, por, em or agora()))


def atribuir(conn, ativo_id: int, codigo: str, responsavel: str, por: str | None = None) -> None:
    """Quem responde por esta obrigação neste ativo. Vazio volta ao responsável do ativo."""
    ob = _obrigacao_id(conn, codigo, _empresa_do_ativo(conn, ativo_id))
    nome = responsavel.strip()
    with conn:
        if nome:
            conn.execute("INSERT INTO responsavel_obrigacao (ativo_id, obrigacao_id, responsavel) VALUES (?, ?, ?) "
                         "ON CONFLICT(ativo_id, obrigacao_id) DO UPDATE SET responsavel = excluded.responsavel",
                         (ativo_id, ob, nome))
        else:
            conn.execute("DELETE FROM responsavel_obrigacao WHERE ativo_id = ? AND obrigacao_id = ?", (ativo_id, ob))
    registrar_evento(conn, ativo_id, codigo, "responsavel", f"responsável: {nome or 'o do ativo'}", por)


def responsaveis(conn) -> dict[tuple[int, str], str]:
    """{(ativo_id, código): responsável} das obrigações que têm responsável próprio."""
    return {(r["ativo_id"], r["codigo"]): r["responsavel"] for r in conn.execute(
        "SELECT ro.ativo_id, o.codigo, ro.responsavel FROM responsavel_obrigacao ro "
        "JOIN obrigacao o ON o.id = ro.obrigacao_id")}


def eventos(conn, ativo_id: int, codigo: str | None = None, limite: int = 50) -> list[dict]:
    """Histórico, mais recente primeiro. Com `codigo`: os da obrigação e os de cadastro do ativo."""
    sql = ("SELECT ev.*, o.codigo FROM evento ev LEFT JOIN obrigacao o ON o.id = ev.obrigacao_id "
           "WHERE ev.ativo_id = ?")
    args: list = [ativo_id]
    if codigo:
        sql += " AND (o.codigo = ? OR ev.obrigacao_id IS NULL)"
        args.append(codigo)
    return [dict(r) for r in conn.execute(sql + " ORDER BY ev.em DESC, ev.id DESC LIMIT ?", (*args, limite))]


def acionar(conn, ativo_id: int, codigo: str, dia: str, prazo: str, motivo: str,
            origem: str | None = None) -> None:
    """Abre uma obrigação por evento (idempotente por ativo + obrigação + dia)."""
    with conn:
        conn.execute(
            "INSERT INTO acionamento (ativo_id, obrigacao_id, dia, prazo, motivo, origem) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
            (ativo_id, _obrigacao_id(conn, codigo, _empresa_do_ativo(conn, ativo_id)), dia, prazo, motivo, origem))


def encerrar_acionamentos(conn, ativo_id: int, codigo: str, dia: str) -> int:
    """A evidência da obrigação acionada, feita em `dia`, encerra o que foi aberto até esse dia."""
    with conn:
        return conn.execute(
            "UPDATE acionamento SET encerrado_em = ? WHERE ativo_id = ? AND obrigacao_id = ? "
            "AND dia <= ? AND encerrado_em IS NULL", (dia, ativo_id, _obrigacao_id(conn, codigo, _empresa_do_ativo(conn, ativo_id)), dia)).rowcount


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
    a = conn.execute("SELECT a.tipo, a.atributos, e.nome AS empresa FROM ativo a "
                     "JOIN empresa e ON e.id = a.empresa_id WHERE a.id = ?", (ativo_id,)).fetchone()
    if a is None:
        raise ErroCadastro(f"ativo {ativo_id} não existe")
    attrs = json.loads(a["atributos"])
    # uma consulta só: vigente e pendente de todas as obrigações do tipo do ativo, das normas
    # públicas e das próprias da empresa dona do ativo (nunca as de outra empresa)
    versoes: dict[str, dict[str, dict]] = {}
    for r in conn.execute(
        "SELECT v.*, o.codigo FROM obrigacao_versao v JOIN obrigacao o ON o.id = v.obrigacao_id "
        "WHERE o.tipo_ativo = ? AND v.status IN ('vigente', 'pendente') "
        "AND (o.empresa IS NULL OR o.empresa = ?)", (a["tipo"], a["empresa"])
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
