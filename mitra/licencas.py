"""Licenças e condicionantes: as obrigações próprias da empresa, com o trecho literal conferido.

A empresa envia o PDF da licença (LP, LI, LO, LAC, outorga, autorização). A leitura reaproveita o que
já existe (`ocr.ler`, a mesma do leitor de evidências): a IA propõe as condicionantes como obrigações
(título, prazo, periodicidade, evidência, a que ativo ou unidade se aplica) **com o trecho literal da
licença**, e o Python confere que o trecho está, palavra por palavra, no texto do PDF. **Sem trecho
conferido, não entra** — a mesma regra do catálogo de normas públicas.

As propostas ficam pendentes. Quem aprova é o Regulatório (ou a Diretoria) **da própria empresa**: a
plataforma só lê os dados da cliente. Aprovada, a condicionante vira obrigação com `empresa` preenchida
e versão vigente, e o código é único por empresa (migração 0005), então duas clientes têm cada uma a
sua "LO-01".

A validade da licença também vira obrigação: renovar com a antecedência que a licença pedir (em geral
120 dias, `RENOVACAO_PADRAO`).

Dado pessoal **nunca** vai para a IA: o texto enviado passa por `pessoal.sem_cpf`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import agenda as agenda_, db, pessoal, regras
from .impacto import _limpo
from .instanciacao import LICENCAS, RENOVACAO_PADRAO, TIPOS_LICENCA, registrar

VERSAO_PROMPT = "condicionantes-v1"
PENDENTE, APROVADA, REJEITADA = "pendente", "aprovada", "rejeitada"

SISTEMA = """Você é analista de conformidade regulatória no Brasil e lê uma LICENÇA AMBIENTAL (ou
outorga/autorização) de um empreendimento minerário. Extraia as CONDICIONANTES: o que a licença obriga
o empreendedor a fazer, entregar, manter ou comunicar.

NÃO são condicionantes: a descrição do empreendimento, as competências do órgão, fundamentos legais,
definições, e o que a licença apenas autoriza (sem dever associado).

Para cada condicionante:
- "titulo": a ação no imperativo, curta (ex.: "Monitorar trimestralmente a qualidade das águas").
- "periodicidade": Mensal, Trimestral, Semestral, Anual, A cada N anos, Por evento ou Evento único.
- "prazo": quando, em texto curto, como a licença diz (ex.: "Até 30 dias após o fim do trimestre").
- "evidencia": o documento que comprova (ex.: "Laudo de laboratório acreditado").
- "aplica_a": "empresa", "unidade" ou "ativo" — a que a condicionante se refere.
- "alvo": o nome da unidade ou o código do ativo, se a licença disser; senão null.
- "numero": o número da condicionante na licença, se houver (ex.: "3.1"); senão null.
- "trecho": cópia literal, palavra por palavra, do texto da licença que cria a obrigação. Curto: a
  frase que obriga, não a página inteira. Escape as aspas no JSON.

Não invente e não complete: o que não estiver escrito, deixe null. Se a licença não tiver
condicionantes, devolva lista vazia.
Responda só com JSON: {"condicionantes": [ {...}, ... ], "validade": "AAAA-MM-DD ou null",
"numero_licenca": "o número da licença ou null", "orgao": "o órgão emissor ou null"}"""


class ErroLicenca(ValueError):
    pass


@dataclass
class Proposta:
    titulo: str
    periodicidade: str | None = None
    prazo: str | None = None
    evidencia: str | None = None
    aplica_a: str = "empresa"
    alvo: str | None = None
    numero: str | None = None
    trecho: str = ""
    pagina: int | None = None
    reprovada: str | None = None        # motivo, se o Python reprovou


@dataclass
class Leitura:
    propostas: list[Proposta] = field(default_factory=list)
    validade: str | None = None
    numero_licenca: str | None = None
    orgao: str | None = None
    modelo: str | None = None
    custo_usd: float = 0.0
    problemas: list[str] = field(default_factory=list)

    @property
    def aprovadas(self) -> list[Proposta]:
        return [p for p in self.propostas if p.reprovada is None]


# ------------------------------------------------------------------ conferência


def conferir(p: Proposta, texto: str, unidades: set[str], ativos: set[str]) -> str | None:
    """O motivo da reprovação, ou None se a proposta se sustenta. A regra do trecho é a do catálogo:
    cópia literal, palavra por palavra (só espaços e aspas curvas normalizados)."""
    if not (p.titulo or "").strip():
        return "condicionante sem título"
    if not p.trecho or _limpo(p.trecho) not in _limpo(texto):
        return "o trecho citado não existe no texto da licença"
    if p.aplica_a not in ("empresa", "unidade", "ativo"):
        return f"aplica_a {p.aplica_a!r}: use empresa, unidade ou ativo"
    if p.aplica_a == "unidade" and (p.alvo or "") not in unidades:
        return f"a empresa não tem a unidade {p.alvo!r}"
    if p.aplica_a == "ativo" and (p.alvo or "") not in ativos:
        return f"a empresa não tem o ativo {p.alvo!r}"
    return None


def _pagina_do_trecho(trecho: str, paginas: list[str]) -> int | None:
    """Em que página do PDF está o trecho (para a tela mostrar "página 4")."""
    alvo = _limpo(trecho)
    for n, pagina in enumerate(paginas, start=1):
        if alvo and alvo in _limpo(pagina):
            return n
    return None


def agenda_da(periodicidade: str | None, prazo: str | None) -> str:
    """A agenda que a torre usa, deduzida da periodicidade da condicionante (regra, não IA).
    O que não dá para deduzir vira "evento": a torre mostra como gatilho em vez de inventar prazo."""
    t = (periodicidade or "").strip().lower()
    folga = 30
    if m := re.search(r"até (\d{1,3}) dias", (prazo or "").lower()):
        folga = int(m.group(1))
    for palavra, freq in (("quinzenal", "quinzenal"), ("mensal", "mensal"), ("trimestral", "trimestral"),
                          ("semestral", "semestral"), ("anual", "anual"), ("bimestral", None)):
        if palavra in t and freq:
            return f"{freq}+{folga}d"
    if m := re.search(r"a cada (\d{1,2}) anos?", t):
        return f"anos:{m.group(1)}"
    if m := re.search(r"a cada (\d{1,2}) (?:meses|mes)", t):
        return f"meses:{m.group(1)}"
    if "único" in t or "unico" in t:
        return "unica"
    return "evento"


# ------------------------------------------------------------------ a licença


def guardar_licenca(conn, empresa_id: int, *, tipo: str, numero: str, por: str, orgao: str | None = None,
                    emitida_em: str | None = None, validade: str | None = None,
                    renovar_dias: int = RENOVACAO_PADRAO, unidade: str | None = None,
                    ativo_codigo: str | None = None, arquivo: str | None = None,
                    guardado_em: str | None = None, sha256: str | None = None,
                    texto: str | None = None) -> int:
    """Grava a licença enviada. O texto fica para o Python conferir o trecho de cada condicionante."""
    tipo = (tipo or "").strip()
    if tipo not in TIPOS_LICENCA:
        raise ErroLicenca(f"tipo de licença desconhecido: {tipo!r} (há: {', '.join(TIPOS_LICENCA)})")
    numero = (numero or "").strip()
    if not numero:
        raise ErroLicenca("informe o número da licença")
    for rotulo, valor in (("emitida_em", emitida_em), ("validade", validade)):
        if valor:
            try:
                date.fromisoformat(valor)
            except ValueError:
                raise ErroLicenca(f"{rotulo}: {valor!r} não é data AAAA-MM-DD") from None
    if unidade and not conn.execute("SELECT 1 FROM unidade WHERE empresa_id = ? AND nome = ?",
                                    (empresa_id, unidade)).fetchone():
        raise ErroLicenca(f"a empresa não tem a unidade {unidade!r}")
    if ativo_codigo and not db.ativo_por_codigo(conn, empresa_id, ativo_codigo):
        raise ErroLicenca(f"a empresa não tem o ativo {ativo_codigo!r}")
    if conn.execute("SELECT 1 FROM licenca WHERE empresa_id = ? AND tipo = ? AND numero = ?",
                    (empresa_id, tipo, numero)).fetchone():
        raise ErroLicenca(f"a empresa já tem a {tipo} {numero} cadastrada")
    with conn:
        cur = conn.execute(
            "INSERT INTO licenca (empresa_id, tipo, numero, orgao, emitida_em, validade, renovar_dias, "
            "unidade, ativo_codigo, arquivo, guardado_em, sha256, texto, enviada_por, enviada_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (empresa_id, tipo, numero, orgao, emitida_em, validade, int(renovar_dias), unidade,
             ativo_codigo, arquivo, guardado_em, sha256, texto, por, db.agora()))
    registrar(conn, empresa_id, LICENCAS, f"licença {tipo} {numero}", por,
              {"validade": validade, "unidade": unidade, "ativo": ativo_codigo})
    return cur.lastrowid


def licencas(conn, empresa_id: int) -> list[dict]:
    """As licenças da empresa, sem o texto (que é grande) e com a contagem de condicionantes."""
    rows = conn.execute(
        "SELECT l.id, l.empresa_id, l.tipo, l.numero, l.orgao, l.emitida_em, l.validade, l.renovar_dias, "
        "l.unidade, l.ativo_codigo, l.arquivo, l.guardado_em, l.sha256, l.enviada_por, l.enviada_em "
        "FROM licenca l WHERE l.empresa_id = ? ORDER BY l.tipo, l.numero", (empresa_id,)).fetchall()
    por_licenca: dict[int, dict[str, int]] = {}
    for r in conn.execute("SELECT licenca_id, status, COUNT(*) AS n FROM condicionante "
                          "WHERE empresa_id = ? GROUP BY licenca_id, status", (empresa_id,)):
        por_licenca.setdefault(r["licenca_id"], {})[r["status"]] = r["n"]
    return [dict(r) | {"condicionantes": por_licenca.get(r["id"], {})} for r in rows]


def licenca(conn, empresa_id: int, licenca_id: int) -> dict | None:
    """Uma licença da empresa. A de outra cliente não existe para esta."""
    r = conn.execute("SELECT * FROM licenca WHERE id = ? AND empresa_id = ?",
                     (licenca_id, empresa_id)).fetchone()
    return dict(r) if r else None


# ------------------------------------------------------------------ a leitura (IA + conferência)


def ler(conn, roteador, empresa_id: int, texto: str, paginas: list[str] | None = None) -> Leitura:
    """A IA propõe as condicionantes; o Python confere o trecho palavra por palavra. Nada é gravado.

    O texto vai para a IA **sem CPF** (`pessoal.sem_cpf`): dado pessoal nunca sai daqui."""
    le = Leitura()
    if len((texto or "").split()) < 20:
        le.problemas.append("o PDF não tem texto suficiente (parece escaneado): mande a versão digital")
        return le
    unidades = {u["nome"] for u in conn.execute(
        "SELECT nome FROM unidade WHERE empresa_id = ?", (empresa_id,))}
    ativos = {a["codigo"] for a in db.ativos(conn, empresa_id)}
    limpo = pessoal.sem_cpf(texto)
    try:
        r = roteador.pedir_json("condicionantes", 3, SISTEMA, limpo[:60000], VERSAO_PROMPT, max_tokens=8000)
    except Exception as erro:
        le.problemas.append(f"leitura indisponível: {str(erro)[:160]}")
        return le
    le.modelo = r.modelo.rotulo + (" (cache)" if r.do_cache else "")
    le.custo_usd = 0.0 if r.do_cache else r.custo_usd
    dados = r.dados
    le.validade = (dados.get("validade") or None) if isinstance(dados.get("validade"), str) else None
    le.numero_licenca = (dados.get("numero_licenca") or None)
    le.orgao = (dados.get("orgao") or None)
    for d in dados.get("condicionantes") or []:
        p = Proposta(
            titulo=str(d.get("titulo") or "").strip(),
            periodicidade=(d.get("periodicidade") or None),
            prazo=(d.get("prazo") or None),
            evidencia=(d.get("evidencia") or None),
            aplica_a=str(d.get("aplica_a") or "empresa").strip().lower(),
            alvo=(d.get("alvo") or None),
            numero=(str(d["numero"]) if d.get("numero") else None),
            trecho=str(d.get("trecho") or ""),
        )
        p.reprovada = conferir(p, texto, unidades, ativos)
        if p.reprovada is None and paginas:
            p.pagina = _pagina_do_trecho(p.trecho, paginas)
        le.propostas.append(p)
    return le


def propor(conn, empresa_id: int, licenca_id: int, le: Leitura, por: str) -> list[int]:
    """Grava as propostas conferidas como condicionantes pendentes. As reprovadas não entram."""
    if licenca(conn, empresa_id, licenca_id) is None:
        raise ErroLicenca(f"licença {licenca_id} não é desta empresa")
    ids = []
    for p in le.aprovadas:
        titulo = f"{p.titulo} (cond. {p.numero})" if p.numero else p.titulo
        with conn:
            cur = conn.execute(
                "INSERT INTO condicionante (licenca_id, empresa_id, titulo, prazo, periodicidade, agenda, "
                "evidencia, aplica_a, alvo, trecho, pagina, status, proposta_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (licenca_id, empresa_id, titulo, p.prazo, p.periodicidade,
                 agenda_da(p.periodicidade, p.prazo), p.evidencia, p.aplica_a, p.alvo, p.trecho,
                 p.pagina, PENDENTE, db.agora()))
        ids.append(cur.lastrowid)
    registrar(conn, empresa_id, LICENCAS, f"{len(ids)} condicionantes propostas", por,
              {"licenca_id": licenca_id, "reprovadas": [p.reprovada for p in le.propostas if p.reprovada]})
    return ids


def condicionantes(conn, empresa_id: int, status: str | None = None,
                   licenca_id: int | None = None) -> list[dict]:
    sql = ("SELECT c.*, l.tipo AS licenca_tipo, l.numero AS licenca_numero FROM condicionante c "
           "JOIN licenca l ON l.id = c.licenca_id WHERE c.empresa_id = ?")
    args: list = [empresa_id]
    if status:
        sql += " AND c.status = ?"
        args.append(status)
    if licenca_id is not None:
        sql += " AND c.licenca_id = ?"
        args.append(licenca_id)
    return [dict(r) for r in conn.execute(sql + " ORDER BY c.id", args)]


def condicionante(conn, empresa_id: int, condicionante_id: int) -> dict | None:
    r = conn.execute("SELECT c.*, l.tipo AS licenca_tipo, l.numero AS licenca_numero FROM condicionante c "
                     "JOIN licenca l ON l.id = c.licenca_id WHERE c.id = ? AND c.empresa_id = ?",
                     (condicionante_id, empresa_id)).fetchone()
    return dict(r) if r else None


# ------------------------------------------------------------------ a decisão da dona

CAMPOS_CORRIGIVEIS = ("titulo", "prazo", "periodicidade", "agenda", "evidencia", "aplica_a", "alvo")


def _proximo_codigo(conn, empresa_id: int, empresa: str, prefixo: str) -> str:
    """O próximo código livre da empresa para o prefixo ("LO-01", "LO-02"...). O código é único por
    empresa (migração 0005): o "LO-01" de uma cliente não atrapalha o da outra."""
    usados = {r["codigo"] for r in conn.execute(
        "SELECT codigo FROM obrigacao WHERE empresa = ?", (empresa,))}
    for n in range(1, 1000):
        codigo = f"{prefixo}-{n:02d}"
        if codigo not in usados:
            return codigo
    raise ErroLicenca(f"a empresa já tem 999 obrigações {prefixo}-xx")


def aprovar(conn, empresa_id: int, condicionante_id: int, por: str, correcoes: dict | None = None,
            nota: str | None = None) -> str:
    """A condicionante aprovada vira obrigação própria da empresa, já vigente. Devolve o código.

    `correcoes` é o que quem aprova ajustou antes de aprovar (título, prazo, periodicidade, agenda,
    evidência, a que se aplica): a obrigação nasce com o valor corrigido, e o proposto fica na nota."""
    c = condicionante(conn, empresa_id, condicionante_id)
    if c is None:
        raise ErroLicenca(f"condicionante {condicionante_id} não é desta empresa")
    if c["status"] != PENDENTE:
        raise ErroLicenca(f"a condicionante {condicionante_id} já foi {c['status']}")
    invalidos = set(correcoes or {}) - set(CAMPOS_CORRIGIVEIS)
    if invalidos:
        raise ErroLicenca(f"campos que não podem ser corrigidos: {sorted(invalidos)}")
    final = {k: c[k] for k in CAMPOS_CORRIGIVEIS} | {k: v for k, v in (correcoes or {}).items() if v is not None}
    agenda_.validar(final["agenda"] or "evento")
    empresa = conn.execute("SELECT nome FROM empresa WHERE id = ?", (empresa_id,)).fetchone()["nome"]
    tipo_ativo = {"ativo": _tipo_do_ativo(conn, empresa_id, final["alvo"]), "unidade": "unidade"}.get(
        final["aplica_a"], "licenca")
    codigo = _proximo_codigo(conn, empresa_id, empresa, c["licenca_tipo"])
    norma = f"{c['licenca_tipo']} {c['licenca_numero']}"
    regra = "*"
    regras.validar(regra)
    with conn:
        ob = conn.execute("INSERT INTO obrigacao (codigo, tipo_ativo, norma, area, empresa) "
                          "VALUES (?, ?, ?, 'ambiental', ?)",
                          (codigo, tipo_ativo, norma, empresa)).lastrowid
        conn.execute(
            "INSERT INTO obrigacao_versao (obrigacao_id, versao, titulo, artigo, aplica_se_a, regra, "
            "periodicidade, agenda, prazo, vigencia_desde, vigencia_ate, responsavel, evidencia, fonte, "
            "trecho, status, decidida_por, decidida_em) "
            "VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'vigente', ?, ?)",
            (ob, final["titulo"], f"{norma} cond. {c['id']}", _aplica_se_a(final), regra,
             final["periodicidade"], final["agenda"] or "evento", final["prazo"],
             _emitida(conn, c["licenca_id"]), _validade(conn, c["licenca_id"]),
             _responsavel_padrao(conn, empresa_id, "ambiental"), final["evidencia"], norma, c["trecho"],
             por, db.agora()))
        conn.execute("UPDATE condicionante SET status = ?, codigo = ?, decidida_por = ?, decidida_em = ?, "
                     "nota = ? WHERE id = ?",
                     (APROVADA, codigo, por, db.agora(),
                      json.dumps({"nota": nota, "correcoes": correcoes}, ensure_ascii=False)
                      if (nota or correcoes) else None, condicionante_id))
    registrar(conn, empresa_id, LICENCAS, f"condicionante {codigo} aprovada", por,
              {"condicionante_id": condicionante_id, "correcoes": correcoes})
    return codigo


def rejeitar(conn, empresa_id: int, condicionante_id: int, por: str, nota: str | None = None) -> None:
    c = condicionante(conn, empresa_id, condicionante_id)
    if c is None:
        raise ErroLicenca(f"condicionante {condicionante_id} não é desta empresa")
    if c["status"] != PENDENTE:
        raise ErroLicenca(f"a condicionante {condicionante_id} já foi {c['status']}")
    with conn:
        conn.execute("UPDATE condicionante SET status = ?, decidida_por = ?, decidida_em = ?, nota = ? "
                     "WHERE id = ?", (REJEITADA, por, db.agora(),
                                      json.dumps({"nota": nota}, ensure_ascii=False) if nota else None,
                                      condicionante_id))
    registrar(conn, empresa_id, LICENCAS, f"condicionante {condicionante_id} rejeitada", por, {"nota": nota})


def _aplica_se_a(final: dict) -> str:
    if final["aplica_a"] == "unidade" and final["alvo"]:
        return f"a unidade {final['alvo']}"
    if final["aplica_a"] == "ativo" and final["alvo"]:
        return f"o ativo {final['alvo']}"
    return "a licença da empresa"


def _tipo_do_ativo(conn, empresa_id: int, codigo: str | None) -> str:
    a = db.ativo_por_codigo(conn, empresa_id, codigo or "")
    return a["tipo"] if a else "licenca"


def _emitida(conn, licenca_id: int) -> str | None:
    r = conn.execute("SELECT emitida_em FROM licenca WHERE id = ?", (licenca_id,)).fetchone()
    return r["emitida_em"] if r else None


def _validade(conn, licenca_id: int) -> str | None:
    """A condicionante deixa de valer quando a licença vence (a renovada traz as suas)."""
    r = conn.execute("SELECT validade FROM licenca WHERE id = ?", (licenca_id,)).fetchone()
    return r["validade"] if r else None


def _responsavel_padrao(conn, empresa_id: int, area: str) -> str | None:
    r = conn.execute("SELECT responsavel FROM responsavel_padrao WHERE empresa_id = ? AND area = ?",
                     (empresa_id, area)).fetchone()
    return r["responsavel"] if r else None


# ------------------------------------------------------------------ a renovação da licença


def obrigacao_de_renovacao(conn, empresa_id: int, licenca_id: int, por: str) -> str | None:
    """A validade da licença vira obrigação: pedir a renovação com a antecedência que ela exige.
    Sem validade no cadastro, não há o que cobrar (e nada é presumido)."""
    lic = licenca(conn, empresa_id, licenca_id)
    if lic is None:
        raise ErroLicenca(f"licença {licenca_id} não é desta empresa")
    if not lic["validade"]:
        return None
    empresa = conn.execute("SELECT nome FROM empresa WHERE id = ?", (empresa_id,)).fetchone()["nome"]
    norma = f"{lic['tipo']} {lic['numero']}"
    if conn.execute("SELECT 1 FROM obrigacao o JOIN obrigacao_versao v ON v.obrigacao_id = o.id "
                    "WHERE o.empresa = ? AND o.norma = ? AND v.artigo = ?",
                    (empresa, norma, "validade")).fetchone():
        return None                 # já criada: chamar de novo não duplica
    vence = date.fromisoformat(lic["validade"])
    pedir_ate = vence - timedelta(days=int(lic["renovar_dias"] or RENOVACAO_PADRAO))
    codigo = _proximo_codigo(conn, empresa_id, empresa, lic["tipo"])
    # a renovação cobra de quem a licença cobre: o ativo dela, a unidade, ou a licença como ativo
    if lic["ativo_codigo"]:
        tipo_ativo = _tipo_do_ativo(conn, empresa_id, lic["ativo_codigo"])
    else:
        tipo_ativo = "unidade" if lic["unidade"] else "licenca"
    with conn:
        ob = conn.execute("INSERT INTO obrigacao (codigo, tipo_ativo, norma, area, empresa) "
                          "VALUES (?, ?, ?, 'ambiental', ?)",
                          (codigo, tipo_ativo, norma, empresa)).lastrowid
        conn.execute(
            "INSERT INTO obrigacao_versao (obrigacao_id, versao, titulo, artigo, aplica_se_a, regra, "
            "periodicidade, agenda, prazo, vigencia_desde, vigencia_ate, responsavel, evidencia, fonte, "
            "status, decidida_por, decidida_em) "
            "VALUES (?, 1, ?, 'validade', ?, '*', 'Evento único', ?, ?, ?, ?, ?, ?, ?, 'vigente', ?, ?)",
            (ob, f"Requerer a renovação da {norma}", "a licença da empresa",
             f"data:{pedir_ate.isoformat()}", f"Até {pedir_ate:%d/%m/%Y} "
             f"({lic['renovar_dias']} dias antes do vencimento, em {vence:%d/%m/%Y})",
             lic["emitida_em"], lic["validade"],
             _responsavel_padrao(conn, empresa_id, "ambiental"),
             "Protocolo do pedido de renovação no órgão ambiental", norma, por, db.agora()))
    registrar(conn, empresa_id, LICENCAS, f"renovação da {norma} ({codigo})", por,
              {"pedir_ate": pedir_ate.isoformat(), "vence": lic["validade"]})
    return codigo
