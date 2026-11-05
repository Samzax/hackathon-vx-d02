"""Camadas 0 e 1: o que dá para resolver sem IA.

Camada 0 (regex): normas, artigos e datas citados no ato.
Camada 1 (busca local): quais obrigações do cadastro o ato provavelmente toca.
Só essas obrigações vão para a IA; se nenhuma for tocada, a IA nem é chamada.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

# Palavras comuns demais para indicar relação entre o ato e uma obrigação.
VAZIAS = set("""
    barragem barragens mineracao resolucao agencia nacional enviar elaborar realizar
    executar concluir emitir anual semestral quinzenal prazo prazos artigo artigos
    sobre entre todas todos apos cada periodo pelos pelas quanto desde forma deste
    desta dessa nesta neste outras outros demais seguinte seguintes vigor redacao
    para como pelo pela mais onde quando este esta deve devem sera serao todo toda
    conforme menos assim caso casos dias meses anos data datas fica ficam
""".split())


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


# ------------------------------------------------------------------- camada 0


_RE_NORMA = re.compile(r"resolucao(?: dc/| )?(?:anm )?(?:n[o.]? ?|numero )?(\d{1,4})\b")
_RE_NORMA_CURTA = re.compile(r"res\. ?anm (\d{1,4})")
_RE_ART = re.compile(r"\barts?\. ?(\d{1,3})")
_RE_PAR = re.compile(r"§ ?(\d{1,2})")
_RE_DATA_EXTENSO = re.compile(r"(\d{1,2})o? de (" + "|".join(MESES) + r") de (\d{4})")
_RE_DATA_NUM = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


def datas(texto: str) -> set[date]:
    t = normalizar(texto)
    out = set()
    for d, m, a in _RE_DATA_EXTENSO.findall(t):
        try:
            out.add(date(int(a), MESES[m], int(d)))
        except ValueError:
            pass
    for d, m, a in _RE_DATA_NUM.findall(t):
        try:
            out.add(date(int(a), int(m), int(d)))
        except ValueError:
            pass
    return out


@dataclass
class Referencias:
    normas: set[str] = field(default_factory=set)      # "220", "95"...
    artigos: set[str] = field(default_factory=set)
    paragrafos: set[str] = field(default_factory=set)
    datas: set[date] = field(default_factory=set)


def referencias(texto: str) -> Referencias:
    t = normalizar(texto)
    return Referencias(
        normas=set(_RE_NORMA.findall(t)) | set(_RE_NORMA_CURTA.findall(t)),
        artigos=set(_RE_ART.findall(t)),
        paragrafos=set(_RE_PAR.findall(texto)),
        datas=datas(texto),
    )


# ------------------------------------------------------------------- camada 1


def _termos(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z0-9]{4,}", normalizar(texto)) if p not in VAZIAS}


@dataclass
class Candidata:
    codigo: str
    pontos: int
    motivos: list[str]


def candidatas(ato_texto: str, obrigacoes: list[dict], limite: int = 6) -> list[Candidata]:
    """Ordena as obrigações pela chance de o ato tocá-las.

    +5 se o ato cita a norma em que a obrigação se baseia
    +4 se, além disso, cita o mesmo artigo
    +1 por termo relevante em comum (máx. 4), ex.: SIGBM, PAEBM, ZAS
    Sem citação da norma, um termo só não basta (precisa de dois em comum).
    """
    refs = referencias(ato_texto)
    termos_ato = _termos(ato_texto)
    out = []
    for ob in obrigacoes:
        ref_ob = referencias(f'{ob.get("fonte") or ""} {ob["artigo"]}')
        pontos, motivos = 0, []
        if refs.normas & ref_ob.normas:
            pontos += 5
            motivos.append(f"cita a Res. {', '.join(sorted(refs.normas & ref_ob.normas))}")
            comuns = refs.artigos & ref_ob.artigos
            if comuns:
                pontos += 4
                motivos.append(f"cita o art. {', '.join(sorted(comuns, key=int))}")
        termos = termos_ato & _termos(" ".join([ob["titulo"], ob.get("evidencia") or "", ob["aplica_se_a"]]))
        if termos and (pontos or len(termos) >= 2):
            pontos += min(len(termos), 4)
            motivos.append("termos: " + ", ".join(sorted(termos)[:4]))
        if pontos:
            out.append(Candidata(ob["codigo"], pontos, motivos))
    out.sort(key=lambda c: (-c.pontos, c.codigo))
    return out[:limite]
