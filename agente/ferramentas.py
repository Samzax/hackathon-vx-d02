"""As ferramentas de leitura da torre, sem depender do MCP.

Servem a dois clientes: o servidor MCP (`agente/servidor.py`, do lado de quem usa, com o token de serviço)
e o "Assistente Mitra" do front (`mitra/pergunta.py` pela rota da API, com a sessão de quem pergunta).
As duas pontas falam com a torre só pela API (`Torre`), então valem as mesmas regras de acesso.

Sem `from __future__ import annotations`: as anotações ficam como objetos, e o MCP e o Pydantic leem o
esquema de cada ferramenta direto da assinatura, mesmo quando a função é embrulhada em outro módulo.
"""

from collections.abc import Callable
from typing import Annotated

from pydantic import Field

from .cliente import ErroTorre, NaoEncontrado, Torre

INSTRUCOES = """\
Você consulta a torre de controle regulatória da Mitra: para cada ativo de uma mineradora (barragens,
unidades, equipamentos, licenças), quais obrigações de cada norma valem, quando vencem e se estão em dia.

- Toda obrigação tem norma, dispositivo (artigo/item) e o trecho literal da norma: cite-os ao responder.
- Status: atrasada, dado_faltando (falta um dado do ativo para saber se a obrigação vale), vence_logo,
  em_dia, gatilho (depende de um evento, sem calendário).
- "hoje" (AAAA-MM-DD) muda o dia da consulta: serve para ver o futuro (ex.: quando a Res. ANM 220/2025
  passa a valer, em 2027-08-02). Sem "hoje", vale o dia padrão da torre.
- Você não decide nem grava: para aprovar uma mudança ou registrar uma entrega, diga onde fazer na torre.
- Cobertura normativa: jurisdição sem fonte automática é "cobertura não verificada", nunca "coberta"; e mesmo
  a coberta tem lacunas conhecidas (cite-as). Norma "esperando curadoria" ainda não está no catálogo.
- Se faltar dado, diga que falta; não presuma.
"""

PENDENTES = ("atrasada", "dado_faltando", "vence_logo")
# a única que faz POST e chama IA (não grava, mas gasta): fora do chat, que já é uma chamada de IA
CHAMA_IA = {"analisar_ato"}

Empresa = Annotated[str | None, Field(description="Nome ou id da empresa; vazio se só houver uma no escopo")]
Hoje = Annotated[str | None, Field(description="Dia da consulta, AAAA-MM-DD (vazio: o dia padrão da torre)")]


def _linha(l: dict, com_trecho: bool = True) -> dict:
    out = {
        "ativo": l["ativo"], "obrigacao": l["codigo"], "titulo": l["titulo"], "norma": l["norma"],
        "dispositivo": l.get("dispositivo") or l.get("artigo"), "status": l["status"],
        "vence": l.get("vence"), "area": l.get("area"), "responsavel": l.get("responsavel"),
    }
    # os rótulos legíveis ("1ª quinzena de out/2026") vêm nas versões novas da API; senão, o código do período
    if faltando := l.get("faltando_rotulos") or l.get("faltando"):
        out["periodos_faltando"] = faltando
    if dados := l.get("dados_faltando_rotulos") or l.get("dados_faltando"):
        out["dados_faltando"] = dados
    if l.get("mudanca_pendente"):
        out["mudanca_pendente"] = True
    if com_trecho and l.get("trecho"):
        out["trecho"] = l["trecho"]
    return out


def _norma_descoberta(n: dict) -> dict:
    out = {"norma": n["titulo"], "ementa": n["ementa"][:400], "deveres": n.get("deveres") or None,
           "texto_oficial": n.get("url")}
    if n.get("cita_catalogo"):          # altera ou regulamenta norma do catálogo: o consolidado pode já ter
        out["altera_do_catalogo"] = n["cita_catalogo"]
    return out


def ferramentas(torre: Torre) -> list[Callable]:
    """As ferramentas ligadas a uma `Torre` (a docstring de cada uma é a descrição que o modelo lê)."""

    def empresas() -> list[dict]:
        """Empresas que este agente enxerga (id, nome, setor, se é fictícia, de onde veio)."""
        return [{"id": e["id"], "nome": e["nome"], "setor": e.get("setor"), "ficticia": e.get("ficticia"),
                 "origem": e.get("origem")}
                for e in torre.empresas()]

    def instanciacao(empresa: Empresa = None) -> dict:
        """Em que pé está a instanciação da empresa: cada etapa (título, estado, o que falta nela e quem mexeu
        por último), o percentual, se já entrou em operação e desde quando a torre cobra, e os dados que faltam
        no cadastro dos ativos (o que perguntar e quais obrigações dependem do dado)."""
        eid = torre.empresa_id(empresa)
        try:
            e = torre.get(f"/empresas/{eid}/instanciacao")
        except NaoEncontrado:
            # a empresa existe (empresa_id já a achou): o 404 aqui é da instanciação, que ela não tem
            alvo = f"A empresa {empresa}" if empresa else "A empresa"
            raise ErroTorre(f"{alvo} não passou pela instanciação (entrou na torre por outro caminho): não há "
                            "etapas para contar; o que falta no cadastro dos ativos aparece na ficha de "
                            "cada um.") from None
        faltando = torre.get(f"/empresas/{eid}/dados-faltando")
        return {"empresa": e["empresa"], "percentual": e["percentual"], "em_operacao": e["em_operacao"],
                "monitorado_desde": e["monitorado_desde"],
                "etapas": [{"titulo": x["titulo"], "estado": x["estado"], "falta": x["falta"],
                            "numeros": x["numeros"], "por": x.get("por")} for x in e["etapas"]],
                "dados_faltando": {"total": len(faltando),
                                   "itens": [{"ativo": d["ativo"], "pergunta": d["pergunta"],
                                              "obrigacoes": d["obrigacoes"]} for d in faltando]}}

    def pendencias(empresa: Empresa = None, hoje: Hoje = None,
                   ativo: Annotated[str | None, Field(description="Código do ativo (ex.: B1)")] = None,
                   status: Annotated[list[str] | None, Field(
                       description="Filtrar status; padrão: atrasada, dado_faltando, vence_logo")] = None) -> dict:
        """O que precisa de ação: contagem por status e cada pendência com norma, dispositivo, vencimento,
        períodos ou dados que faltam e o trecho literal da norma."""
        eid = torre.empresa_id(empresa)
        # o painel filtra pelo código do ativo (B3), não pelo id; torre.ativo confere que ele existe no escopo
        codigo = torre.ativo(eid, ativo)["codigo"] if ativo else None
        p = torre.get(f"/empresas/{eid}/painel", hoje=hoje, ativo=codigo)
        quero = set(status or PENDENTES)
        return {"hoje": p["hoje"], "contagem": p["contagem"],
                "pendencias": [_linha(l) for l in p["linhas"] if l["status"] in quero]}

    def ativos(empresa: Empresa = None, hoje: Hoje = None) -> list[dict]:
        """Ativos da empresa com o cadastro (atributos) e a contagem de obrigações por status."""
        eid = torre.empresa_id(empresa)
        return [{"codigo": a["codigo"], "nome": a["nome"], "tipo": a["tipo"], "responsavel": a.get("responsavel"),
                 "contagem": a.get("contagem"), "atributos": a.get("atributos")}
                for a in torre.get(f"/empresas/{eid}/ativos", hoje=hoje)]

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

    def historico_da_obrigacao(codigo: Annotated[str, Field(description="Código da obrigação (ex.: OB-01)")]) -> list[dict]:
        """Todas as versões de uma obrigação: o que mudou, por qual ato, quem decidiu e quando."""
        # agente preso a uma empresa: obrigação própria de outra cliente responde "não encontrado"
        empresa_id = torre.empresa_id(None) if torre.empresa_fixa else None
        return torre.get(f"/obrigacoes/{codigo.strip().upper()}/historico", empresa_id=empresa_id)

    def mudancas_pendentes(empresa: Empresa = None) -> list[dict]:
        """Mudanças propostas por atos novos (DOU) aguardando decisão humana: antes/depois, trecho do ato,
        conferência do Python e quem decide."""
        eid = torre.empresa_id(empresa)
        return [{"versao_id": m["versao_id"], "obrigacao": m["codigo"], "titulo": m["titulo"], "ato": m["ato"],
                 "diferencas": m["diferencas"], "trecho_do_ato": m.get("trecho"), "conferencia": m.get("conferencia"),
                 "ativos": m.get("ativos"), "quem_decide": m.get("quem_decide")}
                for m in torre.get(f"/empresas/{eid}/mudancas")]

    def linha_do_tempo(empresa: Empresa = None, hoje: Hoje = None,
                       ate: Annotated[str | None, Field(description="Só até este dia (AAAA-MM-DD)")] = None) -> list[dict]:
        """Obrigações que passam a valer depois de hoje, por dia e ativo (ex.: a troca da Res. 95 pela 220,
        a ZAS da NR-22). 'proposta' marca data que vem de mudança ainda não aprovada."""
        eid = torre.empresa_id(empresa)
        futuras = torre.get(f"/empresas/{eid}/linha-do-tempo", hoje=hoje)
        if ate and len(ate) == 4:       # "2027" e "2027-12" valem como o fim do ano e do mês
            ate += "-12-31"
        elif ate and len(ate) == 7:
            ate += "-31"
        # sem o norma_link: a troca 95 -> 220 são dezenas de linhas com o mesmo endereço longo, e o resultado
        # passaria do limite que vai para o modelo (a torre mostra o link na tela)
        return [{k: v for k, v in f.items() if k != "norma_link"} for f in futuras if not ate or f["dia"] <= ate]

    def boletim(empresa: Empresa = None, hoje: Hoje = None,
                responsavel: Annotated[str | None, Field(description="Área ou gestor (vazio: todos)")] = None) -> str:
        """Boletim da semana em Markdown: atrasadas, o que vence em 30 dias, dado faltando e mudanças
        aguardando decisão, com norma e dispositivo. Não envia nada."""
        eid = torre.empresa_id(empresa)
        return torre.get(f"/empresas/{eid}/boletim", formato="md", responsavel=responsavel, hoje=hoje)

    def cobertura_normativa(
            empresa: Empresa = None,
            jurisdicao: Annotated[str | None, Field(description="BR (federal) ou a UF, ex.: MG")] = None,
            tipo_ativo: Annotated[str | None, Field(description="barragem, unidade ou equipamento")] = None,
    ) -> list[dict]:
        """Que normas valem para os ativos da empresa e quais ainda não estão no catálogo, por jurisdição e
        tipo de ativo: as normas catalogadas, as fontes oficiais lidas (e até que ano), as lacunas conhecidas,
        as normas já publicadas que a IA achou relevantes e esperam a curadoria Mitra, e as aprovadas que
        esperam a extração das obrigações. Ex.: "que normas valem para as minhas barragens em MG?"."""
        eid = torre.empresa_id(empresa)
        jur = (jurisdicao or "").strip().upper()
        tipo = (tipo_ativo or "").strip().lower()
        out = []
        for i in torre.get(f"/empresas/{eid}/cobertura"):
            if (jur and i["jurisdicao"] != jur) or (tipo and i["tipo_ativo"] != tipo):
                continue
            out.append({
                "jurisdicao": i["jurisdicao"], "jurisdicao_nome": i["jurisdicao_nome"], "tipo_ativo": i["tipo_ativo"],
                "ativos": i["ativos"], "estado": i["estado_rotulo"], "verificada": i["verificada"],
                "no_catalogo": i["catalogadas"],
                "fontes_lidas": [f"{f['nome']} ({f['cobre']}), {f['desde']}–{f['ate']}, lida em {f['em'][:16]} UTC"
                                 for f in i["fontes"]],
                "lacunas_conhecidas": i["lacunas"],
                "esperando_triagem": i["triagem_pendente"],
                "fora_do_catalogo_esperando_curadoria": [_norma_descoberta(n) for n in i["em_curadoria"]],
                "aprovadas_falta_extrair": [_norma_descoberta(n) for n in i["aprovadas"]],
            })
        return out

    def radar_do_dou() -> dict:
        """O radar do Diário Oficial: funil do mês (atos lidos, da ANM, candidatos, mudanças), as análises
        feitas e o custo real da IA."""
        r = torre.get("/radar")
        return {"funil": r["funil"], "custo_ia": r["custo_ia"],
                "analises": [{"ato": a.get("ato"), "candidatas": a.get("candidatas"), "motivo": a.get("motivo"),
                              "mudancas": a.get("mudancas")} for a in r["analises"]]}

    def analisar_ato(texto: Annotated[str, Field(description="Texto integral do ato normativo")],
                     identificacao: Annotated[str | None, Field(description="Ex.: Resolução ANM nº 250/2026")] = None
                     ) -> dict:
        """Analisa um ato contra o catálogo: triagem por regra, IA só nas obrigações candidatas e conferência
        do Python (data e trecho citados existem no ato). Não grava na torre: mandar para decisão é lá.
        Chama a IA (tem custo); agente preso a uma empresa analisa só contra o catálogo dela."""
        corpo: dict = {"identificacao": identificacao, "texto": texto}
        if torre.empresa_fixa:          # nunca a condicionante de outra cliente na análise
            corpo["empresa_id"] = torre.empresa_id(None)
        a = torre.post("/radar/analise", corpo)
        return {"ato": a["ato"], "candidatas": a["candidatas"], "motivo": a["motivo"], "confianca": a["confianca"],
                "mudancas": a["mudancas"], "aprovadas_pela_conferencia": a.get("aprovadas"),
                "revisao_humana": a["revisao_humana"], "custo_usd": a["custo_usd"]}

    return [empresas, instanciacao, pendencias, ativos, ficha_do_ativo, obrigacoes, historico_da_obrigacao,
            mudancas_pendentes, linha_do_tempo, boletim, cobertura_normativa, radar_do_dou, analisar_ato]
