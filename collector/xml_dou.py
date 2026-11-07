"""Leitor do XML mensal de dados abertos do DOU (Imprensa Nacional).

Cada ZIP mensal (ex.: S01082026.zip = Seção 1, agosto de 2026) traz um XML
por publicação. Atos grandes vêm divididos em partes (_001, _002...) com o
mesmo idMateria; aqui as partes são juntadas, e cada ato aparece uma vez.

Fonte: https://www.in.gov.br/acesso-a-informacao/dados-abertos/base-de-dados
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from .dou import ANM, SAUDE, NORMATIVE_TYPES


@dataclass
class XmlAct:
    id_materia: str
    name: str
    pub_name: str          # DO1, DO1E (edição extra)...
    art_type: str
    pub_date: date
    category: str          # hierarquia do órgão
    page: str
    edition: str
    pdf_page: str
    identifica: str
    ementa: str
    texto_html: str

    @property
    def is_anm(self) -> bool:
        return ANM in self.category

    @property
    def is_saude(self) -> bool:
        return SAUDE in self.category or "Agência Nacional de Vigilância Sanitária" in self.category

    @property
    def is_normative(self) -> bool:
        return self.art_type.startswith(NORMATIVE_TYPES)

    @property
    def paragraphs(self) -> list[str]:
        soup = BeautifulSoup(self.texto_html, "html.parser")
        return [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)


_PARTE = re.compile(r"-(\d+)\.xml$", re.IGNORECASE)


def _ordem(name: str) -> tuple[str, int]:
    """Ordena 'x-2.xml' antes de 'x-10.xml' (ordem alfabética erraria)."""
    m = _PARTE.search(name)
    return (name[: m.start()] if m else name[:-4], int(m.group(1)) if m else 0)


def _parts(zip_path: Path):
    with zipfile.ZipFile(zip_path) as z:
        for name in sorted(z.namelist(), key=_ordem):
            if not name.lower().endswith(".xml"):
                continue
            root = ET.fromstring(z.read(name).decode("utf-8-sig"))
            art = root.find("article") if root.tag != "article" else root
            if art is None:
                continue
            body = art.find("body")

            def field(tag: str, body=body) -> str:
                el = body.find(tag) if body is not None else None
                return (el.text or "").strip() if el is not None else ""

            yield art.attrib, field("Identifica"), field("Ementa"), field("Texto")


def load_month(zip_path: str | Path) -> list[XmlAct]:
    grupos: dict[str, list] = defaultdict(list)
    for attrs, identifica, ementa, texto in _parts(Path(zip_path)):
        key = attrs.get("idMateria") or attrs["id"]
        grupos[key].append((attrs, identifica, ementa, texto))

    acts = []
    for key, partes in grupos.items():
        attrs = partes[0][0]
        acts.append(XmlAct(
            id_materia=key,
            name=attrs.get("name", ""),
            pub_name=attrs.get("pubName", ""),
            art_type=attrs.get("artType", ""),
            pub_date=datetime.strptime(attrs["pubDate"], "%d/%m/%Y").date(),
            category=attrs.get("artCategory", ""),
            page=attrs.get("numberPage", ""),
            edition=attrs.get("editionNumber", ""),
            pdf_page=attrs.get("pdfPage", ""),
            identifica=next((p[1] for p in partes if p[1]), ""),
            ementa=next((p[2] for p in partes if p[2]), ""),
            texto_html="".join(p[3] for p in partes),
        ))
    acts.sort(key=lambda a: (a.pub_date, a.pub_name, a.id_materia))
    return acts


def atos_do_setor(acts: list[XmlAct], setor: str) -> list[XmlAct]:
    """Recorte reutilizável do DOU para um setor antes da triagem por regra e IA.

    O XML mensal continua sendo a fonte oficial de dados abertos; mudar o setor não exige
    mudar o parser nem recorrer ao site do DOU. Setores novos só precisam declarar o órgão
    que os regula e manter um cadastro de obrigações compatível.
    """
    predicados = {"mineracao": lambda a: a.is_anm, "saude": lambda a: a.is_saude}
    try:
        predicado = predicados[setor]
    except KeyError as e:
        raise ValueError(f"setor desconhecido: {setor}") from e
    return [a for a in acts if predicado(a)]


@dataclass
class Funil:
    dia: date
    total: int
    por_edicao: dict[str, int]
    anm: int
    normativos: list[XmlAct]

    def linha(self) -> str:
        ed = ", ".join(f"{k} {v}" for k, v in sorted(self.por_edicao.items()))
        nomes = "; ".join(a.identifica for a in self.normativos)
        return (f"{self.dia}: {self.total:4d} atos ({ed}) -> {self.anm:3d} da ANM "
                f"-> {len(self.normativos)} normativos" + (f"  [{nomes}]" if nomes else ""))


def funil_por_dia(acts: list[XmlAct]) -> list[Funil]:
    por_dia: dict[date, list[XmlAct]] = defaultdict(list)
    for a in acts:
        por_dia[a.pub_date].append(a)
    out = []
    for dia in sorted(por_dia):
        do_dia = por_dia[dia]
        anm = [a for a in do_dia if a.is_anm]
        out.append(Funil(
            dia=dia,
            total=len(do_dia),
            por_edicao=dict(Counter(a.pub_name for a in do_dia)),
            anm=len(anm),
            normativos=[a for a in anm if a.is_normative],
        ))
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print("Uso: python -m collector.xml_dou data/raw/dou/S01082026.zip")
        return 2
    acts = load_month(argv[0])
    funis = funil_por_dia(acts)
    for f in funis:
        print(f.linha())
    total = sum(f.total for f in funis)
    anm = sum(f.anm for f in funis)
    norm = sum(len(f.normativos) for f in funis)
    print(f"\nMês: {total} atos -> {anm} da ANM -> {norm} normativos da ANM")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
