"""Postgres com a mesma cara da conexão SQLite.

O domínio (db.py, torre.py, usuarios.py...) escreve SQL portátil com `?` e usa a
conexão do jeito do `sqlite3`: `conn.execute(...).fetchone()["col"]`, `dict(linha)`,
`cur.lastrowid`, `with conn:` para a transação. Esta classe dá exatamente isso sobre o
psycopg, para o mesmo código rodar no SQLite (testes, demo offline) e no Postgres (API,
AWS RDS) sem um `if` sequer no domínio.

O que muda entre os dois fica aqui:
- `?` vira `%s` (fora de strings) e `%` literal vira `%%`;
- `lastrowid` vem de `RETURNING id`, acrescentado nos INSERT das tabelas com `id`;
- `with conn:` faz commit no fim e rollback se der erro, como no sqlite3.

A API empresta conexões de um pool (api/banco.py): `ConexaoPostgres.sobre(pg)` dá o mesmo
embrulho a uma conexão psycopg que já está aberta.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path

ESQUEMA_PG = Path(__file__).with_name("schema_pg.sql")

# Tabelas cuja chave é `id`: num INSERT nelas, `lastrowid` vem do RETURNING.
_COM_ID = {"empresa", "ativo", "ato", "obrigacao", "obrigacao_versao", "evidencia",
           "acionamento", "evento", "usuario", "auditoria", "instanciacao_evento", "unidade",
           "licenca", "condicionante", "responsavel_tecnico"}
_CRIADOS: set[tuple[str, str | None]] = set()
_INSERT = re.compile(r"^\s*INSERT\s+INTO\s+(\w+)", re.IGNORECASE)


def eh_url_postgres(alvo) -> bool:
    return isinstance(alvo, str) and alvo.startswith(("postgresql://", "postgres://", "postgresql+psycopg://"))


def url_psycopg(url: str) -> str:
    """A URL do SQLAlchemy (`postgresql+psycopg://`, a do Alembic) no formato que o psycopg aceita."""
    return url.replace("postgresql+psycopg://", "postgresql://")


def traduzir(sql: str) -> str:
    """`?` -> `%s` e `%` -> `%%`, sem tocar no que está entre aspas simples."""
    out, dentro = [], False
    for ch in sql:
        if ch == "'":
            dentro = not dentro
            out.append(ch)
        elif ch == "%":
            out.append("%%")
        elif ch == "?" and not dentro:
            out.append("%s")
        else:
            out.append(ch)
    return "".join(out)


class Linha:
    """Linha que se lê por nome e por posição, como `sqlite3.Row`."""

    __slots__ = ("_nomes", "_valores")

    def __init__(self, nomes: Sequence[str], valores: Sequence):
        self._nomes = nomes
        self._valores = tuple(valores)

    def __getitem__(self, k):
        if isinstance(k, (int, slice)):
            return self._valores[k]
        try:
            return self._valores[self._nomes.index(k)]
        except ValueError:
            raise IndexError(f"coluna {k!r} não existe") from None

    def keys(self) -> list[str]:
        return list(self._nomes)

    def __iter__(self):
        return iter(self._valores)

    def __len__(self) -> int:
        return len(self._valores)

    def __repr__(self) -> str:
        return f"Linha({dict(zip(self._nomes, self._valores, strict=True))!r})"


class Cursor:
    def __init__(self, cur, lastrowid=None):
        self._cur = cur
        self.lastrowid = lastrowid
        self.rowcount = cur.rowcount
        self._nomes = [d.name for d in cur.description] if cur.description else []
        self._pendente: list | None = None

    def _linha(self, valores):
        return Linha(self._nomes, valores) if valores is not None else None

    def fetchone(self):
        if self._pendente is not None:
            return self._linha(self._pendente.pop(0)) if self._pendente else None
        if not self._nomes:
            return None
        return self._linha(self._cur.fetchone())

    def fetchall(self) -> list[Linha]:
        if self._pendente is not None:
            linhas, self._pendente = self._pendente, []
            return [self._linha(v) for v in linhas]
        if not self._nomes:
            return []
        return [self._linha(v) for v in self._cur.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class ConexaoPostgres:
    """Uma conexão psycopg que se comporta como a do sqlite3 que o domínio espera."""

    dialeto = "postgres"

    def __init__(self, url: str, *, esquema: str | None = None, criar: bool = True):
        import psycopg

        url = url_psycopg(url)
        self._pg = psycopg.connect(url, autocommit=False)
        if esquema:
            with self._pg.cursor() as c:
                c.execute(f'CREATE SCHEMA IF NOT EXISTS "{esquema}"')
                c.execute(f'SET search_path TO "{esquema}"')
            self._pg.commit()
        if criar and (url, esquema) not in _CRIADOS:     # uma vez por processo, não a cada conexão
            aplicar_esquema(self)
            _CRIADOS.add((url, esquema))

    @classmethod
    def sobre(cls, pg) -> ConexaoPostgres:
        """O mesmo embrulho sobre uma conexão psycopg já aberta (a que o pool da API empresta).
        Não conecta nem cria tabelas: quem abriu a conexão cuida dela (e de devolvê-la)."""
        conn = cls.__new__(cls)
        conn._pg = pg
        return conn

    # --- a interface do sqlite3 que o domínio usa

    def execute(self, sql: str, params: Iterable = ()) -> Cursor:
        lastrowid = None
        m = _INSERT.match(sql)
        devolve_id = m and m.group(1).lower() in _COM_ID and "returning" not in sql.lower()
        if devolve_id:
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
        cur = self._pg.cursor()
        cur.execute(traduzir(sql), tuple(params))
        if devolve_id:
            linha = cur.fetchone()      # None quando o ON CONFLICT DO NOTHING não inseriu
            lastrowid = linha[0] if linha else None
            c = Cursor(cur, lastrowid)
            c._pendente = []
            return c
        return Cursor(cur, lastrowid)

    def executemany(self, sql: str, seq: Iterable[Iterable]) -> None:
        with self._pg.cursor() as cur:
            cur.executemany(traduzir(sql), [tuple(p) for p in seq])

    def executescript(self, script: str) -> None:
        with self._pg.cursor() as cur:
            cur.execute(script)

    def commit(self) -> None:
        self._pg.commit()

    def rollback(self) -> None:
        self._pg.rollback()

    def close(self) -> None:
        self._pg.close()

    def __enter__(self):
        return self

    def __exit__(self, tipo, *_):
        if tipo is None:
            self._pg.commit()
        else:
            self._pg.rollback()
        return False


def aplicar_esquema(conn: ConexaoPostgres) -> None:
    """Cria as tabelas que faltam (idempotente). Em produção quem faz isso é o Alembic,
    que roda o mesmo arquivo; aqui serve para testes e para o primeiro `conectar`."""
    conn.executescript(ESQUEMA_PG.read_text(encoding="utf-8"))
    conn.commit()
