"""Personalização da empresa: prazo interno, normas internas e responsável padrão por área.

Três coisas que a cliente ajusta **sem mexer na norma**:

- **Prazo interno**: a empresa pode adiantar o prazo de uma obrigação (pública ou própria), por exemplo
  "entregar 15 dias antes do prazo legal". A torre mostra os dois — o interno e o legal — e atrasa pelo
  interno. A norma fica intacta: isto é meta da empresa, não mudança de obrigação, e por isso vive numa
  tabela à parte (`prazo_interno`) e não numa versão de obrigação.
- **Normas internas**: obrigação própria **sem licença** (padrão corporativo, política interna),
  cadastrada pela empresa e aprovada por ela mesma, como a condicionante (`licencas.aprovar`).
- **Responsável padrão por área**: obrigação nova da empresa já nasce com quem responde por ela
  (usado por `licencas.aprovar` e por `nova_norma_interna`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import agenda as agenda_, db, regras
from .instanciacao import ErroInstanciacao, registrar

AREAS = ("barragem", "emergencia", "ambiental", "equipamento", "seguranca_trabalho", "documentacao",
         "comunicacao")
LIMITE_DIAS = 365


class ErroPersonalizacao(ValueError):
    pass


# ------------------------------------------------------------------ prazo interno


@dataclass
class PrazoInterno:
    codigo: str
    dias_antes: int
    definido_por: str
    definido_em: str


def definir_prazo_interno(conn, empresa_id: int, codigo: str, dias_antes: int, por: str) -> None:
    """Adianta em `dias_antes` o prazo daquela obrigação para esta empresa. `dias_antes = 0` tira a meta.

    O código tem de ser de obrigação que a empresa vê (norma pública ou própria dela): não dá para
    criar meta sobre a condicionante de outra cliente."""
    if not isinstance(dias_antes, int) or dias_antes < 0 or dias_antes > LIMITE_DIAS:
        raise ErroPersonalizacao(f"dias antes do prazo legal: use de 0 a {LIMITE_DIAS}")
    empresa = conn.execute("SELECT nome FROM empresa WHERE id = ?", (empresa_id,)).fetchone()
    if empresa is None:
        raise ErroPersonalizacao(f"empresa {empresa_id} não existe")
    try:
        db.obrigacao_por_codigo(conn, codigo, empresa["nome"])
    except db.ErroCadastro as erro:
        raise ErroPersonalizacao(str(erro)) from None
    with conn:
        if dias_antes:
            conn.execute(
                "INSERT INTO prazo_interno (empresa_id, codigo, dias_antes, definido_por, definido_em) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT (empresa_id, codigo) DO UPDATE SET "
                "dias_antes = excluded.dias_antes, definido_por = excluded.definido_por, "
                "definido_em = excluded.definido_em",
                (empresa_id, codigo, dias_antes, por, db.agora()))
        else:
            conn.execute("DELETE FROM prazo_interno WHERE empresa_id = ? AND codigo = ?",
                         (empresa_id, codigo))
    registrar(conn, empresa_id, "operacao", f"prazo interno de {codigo}", por, {"dias_antes": dias_antes})


def prazos_internos(conn, empresa_id: int) -> dict[str, PrazoInterno]:
    """{código: prazo interno} da empresa, para a torre mostrar os dois prazos."""
    return {r["codigo"]: PrazoInterno(codigo=r["codigo"], dias_antes=r["dias_antes"],
                                      definido_por=r["definido_por"], definido_em=r["definido_em"])
            for r in conn.execute("SELECT * FROM prazo_interno WHERE empresa_id = ?", (empresa_id,))}


def prazo_interno_de(vence: str | None, dias_antes: int | None) -> str | None:
    """A data interna a partir da legal. Sem meta (ou sem vencimento), não há data interna."""
    if not vence or not dias_antes:
        return None
    try:
        return (date.fromisoformat(vence) - timedelta(days=int(dias_antes))).isoformat()
    except ValueError:
        return None


# ------------------------------------------------------------------ responsável padrão por área


def definir_responsavel_padrao(conn, empresa_id: int, area: str, responsavel: str, por: str) -> None:
    """Quem responde, nesta empresa, por obrigação nova de uma área. `responsavel` vazio tira o padrão."""
    if area not in AREAS:
        raise ErroPersonalizacao(f"área desconhecida: {area!r} (há: {', '.join(AREAS)})")
    nome = (responsavel or "").strip()
    with conn:
        if nome:
            conn.execute(
                "INSERT INTO responsavel_padrao (empresa_id, area, responsavel, definido_por, definido_em) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT (empresa_id, area) DO UPDATE SET "
                "responsavel = excluded.responsavel, definido_por = excluded.definido_por, "
                "definido_em = excluded.definido_em",
                (empresa_id, area, nome, por, db.agora()))
        else:
            conn.execute("DELETE FROM responsavel_padrao WHERE empresa_id = ? AND area = ?",
                         (empresa_id, area))
    registrar(conn, empresa_id, "operacao", f"responsável padrão de {area}", por, {"responsavel": nome})


def responsaveis_padrao(conn, empresa_id: int) -> dict[str, str]:
    return {r["area"]: r["responsavel"] for r in conn.execute(
        "SELECT area, responsavel FROM responsavel_padrao WHERE empresa_id = ?", (empresa_id,))}


# ------------------------------------------------------------------ normas internas


def nova_norma_interna(conn, empresa_id: int, *, titulo: str, por: str, tipo_ativo: str = "barragem",
                       area: str = "documentacao", agenda: str = "evento",
                       periodicidade: str | None = None, prazo: str | None = None,
                       evidencia: str | None = None, aplica_se_a: str = "todos os ativos do tipo",
                       regra: str = "*", norma: str = "Padrão interno",
                       vigencia_desde: str | None = None) -> str:
    """Obrigação própria da empresa sem licença: padrão corporativo, política interna, TAC.

    Nasce vigente, assinada por quem cadastrou (é a empresa aprovando o que é dela), com código próprio
    (`INT-01`, `INT-02`...) único dentro da empresa."""
    from .licencas import _proximo_codigo

    titulo = (titulo or "").strip()
    if not titulo:
        raise ErroPersonalizacao("a norma interna precisa de um título")
    if area not in AREAS:
        raise ErroPersonalizacao(f"área desconhecida: {area!r} (há: {', '.join(AREAS)})")
    if tipo_ativo not in ("barragem", "unidade", "equipamento", "licenca"):
        raise ErroPersonalizacao(f"tipo de ativo desconhecido: {tipo_ativo!r}")
    try:
        regras.validar(regra)
        agenda_.validar(agenda)
    except (regras.RegraInvalida, agenda_.AgendaInvalida) as erro:
        raise ErroPersonalizacao(str(erro)) from None
    if vigencia_desde:
        try:
            date.fromisoformat(vigencia_desde)
        except ValueError:
            raise ErroPersonalizacao(f"começa a valer em: {vigencia_desde!r} não é data AAAA-MM-DD") from None
    r = conn.execute("SELECT nome FROM empresa WHERE id = ?", (empresa_id,)).fetchone()
    if r is None:
        raise ErroPersonalizacao(f"empresa {empresa_id} não existe")
    empresa = r["nome"]
    codigo = _proximo_codigo(conn, empresa_id, empresa, "INT")
    padrao = responsaveis_padrao(conn, empresa_id).get(area)
    with conn:
        ob = conn.execute("INSERT INTO obrigacao (codigo, tipo_ativo, norma, area, empresa) "
                          "VALUES (?, ?, ?, ?, ?)",
                          (codigo, tipo_ativo, norma, area, empresa)).lastrowid
        conn.execute(
            "INSERT INTO obrigacao_versao (obrigacao_id, versao, titulo, artigo, aplica_se_a, regra, "
            "periodicidade, agenda, prazo, vigencia_desde, vigencia_ate, responsavel, evidencia, fonte, "
            "status, decidida_por, decidida_em) "
            "VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, 'vigente', ?, ?)",
            (ob, titulo, norma, aplica_se_a, regra, periodicidade, agenda, prazo, vigencia_desde,
             padrao, evidencia, norma, por, db.agora()))
    registrar(conn, empresa_id, "operacao", f"norma interna {codigo}", por,
              {"titulo": titulo, "tipo_ativo": tipo_ativo, "agenda": agenda})
    return codigo


def normas_internas(conn, empresa_id: int) -> list[dict]:
    """As obrigações próprias da empresa que não vieram de licença (padrão interno)."""
    r = conn.execute("SELECT nome FROM empresa WHERE id = ?", (empresa_id,)).fetchone()
    if r is None:
        raise ErroInstanciacao(f"empresa {empresa_id} não existe")
    return [dict(x) for x in conn.execute(
        "SELECT o.codigo, o.norma, o.area, o.tipo_ativo, v.titulo, v.agenda, v.periodicidade, v.prazo, "
        "v.evidencia, v.responsavel, v.vigencia_desde, v.decidida_por, v.decidida_em "
        "FROM obrigacao o JOIN obrigacao_versao v ON v.obrigacao_id = o.id "
        "WHERE o.empresa = ? AND v.status = 'vigente' AND o.codigo LIKE 'INT-%' ORDER BY o.codigo",
        (r["nome"],))]
