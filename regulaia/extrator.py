"""Extrator: texto de uma norma -> obrigações propostas, para revisão humana.

A IA lê a norma em blocos de artigos e propõe obrigações do regulado (o quê,
quando, para quais ativos, com qual evidência), sempre com o trecho literal.
O Python reprova trecho que não existe no bloco, artigo fora do bloco e regra
de aplicabilidade mal escrita ou com atributo desconhecido. Nada entra no
cadastro sem uma pessoa revisar o arquivo gerado.

Uso:
  uv run python -m regulaia.extrator ORIGEM NORMA TIPO DESTINO [PREFIXOS]

  ORIGEM   .html do ANMlegis (unidade = artigo) ou .pdf de NR (unidade = item 13.5.4)
  PREFIXOS itens a ler, separados por vírgula (ex.: 22.24,22.30); padrão: todos

Exemplos:
  uv run python -m regulaia.extrator data/raw/normas/res95_2022.html \
      "Res. ANM 95/2022" barragem data/extraido/res95_2022.json
  uv run python -m regulaia.extrator data/raw/normas/nr-13-atualizada-2023-b.pdf \
      "NR-13" equipamento data/extraido/nr13.json
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import db, normas, regras
from .ia import Roteador, SemProvedor
from .impacto import _limpo
from .triagem import normalizar

VERSAO_PROMPT = "extrator-v2"

# Atributos que a regra de aplicabilidade pode usar, por tipo de ativo.
VOCABULARIO = {
    "barragem": {
        "dpa": "dano potencial associado: alto, medio ou baixo",
        "cri": "categoria de risco: alto, medio ou baixo",
        "dpa2": "pontuação de perda de vidas humanas do DPA (número)",
        "inserida_pnsb": "verdadeiro se a barragem está na Política Nacional de Segurança de Barragens",
        "metodo_construtivo": "montante, jusante, linha_de_centro, etapa_unica",
        "situacao_operacional": "ativa, inativa, em_descaracterizacao",
        "nivel_emergencia": "0 (sem emergência), 1, 2 ou 3; use 'alerta' para nível de alerta",
        "altura_m": "altura em metros (número)",
        "volume_m3": "volume do reservatório em m³ (número)",
        "trabalhadores_zas": "verdadeiro se há trabalhadores na Zona de Autossalvamento",
        "mapa_inundacao_validado": "verdadeiro se o mapa de inundação foi validado",
        "alteamento_continuo": "verdadeiro se é alteada continuamente",
        "modificacao_estrutural": "verdadeiro se passou por modificação estrutural",
        "residuo_perigoso": "verdadeiro se armazena resíduo perigoso",
    },
    # máquinas e equipamentos sob NR-12 / NR-13 / NR-22
    "equipamento": {
        "classe": "vaso_pressao, caldeira, tubulacao, tanque, maquina, transportador_continuo, "
                  "equipamento_guindar, veiculo",
        "categoria_vaso": "categoria do vaso de pressão pela NR-13: I, II, III, IV ou V",
        "categoria_caldeira": "categoria da caldeira pela NR-13: A ou B",
        "spie": "verdadeiro se o estabelecimento tem SPIE certificado",
        "em_operacao": "verdadeiro se está em operação",
        "subsolo": "verdadeiro se opera em mina subterrânea",
    },
    # a mina ou unidade operacional como um todo (NR-22, licença ambiental)
    "unidade": {
        "lavra": "ceu_aberto ou subterranea",
        "beneficiamento": "verdadeiro se há beneficiamento mineral",
        "deposito_rejeitos": "verdadeiro se há depósito de estéril, rejeitos ou produtos (pilhas, barragens)",
        "usa_explosivos": "verdadeiro se usa explosivos",
        "carvao": "verdadeiro se é mina de carvão",
        "dragas": "verdadeiro se opera dragas flutuantes",
        "trabalhadores": "número de trabalhadores (número)",
    },
}

SISTEMA = """Você é especialista em conformidade regulatória no Brasil.
Recebe um BLOCO de artigos (ou itens numerados, no caso de NR) de uma norma e extrai as OBRIGAÇÕES DO REGULADO (a empresa),
no formato de um cadastro de conformidade.

O que é obrigação: algo que a empresa deve fazer, entregar, manter ou comunicar, com prazo,
periodicidade ou gatilho. NÃO são obrigações: definições, competências da agência,
faculdades ("poderá"), proibições sem ação associada, regras de transição já vencidas.

Para cada obrigação:
- "artigo": dispositivo exato, ex.: "art. 27 §1 I" ou, em NR, o número do item ("13.5.4.5" ou
  "22.30.1 b"). Use só dispositivos que estão no bloco.
- "titulo": a ação no imperativo, curta (ex.: "Enviar a DCE semestral via SIGBM").
- "aplica_se_a": a quem se aplica, em português (ex.: "Barragens com DPA alto").
- "regra": a mesma condição na linguagem da máquina, usando SÓ os atributos listados.
  Sintaxe: "*" (todos), "atributo" (verdadeiro), "atributo = valor", "atributo >= 4",
  condições unidas por " e ". Valor é uma palavra só, sem acento. Se a condição não couber
  nos atributos, use "*" e marque "regra_incompleta": true.
- "periodicidade": Quinzenal, Mensal, Semestral, Anual, A cada N anos, Por evento ou Evento único.
- "prazo": quando, em texto curto (ex.: "01/03-31/03 e 01/09-30/09", "Até 30 dias após o evento").
- "evidencia": o documento ou registro que comprova o cumprimento.
- "area": barragem, emergencia, ambiental, equipamento, seguranca_trabalho, documentacao ou comunicacao.
- "trecho": cópia literal, palavra por palavra, do trecho do bloco que cria a obrigação.

Não invente: se o bloco não tem obrigações do regulado, devolva lista vazia.
Mantenha o "trecho" curto (a frase que obriga, não o parágrafo inteiro) e escape aspas no JSON.
Responda só com JSON: {"obrigacoes": [ {...}, ... ]}"""


@dataclass
class Proposta:
    artigo: str
    titulo: str
    aplica_se_a: str
    regra: str
    periodicidade: str
    prazo: str
    evidencia: str
    area: str
    trecho: str
    regra_incompleta: bool = False
    reprovada: str | None = None
    bloco: str = ""


def dispositivos(texto: str) -> set[str]:
    """Itens de NR ("13.5.4.5") ou números de artigo ("27") citados no texto."""
    itens = set(re.findall(r"\b(\d{1,2}(?:\.\d+)+)\b", texto))
    if itens:
        return itens
    return set(re.findall(r"\barts?\. ?(\d+)", normalizar(texto)))


def _no_bloco(dispositivo: str, ids_bloco: set[str]) -> bool:
    return any(dispositivo == i or dispositivo.startswith(i + ".") for i in ids_bloco)


def conferir(p: Proposta, bloco_texto: str, ids_bloco: set[str], tipo: str) -> str | None:
    if not p.trecho or _limpo(p.trecho) not in _limpo(bloco_texto):
        return "o trecho citado não existe no bloco"
    nums = dispositivos(p.artigo)
    if not nums:
        return f"dispositivo {p.artigo!r} sem número"
    if any(not _no_bloco(d, ids_bloco) for d in nums):
        return f"dispositivo {p.artigo!r} não está no bloco"
    try:
        regras.validar(p.regra)
    except regras.RegraInvalida as e:
        return f"regra inválida: {e}"
    desconhecidos = regras.campos(p.regra) - set(VOCABULARIO[tipo])
    if desconhecidos:
        return f"regra usa atributo desconhecido: {sorted(desconhecidos)}"
    if not p.titulo.strip():
        return "sem título"
    return None


@dataclass
class Resultado:
    norma: str
    tipo_ativo: str
    propostas: list[Proposta] = field(default_factory=list)
    modelos: list[str] = field(default_factory=list)
    custo_usd: float = 0.0
    blocos_sem_resposta: list[str] = field(default_factory=list)

    @property
    def aprovadas(self):
        return [p for p in self.propostas if p.reprovada is None]


def _chave_dup(p: Proposta) -> tuple:
    return (normalizar(p.artigo), normalizar(p.titulo)[:60])


def _rotulo(grupo: list[normas.Unidade]) -> str:
    a, b = grupo[0].id, grupo[-1].id
    prefixo = "itens" if "." in a else "arts."
    return f"{prefixo} {a}" if a == b else f"{prefixo} {a}-{b}"


def extrair(roteador: Roteador, norma: str, unidades: list[normas.Unidade], tipo: str,
            max_chars: int = 9000) -> Resultado:
    """Lê a norma em blocos. Bloco que nenhum modelo consegue responder (resposta longa
    demais, JSON quebrado, tempo esgotado) é dividido ao meio e tentado de novo."""
    vocab = "\n".join(f"- {k}: {v}" for k, v in VOCABULARIO[tipo].items())
    res = Resultado(norma, tipo)
    vistos = set()
    fila = list(normas.blocos(unidades, max_chars))
    while fila:
        grupo = fila.pop(0)
        ids = {u.id for u in grupo}
        rotulo = _rotulo(grupo)
        texto = "\n\n".join(u.texto for u in grupo)
        usuario = (f"NORMA: {norma}\nTIPO DE ATIVO: {tipo}\n\nATRIBUTOS PERMITIDOS NA REGRA:\n{vocab}\n\n"
                   f"BLOCO ({rotulo}):\n{texto}")
        try:
            r = roteador.pedir_json("extrator", 2, SISTEMA, usuario, VERSAO_PROMPT, max_tokens=16000)
        except SemProvedor as e:
            if len(grupo) > 1:
                meio = len(grupo) // 2
                fila[:0] = [grupo[:meio], grupo[meio:]]
                res.modelos.append(f"{rotulo}: dividido em dois ({str(e)[:80]})")
            else:
                res.blocos_sem_resposta.append(f"{rotulo}: {e}")
            continue
        res.modelos.append(f"{rotulo}: {r.modelo.rotulo}" + (" (cache)" if r.do_cache else ""))
        res.custo_usd += 0.0 if r.do_cache else r.custo_usd
        for d in r.dados.get("obrigacoes") or []:
            p = Proposta(
                artigo=str(d.get("artigo", "")), titulo=str(d.get("titulo", "")),
                aplica_se_a=str(d.get("aplica_se_a", "")), regra=str(d.get("regra", "*")).strip() or "*",
                periodicidade=str(d.get("periodicidade", "")), prazo=str(d.get("prazo", "")),
                evidencia=str(d.get("evidencia", "")), area=str(d.get("area", "")),
                trecho=str(d.get("trecho", "")), regra_incompleta=bool(d.get("regra_incompleta", False)),
                bloco=rotulo,
            )
            p.reprovada = conferir(p, texto, ids, tipo)
            if p.reprovada is None:
                k = _chave_dup(p)
                if k in vistos:
                    p.reprovada = "duplicada"
                vistos.add(k)
            res.propostas.append(p)
    return res


def carregar_unidades(origem: str | Path, prefixos: list[str] | None = None) -> list[normas.Unidade]:
    origem = Path(origem)
    if origem.suffix.lower() == ".pdf":
        unidades = normas.itens_nr(normas.paragrafos_pdf_nr(origem))
    else:
        unidades = normas.artigos(normas.paragrafos_anmlegis(origem))
    if prefixos:
        unidades = [u for u in unidades if any(u.id == x or u.id.startswith(x + ".") for x in prefixos)]
    return unidades


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(__doc__)
        return 2
    origem, norma, tipo, destino = argv[:4]
    prefixos = argv[4].split(",") if len(argv) > 4 else None
    # respostas de extração são longas (milhares de tokens): mais tempo por chamada
    roteador = Roteador(db.conectar(db.ROOT / "data" / "cache_ia.db"), timeout=420)
    res = extrair(roteador, norma, carregar_unidades(origem, prefixos), tipo)
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    Path(destino).write_text(json.dumps(
        {"norma": norma, "tipo_ativo": tipo, "custo_usd": res.custo_usd, "modelos": res.modelos,
         "blocos_sem_resposta": res.blocos_sem_resposta,
         "propostas": [asdict(p) for p in res.propostas]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{norma}: {len(res.aprovadas)} obrigações aprovadas pelo Python, "
          f"{len(res.propostas) - len(res.aprovadas)} reprovadas, custo US$ {res.custo_usd:.4f}")
    for m in res.modelos:
        print("  ", m)
    for b in res.blocos_sem_resposta:
        print("   SEM RESPOSTA:", b)
    print(f"-> {destino}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
