"""A torre: painel por ativo, ficha do ativo, entregas, responsáveis, transição e boletim."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from regulaia import agenda, db, operacao, pdf, torre, usuarios

from .. import armazenamento, auditoria, cadastro
from ..banco import conexao
from ..config import desde_padrao, hoje_padrao
from ..seguranca import Escopo, diretoria, empresa_visivel, regulatorio

rota = APIRouter(tags=["torre"])

ROTULO = {agenda.ATRASADA: "atrasada", torre.DADO_FALTANDO: "dado faltando", agenda.VENCE_LOGO: "vence em breve",
          agenda.EM_DIA: "em dia", agenda.CUMPRIDA: "cumprida", agenda.GATILHO: "por gatilho"}
POSICOES = db.ROOT / "data" / "posicoes_demo.json"
LIMITE_COMPROVANTE = 20 * 1024 * 1024


# ------------------------------------------------------------------ modelos


class Empresa(BaseModel):
    id: int
    nome: str
    ficticia: bool
    monitorado_desde: str | None = None
    origem: str | None = None


class LinhaPainel(BaseModel):
    ativo: str
    ativo_id: int | None
    ativo_nome: str
    tipo_ativo: str
    responsavel: str | None
    responsavel_proprio: bool
    codigo: str
    norma: str | None
    area: str | None
    titulo: str
    artigo: str
    dispositivo: str = Field(description="norma e artigo prontos para mostrar")
    periodicidade: str | None
    agenda: str
    status: str = Field(description="atrasada, dado_faltando, vence_logo, em_dia, cumprida, gatilho")
    status_rotulo: str
    vence: str | None
    faltando: list[str]
    pendente: str = Field(description="o que falta, em português")
    ultima: str | None
    dados_faltando: list[str]
    mudanca_pendente: bool
    evidencia: str | None
    nota: str
    trecho: str | None = Field(None, description="o texto literal da norma que cria a obrigação (versão vigente)")
    agenda_descricao: str = Field("", description="a agenda em português ('quinzenal, até o fim de cada quinzena')")
    ultima_rotulo: str | None = Field(None, description="o último período comprovado, em português")
    faltando_rotulos: list[str] = Field([], description="os períodos sem evidência, em português")
    dados_faltando_rotulos: list[str] = Field([], description="o que falta no cadastro, em português")


class Painel(BaseModel):
    hoje: str
    desde: str
    contagem: dict[str, int]
    por_ativo: dict[str, dict[str, int]]
    linhas: list[LinhaPainel]


class Ativo(BaseModel):
    id: int
    codigo: str
    nome: str
    tipo: str
    responsavel: str | None
    atributos: dict
    contagem: dict[str, int]
    posicao: list[float] | None = Field(None, description="[latitude, longitude] para o mapa (só na demo)")


class Evidencia(BaseModel):
    id: int
    codigo: str
    periodo: str
    periodo_rotulo: str
    arquivo: str | None
    arquivo_nome: str | None
    recebida_em: str | None
    origem: str = Field(description="lido por regra, lido por IA (conferido), baixa manual ou histórico da demo")
    baixa_manual: bool
    avisos: list[str] = []


class Evento(BaseModel):
    id: int
    em: str
    tipo: str = Field(description="entrega, responsavel, comentario, cadastro...")
    codigo: str | None
    texto: str | None
    por: str | None


class Ficha(BaseModel):
    ativo: Ativo
    linhas: list[LinhaPainel]
    evidencias: list[Evidencia]
    eventos: list[Evento]


class Historico(BaseModel):
    """O que se fez numa obrigação de um ativo: entregas, comentários, atribuições e comprovantes."""
    eventos: list[Evento]
    evidencias: list[Evidencia]


class Alteracao(BaseModel):
    campo: str
    rotulo: str = Field(description="nome de tela do campo ('Prazo', 'Começa a valer em')")
    antes: str = Field(description="o valor anterior (ou o proposto, numa correção), pronto para mostrar")
    depois: str = Field(description="o valor novo (ou o aprovado, numa correção), pronto para mostrar")


class VersaoObrigacao(BaseModel):
    id: int
    versao: int
    codigo: str
    titulo: str
    artigo: str | None
    aplica_se_a: str | None
    regra: str | None
    periodicidade: str | None
    agenda: str | None
    agenda_descricao: str
    prazo: str | None
    vigencia_desde: str | None
    vigencia_ate: str | None
    responsavel: str | None
    evidencia: str | None
    fonte: str | None
    trecho: str | None
    status: str = Field(description="vigente, substituida, pendente ou rejeitada")
    decidida_por: str | None
    decidida_em: str | None
    correcao: dict[str, list] | None = Field(description="{campo: [proposto, aprovado]} quando quem aprovou corrigiu")
    ato: str | None = Field(description="o ato que originou a versão, como o DOU publica")
    ato_nome: str | None = Field(description="o mesmo ato, para ler ('Resolução ANM nº 245, de ...')")
    norma: str | None
    dispositivo: str
    mudou: list[Alteracao] = Field(default=[], description="o que mudou em relação à versão anterior")
    corrigido: list[Alteracao] = Field(default=[], description="o que quem aprovou corrigiu: proposto → aprovado")


class ObrigacaoResumo(BaseModel):
    codigo: str
    titulo: str
    norma: str | None
    versoes: int
    mudou: bool = Field(description="já teve mais de uma versão (mudou por ato ou tem mudança proposta)")


class Vencimento(BaseModel):
    dia: str
    periodo: str
    periodo_rotulo: str
    entregue: bool
    ativo: str
    ativo_id: int | None
    codigo: str
    titulo: str
    status: str
    responsavel: str | None


class ObrigacaoTroca(BaseModel):
    codigo: str
    titulo: str
    norma: str | None
    artigo: str | None
    dispositivo: str
    periodicidade: str | None
    agenda: str | None
    trecho: str | None
    aplica_se_a: str | None


class TemaTroca(BaseModel):
    tema: str
    situacao: str
    saem: list[ObrigacaoTroca]
    entram: list[ObrigacaoTroca]
    so_para_outros: list[ObrigacaoTroca] = Field(
        [], description="o tema existe na norma nova, mas a regra exclui este ativo (ex.: só DPA2 ≥ 4)")


class Troca(BaseModel):
    ativo: str
    ativo_nome: str
    responsavel: str | None
    saem: int
    entram: int
    temas: list[TemaTroca]


class Futura(BaseModel):
    dia: str
    ativo: str
    codigo: str
    titulo: str
    norma: str | None
    artigo: str
    dispositivo: str
    proposta: bool = Field(description="a data vem de uma mudança ainda não aprovada")


class Faixa(BaseModel):
    ativo: str
    norma: str
    desde: str | None = Field(description="desde quando a norma vale para o ativo (vazio: desde antes da demo)")
    ate: str | None = Field(description="até quando vale (vazio: sem data de fim)")


class Areas(BaseModel):
    areas: list[str] = Field(description="áreas da empresa: as dos gestores e as que já respondem por algo")
    com_conta: list[str] = Field(description="áreas com pelo menos uma conta ativa de gestor")


class PeriodoEntrega(BaseModel):
    periodo: str
    rotulo: str


class Comprovante(BaseModel):
    arquivo: str
    guardado_em: str
    sha256: str


class Resumo(BaseModel):
    ativos: int
    obrigacoes: int = Field(description="obrigações do catálogo que valem para a empresa (normas públicas e as dela)")
    normas: int
    evidencias: int


class Opcao(BaseModel):
    valor: str
    rotulo: str


class CampoCadastro(BaseModel):
    campo: str
    rotulo: str = Field(description="nome de tela ('Trabalhadores na ZAS')")
    pergunta: str = Field(description="o que perguntar a quem preenche ('há trabalhadores na Zona de Autossalvamento?')")
    tipo: str = Field(description="booleano, numero, opcoes, texto ou data")
    opcoes: list[Opcao] = []
    tipos_ativo: list[str] = Field(description="barragem, unidade, equipamento, licenca")


class Entrega(BaseModel):
    ativo_id: int
    codigo: str = Field(examples=["R95-01"])
    dia: date | None = Field(None, description="dia da entrega; padrão: o hoje da torre")
    periodo: str | None = Field(None, description="período comprovado; padrão: o primeiro que falta")
    obs: str | None = None
    arquivo: str | None = Field(None, description="onde o comprovante ficou (o `guardado_em` de POST /comprovantes)")


class EntregaFeita(BaseModel):
    evidencia_id: int
    periodo: str
    periodo_rotulo: str


class Atribuicao(BaseModel):
    ativo_id: int
    codigo: str
    responsavel: str = Field(description="área; vazio devolve a obrigação ao responsável do ativo")


class Comentario(BaseModel):
    ativo_id: int
    codigo: str | None = None
    texto: str = Field(min_length=1, max_length=2000)


class Atributos(BaseModel):
    atributos: dict


class Responsavel(BaseModel):
    area: str | None


class Ok(BaseModel):
    ok: bool


class Mudou(BaseModel):
    mudou: bool


# ------------------------------------------------------------------ apoio


def _ativo(conn, ativo_id: int, e: Escopo) -> dict:
    r = conn.execute("SELECT * FROM ativo WHERE id = ?", (ativo_id,)).fetchone()
    if r is None or not e.ve_empresa(r["empresa_id"]):       # o de outra cliente também é 404
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"ativo {ativo_id} não existe")
    a = db.ativos(conn, r["empresa_id"])
    ativo = next(x for x in a if x["id"] == ativo_id)
    # gestor vê o ativo da sua área e também o ativo em que alguma obrigação foi passada para ela
    if not e.ve_ativo(ativo) and not any(k[0] == ativo_id and v == e.area for k, v in db.responsaveis(conn).items()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "este ativo é de outra área")
    return ativo


def _trechos(conn) -> dict[str, str | None]:
    """O trecho literal da versão vigente de cada obrigação, numa consulta só."""
    return {r["codigo"]: r["trecho"] for r in conn.execute(
        "SELECT o.codigo, v.trecho FROM obrigacao_versao v JOIN obrigacao o ON o.id = v.obrigacao_id "
        "WHERE v.status = 'vigente'")}


def _linha(l: torre.Linha, trechos: dict[str, str | None] | None = None) -> LinhaPainel:
    return LinhaPainel(**{k: v for k, v in asdict(l).items()},
                       dispositivo=torre.dispositivo(l.norma, l.artigo), status_rotulo=ROTULO.get(l.status, l.status),
                       pendente=torre.pendente(l), trecho=(trechos or {}).get(l.codigo),
                       agenda_descricao=agenda.descrever(l.agenda) if l.agenda else "",
                       ultima_rotulo=agenda.rotulo_humano(l.ultima) if l.ultima else None,
                       faltando_rotulos=[agenda.rotulo_humano(p) for p in l.faltando],
                       dados_faltando_rotulos=[torre.campo_legivel(c) for c in l.dados_faltando])


def _visiveis(conn, e: Escopo, empresa_id: int, hoje: date, desde: date, ativo: str | None = None):
    donos = {a["codigo"]: a["responsavel"] for a in db.ativos(conn, empresa_id)}
    return [l for l in torre.painel(conn, empresa_id, hoje, desde, ativo=ativo) if e.ve_linha(l, donos.get(l.ativo))]


def _ativos_visiveis(conn, e: Escopo, empresa_id: int) -> list[dict]:
    """Os ativos da empresa que a sessão vê: os da área e os em que alguma obrigação foi passada para ela."""
    passados = {aid for (aid, _), v in db.responsaveis(conn).items() if e.area and v == e.area}
    return [a for a in db.ativos(conn, empresa_id) if e.ve_ativo(a) or a["id"] in passados]


def _contagem(linhas) -> dict[str, int]:
    out = {s: 0 for s in ROTULO}
    for l in linhas:
        out[l.status] = out.get(l.status, 0) + 1
    return out


def _posicoes(emp: dict) -> dict[str, list[float]]:
    """Coordenadas fictícias da empresa da demo; empresa importada do SIGBM vem sem coordenadas."""
    if not emp.get("ficticia") or emp.get("monitorado_desde") or not POSICOES.exists():
        return {}
    pos = json.loads(POSICOES.read_text(encoding="utf-8"))
    return {k: v for k, v in pos.items() if not k.startswith("_")}


def _ativo_modelo(a: dict, linhas, posicoes: dict | None = None) -> Ativo:
    return Ativo(id=a["id"], codigo=a["codigo"], nome=a["nome"], tipo=a["tipo"], responsavel=a["responsavel"],
                 atributos=a["atributos"], contagem=_contagem([l for l in linhas if l.ativo == a["codigo"]]),
                 posicao=(posicoes or {}).get(a["codigo"]))


def _evidencia(x: dict) -> Evidencia:
    extraido = x.get("extraido") or {}
    metodo = {"regra": "lido por regra", "ia": "lido por IA, conferido"}.get(extraido.get("metodo"))
    manual = bool(extraido.get("baixa_manual"))
    arq = x.get("arquivo")
    return Evidencia(id=x["id"], codigo=x["codigo"], periodo=x["periodo"],
                     periodo_rotulo=agenda.rotulo_humano(x["periodo"]), arquivo=arq,
                     arquivo_nome=arq.replace("\\", "/").split("/")[-1] if arq else None,
                     recebida_em=x.get("recebida_em"),
                     origem=metodo or ("baixa manual" if manual else "histórico da demo"), baixa_manual=manual,
                     avisos=[str(a) for a in extraido.get("avisos") or []])


def _evento(x: dict) -> Evento:
    return Evento(id=x["id"], em=x["em"], tipo=x["tipo"], codigo=x.get("codigo"), texto=x.get("texto"),
                  por=x.get("por"))


def _obrigacao(o: dict) -> ObrigacaoTroca:
    return ObrigacaoTroca(codigo=o["codigo"], titulo=o["titulo"], norma=o.get("norma"), artigo=o.get("artigo"),
                          dispositivo=torre.dispositivo(o.get("norma"), o.get("artigo")),
                          periodicidade=o.get("periodicidade"), agenda=o.get("agenda"), trecho=o.get("trecho"),
                          aplica_se_a=o.get("aplica_se_a"))


# ------------------------------------------------------------------ leitura


@rota.get("/empresas", response_model=list[Empresa],
          summary="Empresas que a sessão vê: a própria (cliente) ou todas (plataforma), a demo primeiro")
def empresas(e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    return [Empresa(**{**x, "ficticia": bool(x["ficticia"])}) for x in db.empresas(conn) if e.ve_empresa(x["id"])]


@rota.get("/empresas/{empresa_id}/painel", response_model=Painel,
          summary="Status de cada obrigação que vale no dia, por ativo, no escopo de quem pede")
def painel(empresa_id: int, hoje: date | None = None, ativo: str | None = None,
           status_: list[str] | None = Query(None, alias="status"),
           e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    hoje = hoje or hoje_padrao()
    desde = desde_padrao(emp)
    linhas = _visiveis(conn, e, empresa_id, hoje, desde, ativo)
    contagem = _contagem(linhas)
    if status_:
        linhas = [l for l in linhas if l.status in status_]
    trechos = _trechos(conn)
    return Painel(hoje=hoje.isoformat(), desde=desde.isoformat(), contagem=contagem,
                  por_ativo=torre.resumo(linhas), linhas=[_linha(l, trechos) for l in linhas])


@rota.get("/empresas/{empresa_id}/ativos", response_model=list[Ativo],
          summary="Ativos com a contagem por status (e a posição no mapa, na demo)")
def ativos(empresa_id: int, hoje: date | None = None, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    linhas = _visiveis(conn, e, empresa_id, hoje or hoje_padrao(), desde_padrao(emp))
    com_linha = {l.ativo for l in linhas}
    pos = _posicoes(emp)
    return [_ativo_modelo(a, linhas, pos) for a in db.ativos(conn, empresa_id)
            if e.ve_ativo(a) or a["codigo"] in com_linha]


@rota.get("/empresas/{empresa_id}/resumo", response_model=Resumo,
          summary="Quantos ativos, obrigações e evidências a empresa tem na torre")
def resumo(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    ids = [a["id"] for a in _ativos_visiveis(conn, e, empresa_id)]
    obs = conn.execute("SELECT COUNT(*), COUNT(DISTINCT norma) FROM obrigacao WHERE empresa IS NULL OR empresa = ?",
                       (emp["nome"],)).fetchone()
    n_ev = 0
    if ids:
        marcas = ",".join("?" * len(ids))
        n_ev = conn.execute(f"SELECT COUNT(*) FROM evidencia WHERE ativo_id IN ({marcas})", ids).fetchone()[0]
    return Resumo(ativos=len(ids), obrigacoes=obs[0], normas=obs[1], evidencias=n_ev)


@rota.get("/empresas/{empresa_id}/areas", response_model=Areas,
          summary="Áreas da empresa, para escolher quem responde por um ativo ou uma obrigação")
def areas(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    contas = usuarios.listar(conn, empresa=emp["nome"])
    com_conta = sorted({u["area"] for u in contas if u["area"] and u["ativa"] and u["papel"] == usuarios.GESTOR})
    return Areas(areas=sorted(set(usuarios.areas(conn, empresa=emp["nome"]))), com_conta=com_conta)


@rota.get("/cadastro/campos", response_model=list[CampoCadastro],
          summary="Os dados do cadastro de um ativo: nome de tela, tipo e valores possíveis (para editar)")
def campos_do_cadastro(e: Escopo = Depends(regulatorio)):
    return [CampoCadastro(campo=c, rotulo=r, pergunta=cadastro.pergunta(c), tipo=t,
                          opcoes=[Opcao(valor=o, rotulo=cadastro.valor(o)) for o in ops or []], tipos_ativo=list(tipos))
            for c, (r, t, ops, tipos) in cadastro.CAMPOS.items()]


@rota.get("/ativos/{ativo_id}", response_model=Ficha, summary="Ficha do ativo: pendências, evidências e histórico")
def ficha(ativo_id: int, hoje: date | None = None, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    a = _ativo(conn, ativo_id, e)
    emp = empresa_visivel(conn, e, a["empresa_id"])
    linhas = _visiveis(conn, e, emp["id"], hoje or hoje_padrao(), desde_padrao(emp), ativo=a["codigo"])
    trechos = _trechos(conn)
    return Ficha(ativo=_ativo_modelo(a, linhas, _posicoes(emp)), linhas=[_linha(l, trechos) for l in linhas],
                 evidencias=[_evidencia(x) for x in db.evidencias_do_ativo(conn, ativo_id, 20)],
                 eventos=[_evento(x) for x in db.eventos(conn, ativo_id, limite=50)])


@rota.get("/ativos/{ativo_id}/obrigacoes/{codigo}/historico", response_model=Historico,
          summary="O que se fez numa obrigação do ativo: entregas, comentários, atribuições e comprovantes")
def historico_no_ativo(ativo_id: int, codigo: str, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    a = _ativo(conn, ativo_id, e)
    evs = [x for x in db.evidencias_do_ativo(conn, a["id"], limite=500) if x["codigo"] == codigo]
    return Historico(eventos=[_evento(x) for x in db.eventos(conn, a["id"], codigo, limite=30)],
                     evidencias=[_evidencia(x) for x in evs[:30]])


@rota.get("/obrigacoes/{codigo}/historico", response_model=list[VersaoObrigacao],
          summary="Todas as versões de uma obrigação, com a origem e quem decidiu")
def historico(codigo: str, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    ob = conn.execute("SELECT empresa, norma FROM obrigacao WHERE codigo = ?", (codigo,)).fetchone()
    h = db.historico(conn, codigo) if ob is not None and e.ve_obrigacao(ob["empresa"]) else []
    if not h:       # obrigação própria de outra cliente: 404, como se não existisse
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"obrigação {codigo} não existe")
    from .regulatorio import CAMPO, _texto

    def _alt(c: str, antes, depois) -> Alteracao:
        return Alteracao(campo=c, rotulo=CAMPO.get(c, c), antes=_texto(c, antes), depois=_texto(c, depois))

    out, anterior = [], None
    for v in h:
        correcao = json.loads(v["correcao"]) if v.get("correcao") else None
        out.append(VersaoObrigacao(
            **{k: v.get(k) for k in VersaoObrigacao.model_fields if k in v and k not in ("correcao", "mudou", "corrigido")},
            agenda_descricao=agenda.descrever(v["agenda"]) if v.get("agenda") else "",
            correcao=correcao, ato_nome=torre.nome_ato(v.get("ato")), norma=ob["norma"],
            dispositivo=torre.dispositivo(ob["norma"], v.get("artigo")),
            mudou=[_alt(c, a, b) for c, (a, b) in db.diferencas(anterior, v).items()] if anterior else [],
            corrigido=[_alt(c, p, a) for c, (p, a) in (correcao or {}).items()]))
        anterior = v
    return out


@rota.get("/empresas/{empresa_id}/obrigacoes", response_model=list[ObrigacaoResumo],
          summary="Obrigações que valem (ou vão valer) para os ativos que a sessão vê, as que mudaram primeiro")
def obrigacoes(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    codigos = sorted({o.codigo for a in _ativos_visiveis(conn, e, empresa_id)
                      for o in db.obrigacoes_do_ativo(conn, a["id"])})
    if not codigos:
        return []
    marcas = ",".join("?" * len(codigos))
    rows = conn.execute(
        "SELECT o.codigo, o.norma, COUNT(v.id) AS versoes, "
        "MAX(CASE WHEN v.status = 'vigente' THEN v.titulo END) AS vigente, MAX(v.titulo) AS qualquer "
        f"FROM obrigacao o JOIN obrigacao_versao v ON v.obrigacao_id = o.id WHERE o.codigo IN ({marcas}) "
        "GROUP BY o.codigo, o.norma", codigos).fetchall()
    out = [ObrigacaoResumo(codigo=r["codigo"], titulo=r["vigente"] or r["qualquer"], norma=r["norma"],
                           versoes=r["versoes"], mudou=r["versoes"] > 1) for r in rows]
    return sorted(out, key=lambda o: (not o.mudou, o.codigo))


@rota.get("/empresas/{empresa_id}/calendario", response_model=list[Vencimento],
          summary="Vencimentos do mês, período a período")
def calendario_mes(empresa_id: int, ano: int, mes: int = Query(ge=1, le=12), hoje: date | None = None,
                   ativo: list[str] | None = Query(None, description="só estes ativos (códigos)"),
                   e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    linhas = _visiveis(conn, e, empresa_id, hoje or hoje_padrao(), desde_padrao(emp))
    if ativo:
        linhas = [l for l in linhas if l.ativo in ativo]
    return [Vencimento(dia=v.dia, periodo=v.periodo, periodo_rotulo=agenda.rotulo_humano(v.periodo),
                       entregue=v.entregue, ativo=v.linha.ativo, ativo_id=v.linha.ativo_id, codigo=v.linha.codigo,
                       titulo=v.linha.titulo, status=v.linha.status, responsavel=v.linha.responsavel)
            for v in operacao.vencimentos_no_mes(conn, linhas, ano, mes)]


@rota.get("/empresas/{empresa_id}/transicao", response_model=list[Troca],
          summary="O que sai, o que entra e o que continua na troca de norma")
def transicao(empresa_id: int, dia: date = date(2027, 8, 2), e: Escopo = Depends(regulatorio),
              conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    visiveis = {a["codigo"]: a for a in db.ativos(conn, empresa_id) if e.ve_ativo(a)}
    out = []
    novas = torre._comecam_em(conn, dia, empresa_id)
    for t in torre.transicao(conn, empresa_id, dia):
        if t.ativo not in visiveis:
            continue
        a = visiveis[t.ativo]
        out.append(Troca(ativo=t.ativo, ativo_nome=a["nome"], responsavel=a["responsavel"], saem=len(t.saem),
                         entram=len(t.entram), temas=[
            TemaTroca(tema=p.tema, situacao=p.situacao, saem=[_obrigacao(o) for o in p.saem],
                      entram=[_obrigacao(o) for o in p.entram], so_para_outros=[_obrigacao(o) for o in p.so_para_outros])
            for p in torre.pares(t, conn, dia, novas)]))
    return out


@rota.get("/empresas/{empresa_id}/plano-transicao", summary="Plano de transição (Markdown ou PDF), por quem olha")
def plano_transicao(empresa_id: int, formato: str = Query("md", pattern="^(md|pdf)$"), dia: date = date(2027, 8, 2),
                    hoje: date | None = None, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    para = None if e.ve_tudo else e.area
    md = torre.plano_transicao(conn, empresa_id, dia, hoje or hoje_padrao(), responsavel=para)
    if formato == "pdf":
        return Response(pdf.de_markdown(md, f"Plano de transição · {para or 'Diretoria'}"), media_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="plano_transicao.pdf"'})
    return Response(md, media_type="text/markdown; charset=utf-8")


@rota.get("/empresas/{empresa_id}/linha-do-tempo", response_model=list[Futura],
          summary="Obrigações que passam a valer depois do dia")
def linha_do_tempo(empresa_id: int, hoje: date | None = None, e: Escopo = Depends(regulatorio),
                   conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    visiveis = {a["codigo"] for a in db.ativos(conn, empresa_id) if e.ve_ativo(a)}
    return [Futura(**asdict(f), dispositivo=torre.dispositivo(f.norma, f.artigo))
            for f in torre.futuras(conn, empresa_id, hoje or hoje_padrao()) if f.ativo in visiveis]


@rota.get("/empresas/{empresa_id}/vigencias", response_model=list[Faixa],
          summary="De quando a quando cada norma vale para cada ativo (as barras da linha do tempo)")
def vigencias(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    norma_de = {r["codigo"]: r["norma"] for r in conn.execute("SELECT codigo, norma FROM obrigacao")}
    faixas: dict[tuple[str, str], list[str]] = {}
    for a in db.ativos(conn, empresa_id):
        if not e.ve_ativo(a):
            continue
        for o in db.obrigacoes_do_ativo(conn, a["id"]):
            v = o.vigente
            if not v:
                continue
            k = (a["codigo"], norma_de.get(o.codigo) or "—")
            ini, fim = v["vigencia_desde"] or "", v["vigencia_ate"] or "9999-12-31"
            faixas[k] = [min(faixas[k][0], ini), max(faixas[k][1], fim)] if k in faixas else [ini, fim]
    return [Faixa(ativo=at, norma=n, desde=ini or None, ate=None if fim == "9999-12-31" else fim)
            for (at, n), (ini, fim) in faixas.items()]


@rota.get("/empresas/{empresa_id}/boletim", summary="Boletim da semana (Markdown ou PDF), nunca enviado")
def boletim(empresa_id: int, formato: str = Query("md", pattern="^(md|pdf)$"), responsavel: str | None = None,
            hoje: date | None = None, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    if not e.ve_tudo:
        responsavel = e.area
    md = torre.boletim(conn, empresa_id, hoje or hoje_padrao(), desde_padrao(emp), responsavel=responsavel)
    if formato == "pdf":
        return Response(pdf.de_markdown(md, f"Boletim · {responsavel or 'Diretoria'}"), media_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="boletim.pdf"'})
    return Response(md, media_type="text/markdown; charset=utf-8")


@rota.get("/empresas/{empresa_id}/calendario.ics", summary="Vencimentos em .ics para a agenda (só download)")
def calendario_ics(empresa_id: int, responsavel: str | None = None, hoje: date | None = None,
                   e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    if not e.ve_tudo:
        responsavel = e.area
    ics = torre.calendario(conn, empresa_id, hoje or hoje_padrao(), desde_padrao(emp), responsavel=responsavel)
    return Response(ics, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="regulaia.ics"'})


@rota.get("/empresas/{empresa_id}/planilha", summary="As pendências em Excel (com os mesmos filtros da aba Entregas)")
def planilha(empresa_id: int, hoje: date | None = None,
             status_: list[str] | None = Query(None, alias="status"), ativo: list[str] | None = Query(None),
             norma: list[str] | None = Query(None), responsavel: list[str] | None = Query(None),
             busca: str | None = None, vence_ate: date | None = None,
             e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    linhas = _visiveis(conn, e, empresa_id, hoje or hoje_padrao(), desde_padrao(emp))
    termo = (busca or "").strip().lower()
    linhas = [l for l in linhas
              if (not status_ or l.status in status_) and (not ativo or l.ativo in ativo)
              and (not norma or l.norma in norma) and (not responsavel or (l.responsavel or "") in responsavel)
              and (not termo or termo in f"{l.titulo} {l.codigo} {l.norma} {l.evidencia}".lower())
              and (not vence_ate or (l.vence and l.vence <= vence_ate.isoformat()))]
    return Response(operacao.planilha(linhas, emp["nome"]),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="regulaia.xlsx"'})


@rota.get("/entregas/periodo", response_model=PeriodoEntrega,
          summary="Qual período uma entrega feita no dia comprova (para mostrar antes de registrar)")
def periodo_da_entrega(ativo_id: int, codigo: str, dia: date | None = None, e: Escopo = Depends(regulatorio),
                       conn=Depends(conexao)):
    a = _ativo(conn, ativo_id, e)
    emp = empresa_visivel(conn, e, a["empresa_id"])
    dia = dia or hoje_padrao()
    linhas = [l for l in _visiveis(conn, e, emp["id"], dia, desde_padrao(emp), ativo=a["codigo"]) if l.codigo == codigo]
    if not linhas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{codigo} não vale para {a['codigo']} em {dia}")
    periodo = operacao.periodo_para_entrega(linhas[0], dia)
    return PeriodoEntrega(periodo=periodo, rotulo=agenda.rotulo_humano(periodo))


# ------------------------------------------------------------------ escrita


@rota.post("/comprovantes", status_code=201, response_model=Comprovante,
           summary="Guardar o comprovante de uma entrega (pasta local ou S3) antes de registrá-la")
async def comprovante(request: Request, ativo_id: int, arquivo: UploadFile = File(...),
                      e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    a = _ativo(conn, ativo_id, e)
    dados = await arquivo.read(LIMITE_COMPROVANTE + 1)
    if len(dados) > LIMITE_COMPROVANTE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "comprovante maior que 20 MB")
    if not dados:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "arquivo vazio")
    sha = hashlib.sha256(dados).hexdigest()
    nome = arquivo.filename or "comprovante"
    guardado = armazenamento.guardar(request.app.state.cfg, sha, nome, dados, tipo=arquivo.content_type)
    auditoria.registrar(conn, request, "comprovante", f"{a['codigo']}/{nome}", {"sha256": sha})
    return Comprovante(arquivo=nome, guardado_em=guardado, sha256=sha)


@rota.post("/entregas", status_code=201, response_model=EntregaFeita,
           summary="Registrar a entrega de um período (com ou sem comprovante)")
def entregar(dados: Entrega, request: Request, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    a = _ativo(conn, dados.ativo_id, e)
    emp = empresa_visivel(conn, e, a["empresa_id"])
    dia = dados.dia or hoje_padrao()
    linhas = [l for l in _visiveis(conn, e, emp["id"], dia, desde_padrao(emp), ativo=a["codigo"])
              if l.codigo == dados.codigo]
    if not linhas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{dados.codigo} não vale para {a['codigo']} em {dia}")
    periodo = dados.periodo or operacao.periodo_para_entrega(linhas[0], dia)
    try:
        eid = db.entregar(conn, a["id"], dados.codigo, periodo, dia=dia.isoformat(), por=e.assinante,
                          arquivo=dados.arquivo, obs=dados.obs)
    except db.ErroCadastro as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "entrega", f"{a['codigo']}/{dados.codigo}", {"periodo": periodo})
    return EntregaFeita(evidencia_id=eid, periodo=periodo, periodo_rotulo=agenda.rotulo_humano(periodo))


@rota.delete("/entregas", response_model=Ok, summary="Desfazer uma entrega registrada por engano")
def desfazer(ativo_id: int, codigo: str, periodo: str, request: Request, e: Escopo = Depends(regulatorio),
             conn=Depends(conexao)):
    a = _ativo(conn, ativo_id, e)
    if not db.desfazer_entrega(conn, a["id"], codigo, periodo, por=e.assinante):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "não havia entrega desse período")
    auditoria.registrar(conn, request, "entrega_desfeita", f"{a['codigo']}/{codigo}", {"periodo": periodo})
    return Ok(ok=True)


@rota.post("/atribuicoes", response_model=Ok, summary="Passar uma obrigação para outra área")
def atribuir(dados: Atribuicao, request: Request, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    a = _ativo(conn, dados.ativo_id, e)
    db.atribuir(conn, a["id"], dados.codigo, dados.responsavel.strip(), por=e.assinante)
    auditoria.registrar(conn, request, "atribuicao", f"{a['codigo']}/{dados.codigo}", {"para": dados.responsavel})
    return Ok(ok=True)


@rota.post("/comentarios", status_code=201, response_model=Ok, summary="Comentar uma obrigação ou o ativo")
def comentar(dados: Comentario, request: Request, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    a = _ativo(conn, dados.ativo_id, e)
    db.registrar_evento(conn, a["id"], dados.codigo, "comentario", dados.texto, e.assinante)
    auditoria.registrar(conn, request, "comentario", f"{a['codigo']}/{dados.codigo or '-'}")
    return Ok(ok=True)


@rota.patch("/ativos/{ativo_id}/atributos", summary="Completar ou corrigir o cadastro do ativo")
def atributos(ativo_id: int, dados: Atributos, request: Request, e: Escopo = Depends(regulatorio),
              conn=Depends(conexao)) -> dict:
    a = _ativo(conn, ativo_id, e)
    novo = db.atualizar_atributos(conn, a["id"], dados.atributos, por=e.assinante)
    auditoria.registrar(conn, request, "cadastro", a["codigo"], dados.atributos)
    return novo


@rota.put("/ativos/{ativo_id}/responsavel", response_model=Mudou, summary="Qual área responde pelo ativo (Diretoria)")
def responsavel(ativo_id: int, dados: Responsavel, request: Request, e: Escopo = Depends(diretoria),
                conn=Depends(conexao)):
    a = _ativo(conn, ativo_id, e)
    mudou = db.definir_responsavel(conn, a["id"], dados.area, por=e.assinante)
    auditoria.registrar(conn, request, "responsavel_ativo", a["codigo"], {"area": dados.area})
    return Mudou(mudou=mudou)
