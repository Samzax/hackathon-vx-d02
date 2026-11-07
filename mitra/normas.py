"""Texto de normas, já baixado: leitura e divisão em unidades (artigos ou itens).

- Resoluções da ANM (ANMlegis, HTML consolidado): unidade = artigo ("27").
- Normas Regulamentadoras do MTE (PDF do texto vigente): unidade = item de
  3º nível ("13.5.4"), com seus subitens e alíneas.

Parágrafos revogados são descartados. Anexos ficam de fora: descrevem conteúdo
de documentos ou requisitos técnicos detalhados, e entram depois, se preciso.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

_ART = re.compile(r"^Art\. ?(\d+)")
_ANEXO = re.compile(r"^ANEXO\b")
_REVOGADO = re.compile(r"^\s*(?:[IVXLC]+|[a-z]\)|§ ?\d+º?|Art\. ?\d+º?\.?|\d+(?:\.\d+)+)?\s*[-–.]?\s*\(?\s*(?:revogad|exclu[ií]d)", re.I)
_ITEM = re.compile(r"^(\d{1,2}(?:\.\d+)+)\.?\s")


@dataclass
class Unidade:
    id: str           # "27" (artigo) ou "13.5.4" (item de NR)
    texto: str

    @property
    def numero(self) -> int:
        """Compatibilidade com artigos numéricos."""
        return int(self.id.split(".")[0])


Artigo = Unidade   # nome antigo


# ------------------------------------------------------------------- ANMlegis


_SUBLINHADO = {">": "≥", "<": "≤"}


def paragrafos_anmlegis(caminho: str | Path) -> list[str]:
    return paragrafos_anmlegis_html(Path(caminho).read_text(encoding="utf-8"))


def paragrafos_anmlegis_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    # O ANMlegis escreve "≥" como ">" sublinhado (<u>&gt;</u>): sem isso, "DPA2 ≥ 4" viraria "DPA2 > 4"
    for u in soup.find_all("u"):
        if (s := u.get_text().strip()) in _SUBLINHADO:
            u.replace_with(_SUBLINHADO[s])
    return paragrafos_anmlegis_de(p.get_text(" ", strip=True) for p in soup.find_all("p"))


def paragrafos_anmlegis_de(textos) -> list[str]:
    """Limpa espaços e descarta parágrafos revogados."""
    out = []
    for t in textos:
        t = re.sub(r"\s+", " ", t).strip()
        if t and not _REVOGADO.match(t):
            out.append(t)
    return out


def artigos(paragrafos: list[str]) -> list[Unidade]:
    """Agrupa os parágrafos por artigo; o preâmbulo (antes do art. 1) é ignorado."""
    out: list[Unidade] = []
    atual: list[str] | None = None
    numero = 0
    for p in paragrafos:
        if _ANEXO.match(p) and atual is not None:
            break   # anexos descrevem conteúdo de documentos, não criam obrigações
        m = _ART.match(p)
        if m:
            if atual is not None:
                out.append(Unidade(str(numero), "\n".join(atual)))
            numero, atual = int(m.group(1)), [p]
        elif atual is not None:
            atual.append(p)
    if atual is not None:
        out.append(Unidade(str(numero), "\n".join(atual)))
    return out


# ------------------------------------------------------------------- NRs (PDF)


_CABECALHO_NR = re.compile(r"^Este texto não substitui o publicado no DOU\s*$", re.I)


def paragrafos_pdf_nr(caminho: str | Path) -> list[str]:
    """Remonta parágrafos do PDF: junta linhas quebradas, tira o cabeçalho de página."""
    from pypdf import PdfReader

    linhas = []
    for pagina in PdfReader(str(caminho)).pages:
        for linha in (pagina.extract_text() or "").splitlines():
            if _CABECALHO_NR.match(linha.strip()):
                continue
            linhas.append(linha.rstrip())
    return paragrafos_de_linhas(linhas)


def paragrafos_de_linhas(linhas: list[str]) -> list[str]:
    paragrafos, atual = [], []

    def fechar():
        if atual:
            t = re.sub(r"\s+", " ", " ".join(atual)).strip()
            if t and not _REVOGADO.match(t):
                paragrafos.append(t)
            atual.clear()

    for linha in linhas:
        s = linha.strip()
        if not s:
            fechar()
            continue
        # um item numerado ou uma alínea sempre começa parágrafo novo
        if _ITEM.match(s) or re.match(r"^[a-z]\)\s", s) or _ANEXO.match(s):
            fechar()
        atual.append(s)
    fechar()
    return paragrafos


def _pula_sumario(paragrafos: list[str]) -> list[str]:
    """Algumas NRs abrem com um sumário ("22.1 Objetivo", ..., "ANEXO I ..."):
    o corpo começa na segunda vez que o primeiro item aparece. A comparação é pelo número do
    item, não pelo parágrafo inteiro: no PDF da NR-18 (2026) o sumário sai com linhas coladas
    ("18.1 Objetivo 118.78.2 ..."), e o parágrafo do corpo nunca é idêntico ao do sumário."""
    primeiro = next((i for i, p in enumerate(paragrafos) if _ITEM.match(p)), None)
    if primeiro is None:
        return paragrafos
    cabeca_id = _ITEM.match(paragrafos[primeiro]).group(1)
    for i in range(primeiro + 1, len(paragrafos)):
        m = _ITEM.match(paragrafos[i])
        if m and m.group(1) == cabeca_id:
            return paragrafos[i:]
    return paragrafos[primeiro:]


def itens_nr(paragrafos: list[str], nivel: int = 3) -> list[Unidade]:
    """Agrupa os parágrafos pelo prefixo do item no nível pedido (13.5.4 com nivel=3).
    Um item que reaparece mais adiante (texto fora de ordem no PDF) junta-se ao primeiro."""
    from collections import Counter

    corpo = _pula_sumario(paragrafos)
    # o capítulo da NR ("13" na NR-13): um número como "1.960 kPa" no início de linha não é item
    caps = Counter(m.group(1).split(".")[0] for p in corpo if (m := _ITEM.match(p)))
    capitulo = caps.most_common(1)[0][0] if caps else None
    grupos: dict[str, list[str]] = {}
    chave = None
    for p in corpo:
        if _ANEXO.match(p) and grupos:
            break
        m = _ITEM.match(p)
        if m and m.group(1).split(".")[0] != capitulo:
            m = None
        if m:
            chave = ".".join(m.group(1).split(".")[:nivel])
        if chave is not None:
            grupos.setdefault(chave, []).append(p)
    return [Unidade(k, "\n".join(v)) for k, v in grupos.items()]


# --------------------------------------------------------------------- blocos


def blocos(unidades: list[Unidade], max_chars: int = 14000) -> list[list[Unidade]]:
    """Junta unidades seguidas em blocos de até max_chars, sem partir uma unidade."""
    out, atual, tamanho = [], [], 0
    for u in unidades:
        if atual and tamanho + len(u.texto) > max_chars:
            out.append(atual)
            atual, tamanho = [], 0
        atual.append(u)
        tamanho += len(u.texto)
    if atual:
        out.append(atual)
    return out
