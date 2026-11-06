"""Servidor MCP da RegulaIA: um agente (Claude, ou qualquer cliente MCP) consulta a torre.

Só leitura. O agente explica, cruza e prioriza; quem decide é gente, na torre: aprovar mudança de norma,
registrar entrega e mexer no cadastro continuam nos botões, com nome na auditoria. A única ferramenta que
chama IA (`analisar_ato`) não grava nada: mostra o que mudaria e a conferência do Python.

Uso:
    REGULAIA_TOKEN_SERVICO=... uv run python -m agente            # stdio (Claude Desktop)
    REGULAIA_TOKEN_SERVICO=... uv run python -m agente --http     # streamable HTTP na 8100
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from .cliente import ErroTorre, Torre

INSTRUCOES = """\
Você consulta a torre de controle regulatória da RegulaIA: para cada ativo de uma mineradora (barragens,
unidades, equipamentos, licenças), quais obrigações de cada norma valem, quando vencem e se estão em dia.

- Toda obrigação tem norma, dispositivo (artigo/item) e o trecho literal da norma: cite-os ao responder.
- Status: atrasada, dado_faltando (falta um dado do ativo para saber se a obrigação vale), vence_logo,
  em_dia, gatilho (depende de um evento, sem calendário).
- "hoje" (AAAA-MM-DD) muda o dia da consulta: serve para ver o futuro (ex.: quando a Res. ANM 220/2025
  passa a valer, em 2027-08-02). Sem "hoje", vale o dia padrão da torre.
- Você não decide nem grava: para aprovar uma mudança ou registrar uma entrega, diga onde fazer na torre.
- Se faltar dado, diga que falta; não presuma.
"""

LEITURA = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
PENDENTES = ("atrasada", "dado_faltando", "vence_logo")

Empresa = Annotated[str | None, Field(description="Nome ou id da empresa; vazio se só houver uma no escopo")]
Hoje = Annotated[str | None, Field(description="Dia da consulta, AAAA-MM-DD (vazio: o dia padrão da torre)")]


def _linha(l: dict, com_trecho: bool = True) -> dict:
    out = {
        "ativo": l["ativo"], "obrigacao": l["codigo"], "titulo": l["titulo"], "norma": l["norma"],
        "dispositivo": l.get("dispositivo") or l.get("artigo"), "status": l["status"],
        "vence": l.get("vence"), "area": l.get("area"), "responsavel": l.get("responsavel"),
    }
    if l.get("faltando_rotulos"):
        out["periodos_faltando"] = l["faltando_rotulos"]
    if l.get("dados_faltando_rotulos"):
        out["dados_faltando"] = l["dados_faltando_rotulos"]
    if l.get("mudanca_pendente"):
        out["mudanca_pendente"] = True
    if com_trecho and l.get("trecho"):
        out["trecho"] = l["trecho"]
    return out


def criar_servidor(torre: Torre) -> MCPServer:
    mcp = MCPServer(name="RegulaIA", title="RegulaIA: torre de controle regulatória",
                    instructions=INSTRUCOES, version="1.0.0")

    @mcp.tool(annotations=LEITURA)
    def empresas() -> list[dict]:
        """Empresas que este agente enxerga (id, nome, se é fictícia, de onde veio)."""
        return [{"id": e["id"], "nome": e["nome"], "ficticia": e.get("ficticia"), "origem": e.get("origem")}
                for e in torre.empresas()]

    @mcp.tool(annotations=LEITURA)
    def pendencias(empresa: Empresa = None, hoje: Hoje = None,
                   ativo: Annotated[str | None, Field(description="Código do ativo (ex.: B1)")] = None,
                   status: Annotated[list[str] | None, Field(
                       description="Filtrar status; padrão: atrasada, dado_faltando, vence_logo")] = None) -> dict:
        """O que precisa de ação: contagem por status e cada pendência com norma, dispositivo, vencimento,
        períodos ou dados que faltam e o trecho literal da norma."""
        eid = torre.empresa_id(empresa)
        ativo_id = torre.ativo(eid, ativo)["id"] if ativo else None
        p = torre.get(f"/empresas/{eid}/painel", hoje=hoje, ativo=ativo_id)
        quero = set(status or PENDENTES)
        return {"hoje": p["hoje"], "contagem": p["contagem"],
                "pendencias": [_linha(l) for l in p["linhas"] if l["status"] in quero]}

    @mcp.tool(annotations=LEITURA)
    def ativos(empresa: Empresa = None, hoje: Hoje = None) -> list[dict]:
        """Ativos da empresa com o cadastro (atributos) e a contagem de obrigações por status."""
        eid = torre.empresa_id(empresa)
        return [{"codigo": a["codigo"], "nome": a["nome"], "tipo": a["tipo"], "responsavel": a.get("responsavel"),
                 "contagem": a.get("contagem"), "atributos": a.get("atributos")}
                for a in torre.get(f"/empresas/{eid}/ativos", hoje=hoje)]

    @mcp.tool(annotations=LEITURA)
    def ficha_do_ativo(ativo: Annotated[str, Field(description="Código do ativo (ex.: B2)")],
                       empresa: Empresa = None, hoje: Hoje = None) -> dict:
        """Tudo de um ativo: cadastro, cada obrigação que vale (com status e trecho), as últimas evidências
        recebidas e o histórico (entregas, comentários, mudanças de responsável)."""
        eid = torre.empresa_id(empresa)
        f = torre.get(f"/ativos/{torre.ativo(eid, ativo)['id']}", hoje=hoje)
        a = f["ativo"]
        return {"ativo": {"codigo": a["codigo"], "nome": a["nome"], "tipo": a["tipo"],
                          "responsavel": a.get("responsavel"), "atributos": a.get("atributos")},
                "obrigacoes": [_linha(l) for l in f["linhas"]],
                "evidencias": [{"obrigacao": e["codigo"], "periodo": e.get("periodo_rotulo") or e.get("periodo"),
                                "recebida_em": e.get("recebida_em"), "origem": e.get("origem")}
                               for e in f["evidencias"][:30]],
                "historico": [{"em": e["em"], "tipo": e["tipo"], "obrigacao": e.get("codigo"),
                               "texto": e.get("texto"), "por": e.get("por")} for e in f["eventos"][:30]]}

    @mcp.tool(annotations=LEITURA)
    def obrigacoes(empresa: Empresa = None,
                   busca: Annotated[str | None, Field(description="Texto no título, código ou norma")] = None) -> list[dict]:
        """Catálogo de obrigações que valem (ou vão valer) para os ativos da empresa, com quantas versões cada
        uma teve e se mudou por ato novo."""
        eid = torre.empresa_id(empresa)
        todas = torre.get(f"/empresas/{eid}/obrigacoes")
        if busca:
            b = busca.casefold()
            todas = [o for o in todas if b in f"{o['codigo']} {o['titulo']} {o['norma']}".casefold()]
        return todas

    @mcp.tool(annotations=LEITURA)
    def historico_da_obrigacao(codigo: Annotated[str, Field(description="Código da obrigação (ex.: OB-01)")]) -> list[dict]:
        """Todas as versões de uma obrigação: o que mudou, por qual ato, quem decidiu e quando."""
        return torre.get(f"/obrigacoes/{codigo.strip().upper()}/historico")

    @mcp.tool(annotations=LEITURA)
    def mudancas_pendentes(empresa: Empresa = None) -> list[dict]:
        """Mudanças propostas por atos novos (DOU) aguardando decisão humana: antes/depois, trecho do ato,
        conferência do Python e quem decide."""
        eid = torre.empresa_id(empresa)
        return [{"versao_id": m["versao_id"], "obrigacao": m["codigo"], "titulo": m["titulo"], "ato": m["ato"],
                 "diferencas": m["diferencas"], "trecho_do_ato": m.get("trecho"), "conferencia": m.get("conferencia"),
                 "ativos": m.get("ativos"), "quem_decide": m.get("quem_decide")}
                for m in torre.get(f"/empresas/{eid}/mudancas")]

    @mcp.tool(annotations=LEITURA)
    def linha_do_tempo(empresa: Empresa = None, hoje: Hoje = None,
                       ate: Annotated[str | None, Field(description="Só até este dia (AAAA-MM-DD)")] = None) -> list[dict]:
        """Obrigações que passam a valer depois de hoje, por dia e ativo (ex.: a troca da Res. 95 pela 220,
        a ZAS da NR-22). 'proposta' marca data que vem de mudança ainda não aprovada."""
        eid = torre.empresa_id(empresa)
        futuras = torre.get(f"/empresas/{eid}/linha-do-tempo", hoje=hoje)
        return [f for f in futuras if not ate or f["dia"] <= ate]

    @mcp.tool(annotations=LEITURA)
    def boletim(empresa: Empresa = None, hoje: Hoje = None,
                responsavel: Annotated[str | None, Field(description="Área ou gestor (vazio: todos)")] = None) -> str:
        """Boletim da semana em Markdown: atrasadas, o que vence em 30 dias, dado faltando e mudanças
        aguardando decisão, com norma e dispositivo. Não envia nada."""
        eid = torre.empresa_id(empresa)
        return torre.get(f"/empresas/{eid}/boletim", formato="md", responsavel=responsavel, hoje=hoje)

    @mcp.tool(annotations=LEITURA)
    def radar_do_dou() -> dict:
        """O radar do Diário Oficial: funil do mês (atos lidos, da ANM, candidatos, mudanças), as análises
        feitas e o custo real da IA."""
        r = torre.get("/radar")
        return {"funil": r["funil"], "custo_ia": r["custo_ia"],
                "analises": [{"ato": a.get("ato"), "candidatas": a.get("candidatas"), "motivo": a.get("motivo"),
                              "mudancas": a.get("mudancas")} for a in r["analises"]]}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True,
                                          openWorldHint=True))
    def analisar_ato(texto: Annotated[str, Field(description="Texto integral do ato normativo")],
                     identificacao: Annotated[str | None, Field(description="Ex.: Resolução ANM nº 250/2026")] = None
                     ) -> dict:
        """Analisa um ato contra o catálogo: triagem por regra, IA só nas obrigações candidatas e conferência
        do Python (data e trecho citados existem no ato). Não grava: mandar para decisão é na torre."""
        a = torre.post("/radar/analise", {"identificacao": identificacao, "texto": texto})
        return {"ato": a["ato"], "candidatas": a["candidatas"], "motivo": a["motivo"], "confianca": a["confianca"],
                "mudancas": a["mudancas"], "aprovadas_pela_conferencia": a.get("aprovadas"),
                "revisao_humana": a["revisao_humana"], "custo_usd": a["custo_usd"]}

    return mcp


__all__ = ["ErroTorre", "Torre", "criar_servidor"]
