"""Analisador de impacto: um ato muda quais obrigações, e para quais ativos?

Fluxo:
  camada 0/1 (triagem.py) -> nenhuma obrigação tocada? fim, sem IA.
  camada 2 (modelo barato) -> Python confere cada mudança proposta.
  camada 3 (modelo forte)  -> só se a 2 teve baixa confiança ou mudança reprovada.
  Mudanças aprovadas pelo Python viram versões PENDENTES; uma pessoa decide.

Uso: uv run python -m regulaia.impacto data/raw/dou/S01082026.zip [AAAA-MM-DD]
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date

from . import agenda, db, triagem
from .ia import Roteador, SemProvedor

VERSAO_PROMPT = "impacto-v3"
CAMPOS = ("prazo", "vigencia_desde", "vigencia_ate", "periodicidade", "aplica_se_a", "titulo", "evidencia")
CAMPOS_DATA = ("prazo", "vigencia_desde", "vigencia_ate")
CONFIANCA_MINIMA = 0.7
CACHE_IA = db.ROOT / "data" / "cache_ia.db"

SISTEMA = """Você é analista de conformidade regulatória de barragens de mineração no Brasil.
Recebe um ATO publicado no Diário Oficial e uma lista de OBRIGAÇÕES do cadastro de uma empresa.
Diga quais campos de quais obrigações o ato altera.

Regras:
1. Aponte só mudanças que o texto do ato estabelece de forma expressa. Não deduza, não complete.
2. "trecho" é cópia literal, palavra por palavra, de uma passagem do ato que sustenta a mudança.
3. Datas no formato AAAA-MM-DD.
4. Ressalvas e exceções do ato decidem: se o ato exclui expressamente o caso, não há mudança.
5. Se o ato mantém um valor igual ao que já está no cadastro, isso não é mudança.
6. Campos que podem mudar: prazo, vigencia_desde, vigencia_ate, periodicidade, aplica_se_a, titulo, evidencia.
   vigencia_ate é o último dia em que a obrigação vale (use quando o ato revoga ou encerra a obrigação).
7. Se o ato muda a data de entrada em vigor e a obrigação tem prazo igual a essa data
   (a obrigação vence no dia em que começa a valer), aponte as duas mudanças: vigencia_desde e prazo.
8. Se nenhuma obrigação muda, devolva "mudancas": [] e explique em "motivo".

Responda só com um objeto JSON, sem texto fora dele:
{
  "mudancas": [
    {"obrigacao": "OB-00", "campo": "prazo", "valor_atual": "...", "valor_novo": "...",
     "trecho": "cópia literal do ato", "justificativa": "uma frase"}
  ],
  "motivo": "uma ou duas frases sobre o que o ato faz e por que muda ou não muda o cadastro",
  "confianca": 0.0
}"""


# --------------------------------------------------------------- conferência


def _limpo(texto: str) -> str:
    texto = texto.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", texto).strip().lower()


@dataclass
class Mudanca:
    obrigacao: str
    campo: str
    valor_atual: str | None
    valor_novo: str
    trecho: str
    justificativa: str = ""
    reprovada: str | None = None          # motivo, se o Python reprovou


def conferir(m: Mudanca, ato_texto: str, cadastro: dict[str, dict]) -> str | None:
    """Devolve o motivo da reprovação, ou None se a mudança se sustenta."""
    if m.obrigacao not in cadastro:
        return f"{m.obrigacao} não estava entre as obrigações enviadas"
    if m.campo not in CAMPOS:
        return f"campo {m.campo!r} não pode mudar"
    if not m.trecho or _limpo(m.trecho) not in _limpo(ato_texto):
        return "o trecho citado não existe no ato"
    if str(cadastro[m.obrigacao].get(m.campo)) == str(m.valor_novo):
        return "o valor novo é igual ao atual"
    if m.campo in CAMPOS_DATA:
        try:
            novo = date.fromisoformat(m.valor_novo)
        except ValueError:
            return f"{m.valor_novo!r} não é data AAAA-MM-DD"
        if novo not in triagem.datas(m.trecho):
            return f"a data {novo.isoformat()} não aparece no trecho citado"
    return None


# ------------------------------------------------------------------ análise


@dataclass
class Analise:
    ato: str
    candidatas: list[triagem.Candidata]
    mudancas: list[Mudanca] = field(default_factory=list)
    motivo: str = ""
    confianca: float | None = None
    modelos: list[str] = field(default_factory=list)
    custo_usd: float = 0.0            # gasto nesta execução (resposta em cache não é paga de novo)
    custo_original_usd: float = 0.0   # quanto as respostas custaram quando foram pedidas pela primeira vez
    revisao_humana: bool = False      # a IA não chegou a uma resposta que o Python aprovasse

    @property
    def aprovadas(self) -> list[Mudanca]:
        return [m for m in self.mudancas if m.reprovada is None]

    @property
    def reprovadas(self) -> list[Mudanca]:
        return [m for m in self.mudancas if m.reprovada is not None]


def _mensagem(identificacao: str, ato_texto: str, cadastro: dict[str, dict]) -> str:
    obs = [
        {k: v for k, v in ob.items() if k in ("codigo", "artigo", "titulo", "aplica_se_a",
                                              "periodicidade", "prazo", "vigencia_desde", "vigencia_ate", "evidencia")}
        for ob in cadastro.values()
    ]
    return (f"ATO: {identificacao}\n\n{ato_texto}\n\n"
            f"OBRIGAÇÕES DO CADASTRO:\n{json.dumps(obs, ensure_ascii=False, indent=1)}")


def _ler(dados: dict, ato_texto: str, cadastro: dict[str, dict]) -> tuple[list[Mudanca], str, float]:
    mudancas = []
    for d in dados.get("mudancas") or []:
        m = Mudanca(
            obrigacao=str(d.get("obrigacao", "")),
            campo=str(d.get("campo", "")),
            valor_atual=d.get("valor_atual"),
            valor_novo=str(d.get("valor_novo", "")),
            trecho=str(d.get("trecho", "")),
            justificativa=str(d.get("justificativa", "")),
        )
        m.reprovada = conferir(m, ato_texto, cadastro)
        mudancas.append(m)
    try:
        confianca = float(dados.get("confianca", 0))
    except (TypeError, ValueError):
        confianca = 0.0
    return mudancas, str(dados.get("motivo", "")), confianca


def analisar(conn, roteador: Roteador, identificacao: str, ato_texto: str, empresa: str | None = None) -> Analise:
    """Sem `empresa`: o catálogo inteiro (radar da plataforma). Com `empresa` (o "teste com um ato"
    de uma cliente): só as normas públicas e as obrigações próprias dela, nada de outra cliente."""
    if empresa is None:
        rows = conn.execute("SELECT codigo FROM obrigacao ORDER BY codigo")
    else:
        rows = conn.execute("SELECT codigo FROM obrigacao WHERE empresa IS NULL OR empresa = ? ORDER BY codigo",
                            (empresa,))
    codigos = [r["codigo"] for r in rows]
    # o código só é único por empresa: a busca da versão vai no mesmo escopo da análise
    escopo = empresa if empresa is not None else db.QUALQUER
    vigentes = [v for c in codigos if (v := db.versao(conn, c, empresa=escopo))]
    cands = triagem.candidatas(ato_texto, vigentes)
    analise = Analise(identificacao, cands)
    if not cands:
        analise.motivo = "Nenhuma obrigação do cadastro é citada ou tem termos em comum com o ato (sem IA)."
        return analise

    cadastro = {c.codigo: db.versao(conn, c.codigo, empresa=escopo) for c in cands}
    usuario = _mensagem(identificacao, ato_texto, cadastro)
    for camada in (2, 3):
        try:
            r = roteador.pedir_json("impacto", camada, SISTEMA, usuario, VERSAO_PROMPT, max_tokens=8000)
        except SemProvedor as e:
            analise.modelos.append(f"camada {camada}: {e}")
            continue
        analise.modelos.append(r.modelo.rotulo + (" (cache)" if r.do_cache else ""))
        analise.custo_usd += 0.0 if r.do_cache else r.custo_usd
        analise.custo_original_usd += r.custo_usd or 0.0
        mudancas, motivo, confianca = _ler(r.dados, ato_texto, cadastro)
        analise.mudancas, analise.motivo, analise.confianca = mudancas, motivo, confianca
        if not analise.reprovadas and confianca >= CONFIANCA_MINIMA:
            analise.revisao_humana = False
            return analise
        analise.revisao_humana = True
    if not analise.motivo:
        # nenhuma camada respondeu: não dá para afirmar que o ato não muda nada
        analise.motivo = "Não foi possível analisar: nenhum modelo de IA disponível."
        analise.revisao_humana = True
    return analise


def aplicar(conn, analise: Analise, ato_id: int, empresa: str | None = None) -> list[int]:
    """Transforma as mudanças aprovadas em versões pendentes (uma por obrigação). `empresa` é o escopo
    em que os códigos foram analisados (o mesmo de `analisar`)."""
    escopo = empresa if empresa is not None else db.QUALQUER
    por_ob: dict[str, dict] = {}
    trechos: dict[str, list[str]] = {}
    for m in analise.aprovadas:
        por_ob.setdefault(m.obrigacao, {})[m.campo] = m.valor_novo
        trechos.setdefault(m.obrigacao, [])
        if m.trecho not in trechos[m.obrigacao]:
            trechos[m.obrigacao].append(m.trecho)
    ids = []
    for codigo, campos in por_ob.items():
        if "periodicidade" in campos and "agenda" not in campos:
            # a agenda que a torre usa acompanha a periodicidade nova (regra, não IA)
            atual = db.versao(conn, codigo, empresa=escopo)
            nova = agenda.agenda_para(campos["periodicidade"], atual["agenda"]) if atual else None
            if nova:
                campos["agenda"] = nova
        ids.append(db.propor_versao(
            conn, codigo, campos, ato_id=ato_id,
            trecho=" […] ".join(trechos[codigo]), fonte=analise.ato, empresa=escopo,
        ))
    return ids


# ---------------------------------------------------------------------- CLI


def main(argv: list[str]) -> int:
    from collector.xml_dou import load_month
    from . import demo

    if not argv:
        print(__doc__)
        return 2
    dia = date.fromisoformat(argv[1]) if len(argv) > 1 else None
    caminho = db.DB_PADRAO
    if caminho.exists():
        caminho.unlink()
    conn = db.conectar(caminho)
    ativos = demo.montar(conn)
    # O cache de IA fica num arquivo à parte: sobrevive à recriação do banco da demo,
    # não paga duas vezes e deixa a demo repetível sem internet.
    roteador = Roteador(db.conectar(CACHE_IA))
    print("Modelos disponíveis:",
          {c: [m.rotulo for m in roteador.candidatos(c)] for c in (2, 3)}, "\n")

    atos = [a for a in load_month(argv[0])
            if a.is_anm and a.is_normative and (dia is None or a.pub_date == dia)]
    for a in atos:
        an = analisar(conn, roteador, a.identifica, a.text)
        print(f"== {a.identifica} ({a.pub_date})")
        print(f"   candidatas: {', '.join(f'{c.codigo}({c.pontos})' for c in an.candidatas) or 'nenhuma'}")
        print(f"   modelos: {' -> '.join(an.modelos) or 'nenhum (sem IA)'} | custo US$ {an.custo_usd:.5f}"
              f" | confiança {an.confianca}")
        print(f"   motivo: {an.motivo}")
        for m in an.mudancas:
            status = "OK" if m.reprovada is None else f"REPROVADA ({m.reprovada})"
            print(f"   {m.obrigacao}.{m.campo}: {m.valor_atual} -> {m.valor_novo} [{status}]")
            print(f"      \"{m.trecho[:160]}\"")
        if an.revisao_humana:
            print("   >> precisa de revisão humana")
        ato_id = db.registrar_ato(conn, "dou", a.id_materia, a.identifica, ementa=a.ementa,
                                  publicado_em=a.pub_date.isoformat(), texto=a.text)
        novas = set(aplicar(conn, an, ato_id))
        afetadas = sorted(
            codigo for codigo, aid in ativos.items()
            if any(o.pendente and o.pendente["id"] in novas for o in db.obrigacoes_do_ativo(conn, aid))
        )
        print(f"   barragens afetadas por este ato: {', '.join(afetadas) or 'nenhuma'}\n")
    print(f"Custo total de IA: US$ {roteador.custo_total():.5f}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
