"""Mudanças de norma (aprovar, corrigir, rejeitar) e o radar do DOU (triagem -> IA -> Python).

Quem decide depende de quem é a obrigação: mudança de norma pública (Res. ANM, NR...) é aprovada
pela curadoria da Mitra (plataforma), uma vez para todas as clientes; a cliente vê a mudança
como "aguardando curadoria Mitra". Obrigação própria de uma empresa (condicionante da licença,
TAC) é aprovada pelo Regulatório ou pela Diretoria dela."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from regulaia import db, demo, impacto, torre
from regulaia.ia import Roteador

from .. import auditoria
from ..banco import conexao, roteador
from ..seguranca import SO_LEITURA, Escopo, curadoria, decide_normas, empresa_visivel, regulatorio

rota = APIRouter(tags=["regulatório"])

NORMA_PUBLICA, PROPRIA = "norma pública", "empresa"
FUNIL = db.ROOT / "data" / "funil_dou.json"
CAMPO = {"prazo": "Prazo", "vigencia_desde": "Começa a valer em", "vigencia_ate": "Deixa de valer após",
         "periodicidade": "Periodicidade", "aplica_se_a": "Aplica-se a", "titulo": "Obrigação",
         "evidencia": "Evidência", "regra": "Regra", "agenda": "Agenda"}


class MudancaRadar(BaseModel):
    obrigacao: str
    campo: str
    valor_novo: str | None
    reprovada: str | None = Field(description="motivo, se o Python reprovou")


class AnaliseRadar(BaseModel):
    """O que o radar guardou de um ato analisado: candidatas, motivo, modelo, custo e mudanças."""
    ato: str
    ato_nome: str | None
    candidatas: list[str]
    motivo: str
    confianca: float | None
    modelos: list[str]
    custo_usd: float = Field(description="gasto nesta execução (resposta em cache não é paga de novo)")
    custo_original_usd: float = Field(description="quanto a resposta custou quando foi pedida pela primeira vez")
    revisao_humana: bool
    mudancas: list[MudancaRadar]


class CampoMudanca(BaseModel):
    campo: str
    rotulo: str
    vigente: str | None
    proposto: str | None
    vigente_texto: str
    proposto_texto: str
    data: bool = Field(description="campo de data (AAAA-MM-DD): a correção é uma data")


class Mudanca(BaseModel):
    versao_id: int
    codigo: str
    titulo: str
    diferencas: dict[str, list] = Field(description="{campo: [vigente, proposto]}")
    campos: list[CampoMudanca] = Field(description="as diferenças prontas para mostrar e corrigir")
    ato: str | None
    publicado_em: str | None
    trecho: str | None
    fonte: str | None
    ativos: list[str]
    norma: str | None
    empresa: str | None = Field(description="dona da obrigação própria; vazio: norma pública")
    escopo: str = Field(description="'norma pública' (vale para todas as clientes) ou 'empresa' (só desta)")
    decide: bool = Field(description="se quem pede pode aprovar ou rejeitar esta mudança")
    quem_decide: str = Field(examples=["curadoria Mitra", "Regulatório ou Diretoria da Mineradora Serra Azul"])
    analise: AnaliseRadar | None = Field(None, description="a análise do radar que propôs a mudança, se houver")
    tamanho: str | None = Field(None, description="o tamanho da mudança dito pelos dados: o que muda e o que fica")
    conferencia: list[str] = Field([], description="o que o Python conferiu antes de propor")


class DecisaoRegistrada(BaseModel):
    versao_id: int
    codigo: str
    ato: str | None
    ato_nome: str | None
    status: str = Field(description="vigente, substituida (aprovada) ou rejeitada")
    aprovada: bool
    corrigida: bool
    decidida_por: str | None
    decidida_em: str | None


class Decisao(BaseModel):
    aprovar: bool
    correcoes: dict[str, str | None] | None = Field(
        None, description="campos corrigidos por quem aprova antes de aprovar ({campo: valor})")


class Ato(BaseModel):
    identificacao: str | None = Field(None, examples=["RESOLUÇÃO ANM Nº 245, DE 31 DE JULHO DE 2026"],
                                      description="vazio: a primeira linha do texto, até o ano")
    texto: str = Field(min_length=20, max_length=200_000)
    empresa_id: int | None = Field(None, description=(
        "analisa no escopo desta empresa (normas públicas e obrigações próprias dela). É o que o agente "
        "preso a uma empresa manda; sem ele, a plataforma analisa contra o catálogo inteiro e a cliente "
        "contra o dela. Empresa de outra cliente: 404."))


class Funil(BaseModel):
    mes: str = Field(description="o mês medido, ex.: ago/2026")
    atos: int = Field(description="atos publicados no DOU (Seção 1) no mês")
    anm: int = Field(description="desses, os da ANM")
    normativos: int = Field(description="normativos da ANM: os únicos que chegam à IA")
    mudam: int = Field(description="atos que mudam o cadastro")
    fonte: str


class CustoIA(BaseModel):
    tarefa: str
    n: int
    usd: float


class EstadoIA(BaseModel):
    ligada: bool = Field(description="há chave de IA: sem ela, só regra e respostas em cache")
    gasto_hoje_usd: float
    teto_dia_usd: float | None


class Radar(BaseModel):
    funil: Funil | None
    analises: list[AnaliseRadar]
    custo_ia: list[CustoIA]
    ia_ligada: bool
    ia: EstadoIA


class Candidata(BaseModel):
    codigo: str
    titulo: str | None
    motivos: list[str]


class MudancaAnalisada(BaseModel):
    obrigacao: str
    campo: str
    campo_rotulo: str
    valor_atual: str | None
    valor_novo: str | None
    valor_atual_texto: str
    valor_novo_texto: str
    trecho: str
    justificativa: str
    reprovada: str | None


class AnaliseAto(BaseModel):
    ato: str
    ato_nome: str | None
    candidatas: list[Candidata]
    motivo: str
    confianca: float | None
    modelos: list[str]
    custo_usd: float
    custo_original_usd: float
    revisao_humana: bool
    mudancas: list[MudancaAnalisada]
    aprovadas: int = Field(description="mudanças que passaram na conferência do Python")
    registro: AnaliseRadar = Field(description="o resumo que o radar guarda (o mesmo de GET /radar)")


class Proposta(BaseModel):
    ato_id: int
    versoes: list[int]


class Ok(BaseModel):
    ok: bool


class AtoExemplo(BaseModel):
    identificacao: str
    texto: str


# o mesmo ato fictício do Streamlit: a resposta da IA para ele está no cache da demo (data/cache_ia_demo.json)
ATO_EXEMPLO = """RESOLUÇÃO FICTÍCIA DE TESTE Nº 1, DE 2 DE MARÇO DE 2027
(texto inventado para demonstração: não é um ato real)

Art. 1º O inciso I do art. 19 da Resolução ANM nº 95, de 7 de fevereiro de 2022, passa a vigorar com a seguinte redação:
"I - preencher, semanalmente, as Fichas de Inspeção Regular (FIR);"
Art. 2º Esta Resolução entra em vigor em 1º de abril de 2027."""


def _quem_decide(dona: str | None) -> str:
    return "curadoria Mitra" if dona is None else f"Regulatório ou Diretoria da {dona}"


def _analises() -> list[dict]:
    return json.loads(demo.RADAR.read_text(encoding="utf-8")) if demo.RADAR.exists() else []


def _registro(r: dict) -> AnaliseRadar:
    campos = {k: r[k] for k in AnaliseRadar.model_fields if k in r and k not in ("ato_nome", "mudancas")}
    return AnaliseRadar(**campos, ato_nome=torre.nome_ato(r["ato"]), mudancas=[MudancaRadar(**m) for m in r["mudancas"]])


def _texto(campo: str, valor) -> str:
    return torre._valor(valor, campo) if valor not in (None, "") else "—"


def _tamanho(conn, r: dict, codigo: str, norma: str | None) -> str:
    """O tamanho da mudança dito pelos dados, não pela IA: o que foi à IA, o que muda, o que fica."""
    mudam = sorted({x["obrigacao"] for x in r["mudancas"] if not x["reprovada"]} or {codigo})
    iguais = [c for c in r["candidatas"] if c not in mudam]
    outras = conn.execute(f"SELECT COUNT(*) FROM obrigacao WHERE norma = ? AND codigo NOT IN ({','.join('?' * len(mudam))})",
                          (norma, *mudam)).fetchone()[0] if norma else 0
    n = len(mudam)
    return (f"Muda {n} {'obrigação' if n == 1 else 'obrigações'} ({', '.join(mudam)}). "
            f"As outras {outras} da {norma or 'mesma norma'} ficam iguais. "
            f"Foram à IA {len(r['candidatas'])} candidatas; "
            f"{', '.join(iguais) or 'nenhuma outra'} {'ficou igual' if len(iguais) == 1 else 'ficaram iguais'}.")


def _conferencia(r: dict) -> list[str]:
    com_data = any(x["campo"] in impacto.CAMPOS_DATA for x in r["mudancas"] if not x["reprovada"])
    return ["a obrigação estava entre as candidatas", "o trecho existe no ato"] + (
        ["as datas propostas aparecem no trecho"] if com_data else [])


@rota.get("/empresas/{empresa_id}/mudancas", response_model=list[Mudanca],
          summary="Mudanças propostas por atos novos, aguardando decisão (da curadoria ou da empresa)")
def mudancas(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    visiveis = {a["codigo"] for a in db.ativos(conn, empresa_id) if e.ve_ativo(a)}
    radar = {torre.nome_ato(r["ato"]): r for r in _analises()}
    normas = {r["codigo"]: r["norma"] for r in conn.execute("SELECT codigo, norma FROM obrigacao")}
    out = []
    for m in torre.mudancas(conn, empresa_id):
        if not (e.ve_tudo or set(m.ativos) & visiveis):
            continue
        d = asdict(m)
        d["diferencas"] = {k: list(v) for k, v in m.diferencas.items()}
        norma = normas.get(m.codigo)
        r = radar.get(m.ato)
        campos = [CampoMudanca(campo=c, rotulo=CAMPO.get(c, c), vigente=a, proposto=b, vigente_texto=_texto(c, a),
                               proposto_texto=_texto(c, b), data=c in db.CAMPOS_DATA)
                  for c, (a, b) in m.diferencas.items()]
        out.append(Mudanca(**d, campos=campos, norma=norma, escopo=NORMA_PUBLICA if m.empresa is None else PROPRIA,
                           decide=e.decide(m.empresa), quem_decide=_quem_decide(m.empresa),
                           analise=_registro(r) if r else None, tamanho=_tamanho(conn, r, m.codigo, norma) if r else None,
                           conferencia=_conferencia(r) if r else []))
    return out


@rota.get("/empresas/{empresa_id}/decisoes", response_model=list[DecisaoRegistrada],
          summary="Mudanças vindas de atos que já foram decididas (aprovadas, corrigidas ou rejeitadas)")
def decisoes(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    rows = conn.execute(
        "SELECT v.id, o.codigo, o.empresa, v.status, v.decidida_por, v.decidida_em, v.correcao, a.titulo AS ato "
        "FROM obrigacao_versao v JOIN obrigacao o ON o.id = v.obrigacao_id LEFT JOIN ato a ON a.id = v.ato_id "
        "WHERE v.ato_id IS NOT NULL AND v.status != 'pendente' AND (o.empresa IS NULL OR o.empresa = ?) "
        "ORDER BY v.decidida_em DESC, v.id DESC", (emp["nome"],)).fetchall()
    return [DecisaoRegistrada(versao_id=r["id"], codigo=r["codigo"], ato=r["ato"], ato_nome=torre.nome_ato(r["ato"]),
                              status=r["status"], aprovada=r["status"] != "rejeitada", corrigida=bool(r["correcao"]),
                              decidida_por=(r["decidida_por"] or "").split(" (")[0] or None,
                              decidida_em=r["decidida_em"]) for r in rows]


@rota.post("/mudancas/{versao_id}/decisao", response_model=Ok,
           summary="Aprovar (com correção opcional) ou rejeitar uma mudança")
def decidir(versao_id: int, dados: Decisao, request: Request, e: Escopo = Depends(decide_normas),
            conn=Depends(conexao)):
    r = conn.execute("SELECT o.empresa FROM obrigacao_versao v JOIN obrigacao o ON o.id = v.obrigacao_id "
                     "WHERE v.id = ?", (versao_id,)).fetchone()
    if r is None or not e.ve_obrigacao(r["empresa"]):     # a de outra cliente: 404, como se não existisse
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"mudança {versao_id} não existe")
    if not e.decide(r["empresa"]):
        auditoria.registrar(conn, request, "decisao", str(versao_id), dados.model_dump(), resultado="recusado")
        motivo = ("mudança de norma pública: quem aprova é a curadoria da Mitra, uma vez para todas as clientes"
                  if r["empresa"] is None else
                  f"obrigação própria da {r['empresa']}: quem aprova ou rejeita é o Regulatório ou a Diretoria dela"
                  + (f" ({SO_LEITURA})" if e.so_leitura else ""))
        raise HTTPException(status.HTTP_403_FORBIDDEN, motivo)
    try:
        db.decidir(conn, versao_id, aprovar=dados.aprovar, por=e.assinante, correcoes=dados.correcoes)
    except db.ErroCadastro as erro:
        auditoria.registrar(conn, request, "decisao", str(versao_id), dados.model_dump(), resultado="recusado")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "decisao", str(versao_id), dados.model_dump())
    return Ok(ok=True)


def _funil(analises: list[dict]) -> Funil | None:
    """O funil do mês medido no XML do DOU (data/funil_dou.json, conferido por teste contra o ZIP)."""
    if not FUNIL.exists():
        return None
    f = json.loads(FUNIL.read_text(encoding="utf-8"))
    mudam = sum(1 for r in analises if any(not m["reprovada"] for m in r["mudancas"]))
    return Funil(mes=f["mes"], atos=f["atos"], anm=f["anm"], normativos=f["normativos"], mudam=mudam, fonte=f["fonte"])


@rota.get("/radar", response_model=Radar, summary="O radar do DOU: funil do mês, análises e custo real da IA")
def radar(e: Escopo = Depends(regulatorio), rot: Roteador = Depends(roteador)):
    analises = _analises()
    gastos = [CustoIA(tarefa=r["tarefa"], n=r["n"], usd=float(r["usd"])) for r in rot.conn.execute(
        "SELECT tarefa, COUNT(*) AS n, COALESCE(SUM(custo_usd), 0) AS usd FROM analise_ia GROUP BY tarefa "
        "ORDER BY tarefa").fetchall()]
    estado = EstadoIA(ligada=rot.ligada, gasto_hoje_usd=float(rot.gasto_hoje()), teto_dia_usd=rot.teto_dia_usd)
    return Radar(funil=_funil(analises), analises=[_registro(r) for r in analises], custo_ia=gastos,
                 ia_ligada=rot.ligada, ia=estado)


@rota.get("/radar/exemplo", response_model=AtoExemplo,
          summary="Um ato fictício de exemplo para o 'teste com um ato seu' (a resposta da IA está no cache)")
def exemplo(e: Escopo = Depends(regulatorio)):
    return AtoExemplo(identificacao=torre.titulo_do_ato(ATO_EXEMPLO), texto=ATO_EXEMPLO)


def _analisar(conn, rot: Roteador, dados: Ato, e: Escopo) -> impacto.Analise:
    ident = (dados.identificacao or "").strip() or torre.titulo_do_ato(dados.texto)
    # a cliente só analisa contra as normas públicas e as obrigações dela; com `empresa_id`, a plataforma
    # (o agente preso a uma cliente) também: condicionante de outra empresa nunca aparece na análise
    empresa = None if e.plataforma else e.empresa
    if dados.empresa_id is not None:
        empresa = empresa_visivel(conn, e, dados.empresa_id)["nome"]
    try:
        return impacto.analisar(conn, rot, ident, dados.texto, empresa=empresa)
    except Exception as erro:       # sem chave e sem cache, ou provedor fora do ar
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"análise indisponível: {erro}") from None


def _analise_ato(conn, an: impacto.Analise) -> AnaliseAto:
    titulos = {r["codigo"]: r["titulo"] for r in conn.execute(
        "SELECT o.codigo, v.titulo FROM obrigacao_versao v JOIN obrigacao o ON o.id = v.obrigacao_id "
        "WHERE v.status = 'vigente'")}
    reg = demo.registro_radar(an)
    return AnaliseAto(
        ato=an.ato, ato_nome=torre.nome_ato(an.ato),
        candidatas=[Candidata(codigo=c.codigo, titulo=titulos.get(c.codigo), motivos=list(c.motivos))
                    for c in an.candidatas],
        motivo=an.motivo, confianca=an.confianca, modelos=an.modelos, custo_usd=an.custo_usd,
        custo_original_usd=an.custo_original_usd, revisao_humana=an.revisao_humana,
        mudancas=[MudancaAnalisada(obrigacao=m.obrigacao, campo=m.campo, campo_rotulo=CAMPO.get(m.campo, m.campo),
                                   valor_atual=m.valor_atual, valor_novo=m.valor_novo,
                                   valor_atual_texto=_texto(m.campo, m.valor_atual),
                                   valor_novo_texto=_texto(m.campo, m.valor_novo), trecho=m.trecho,
                                   justificativa=m.justificativa, reprovada=m.reprovada) for m in an.mudancas],
        aprovadas=len(an.aprovadas), registro=_registro(reg))


@rota.post("/radar/analise", response_model=AnaliseAto,
           summary="Teste com um ato: triagem por regra, IA só nas candidatas, conferência do Python")
def analisar(dados: Ato, request: Request, e: Escopo = Depends(regulatorio), conn=Depends(conexao),
             rot: Roteador = Depends(roteador)):
    an = _analisar(conn, rot, dados, e)
    auditoria.registrar(conn, request, "radar_analise", an.ato[:120],
                        {"mudancas": len(an.mudancas), "custo_usd": an.custo_usd})
    return _analise_ato(conn, an)


@rota.post("/radar/propor", response_model=Proposta,
           summary="Mandar as mudanças aprovadas pelo Python para a fila de decisão (curadoria)")
def propor(dados: Ato, request: Request, e: Escopo = Depends(curadoria), conn=Depends(conexao),
           rot: Roteador = Depends(roteador)):
    an = _analisar(conn, rot, dados, e)
    if not an.aprovadas:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "nenhuma mudança passou na conferência")
    ident = "upload-" + hashlib.sha256(dados.texto.encode()).hexdigest()[:16]
    ato_id = db.registrar_ato(conn, "upload", ident, an.ato, texto=dados.texto)
    try:
        versoes = impacto.aplicar(conn, an, ato_id)
    except db.ErroCadastro as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None
    auditoria.registrar(conn, request, "radar_propor", ident, {"versoes": versoes})
    return Proposta(ato_id=ato_id, versoes=versoes)
