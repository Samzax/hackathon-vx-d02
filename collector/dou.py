"""Leitura de páginas do Diário Oficial da União já salvas em cache/.

Este módulo NÃO acessa a rede. O robots.txt de www.in.gov.br proíbe robôs
(`Disallow: /`), então o radar usa os canais oficiais de acesso em lote
(XML mensal de dados abertos e INLABS). Os parsers abaixo servem para as
páginas HTML que já foram baixadas durante a pesquisa.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

ACT_URL = "https://www.in.gov.br/web/dou/-/{url_title}"

# do1 é a edição regular; as outras são edições extras e suplementos.
SECTIONS = ("do1", "do1a", "do1e", "do1esp")
ANM = "Agência Nacional de Mineração"
SAUDE = "Ministério da Saúde"

# Tipos de ato que podem criar ou mudar obrigações gerais.
# Despachos e retificações costumam ser atos individuais (um processo, uma empresa).
NORMATIVE_TYPES = ("Resolução", "Portaria", "Instrução Normativa", "Deliberação",
                   "Lei", "Decreto", "Medida Provisória")

# Camada 0 do radar: órgãos cujos atos normativos interessam à carteira (trecho da hierarquia do DOU
# -> rótulo do motivo). Era só a ANM; ampliado em 7/11/2026 porque portaria do MTE que altera NR, lei
# federal que altera a 12.334 e ato da ANA passavam no DOU e eram descartados sem ninguém ver.
# Ato de órgão fora da lista ainda entra se a ementa citar termos de um tipo de ativo da carteira
# (mitra/temas.toml); o casamento fica em quem chama (api/jobs.py), para este módulo não depender do mitra.
ORGAOS_RADAR = {
    ANM: "ANM",
    "Ministério do Trabalho e Emprego": "MTE (NRs, portarias de SST)",
    "Ministério do Meio Ambiente": "meio ambiente (MMA, Ibama, ICMBio, Conama)",
    "Agência Nacional de Águas": "ANA",
    "Atos do Poder Legislativo": "lei federal",
    "Atos do Poder Executivo": "decreto ou medida provisória federal",
}


def orgao_de_interesse(hierarquia: str) -> str | None:
    """O motivo de o ato interessar pelo órgão, ou None. `hierarquia` é a artCategory do XML
    (ex.: "Ministério de Minas e Energia/Agência Nacional de Mineração/...")."""
    for marca, rotulo in ORGAOS_RADAR.items():
        if marca in hierarquia:
            return rotulo
    return None

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"


class NotCached(FileNotFoundError):
    """A página pedida não está em cache/ e não será baixada."""


@dataclass
class ListedAct:
    url_title: str
    title: str
    art_type: str
    hierarchy: str
    pub_date: str
    edition: str
    page: str
    section: str
    excerpt: str

    @property
    def is_anm(self) -> bool:
        return ANM in self.hierarchy

    @property
    def is_saude(self) -> bool:
        return SAUDE in self.hierarchy or "Agência Nacional de Vigilância Sanitária" in self.hierarchy

    @property
    def is_normative(self) -> bool:
        return self.art_type.startswith(NORMATIVE_TYPES)

    @property
    def url(self) -> str:
        return ACT_URL.format(url_title=self.url_title)


@dataclass
class Act:
    url_title: str
    url: str
    identifica: str
    ementa: str
    paragraphs: list[str]
    signer: str
    role: str
    published: str
    edition: str
    section: str
    page: str
    organ: str
    extra: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n".join([self.identifica, self.ementa, *self.paragraphs])


# ---------------------------------------------------------------------- parsers


def parse_listing(html: str, section: str) -> list[ListedAct]:
    script = BeautifulSoup(html, "html.parser").find("script", id="params")
    if script is None or not script.string:
        return []
    rows = json.loads(script.string).get("jsonArray", [])
    return [
        ListedAct(
            url_title=r["urlTitle"],
            title=r.get("title", ""),
            art_type=r.get("artType", ""),
            hierarchy=r.get("hierarchyStr", ""),
            pub_date=r.get("pubDate", ""),
            edition=r.get("editionNumber", ""),
            page=r.get("numberPage", ""),
            section=section,
            excerpt=r.get("content", ""),
        )
        for r in rows
    ]


def _text(soup, cls: str) -> str:
    el = soup.find(class_=cls)
    return el.get_text(" ", strip=True) if el else ""


def parse_act(html: str, url_title: str) -> Act:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("div.texto-dou")
    if body is None:
        raise ValueError(f"texto-dou não encontrado em {url_title}")
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in body.find_all("p", class_="dou-paragraph")
        if p.get_text(strip=True)
    ]
    return Act(
        url_title=url_title,
        url=ACT_URL.format(url_title=url_title),
        identifica=_text(body, "identifica"),
        ementa=_text(body, "ementa"),
        paragraphs=paragraphs,
        signer=_text(body, "assina"),
        role=_text(body, "cargo"),
        published=_text(soup, "publicado-dou-data"),
        edition=_text(soup, "edicao-dou-data"),
        section=_text(soup, "secao-dou").removeprefix("Seção:").strip(),
        page=_text(soup, "secao-dou-data"),
        organ=_text(soup, "orgao-dou-data"),
    )


# ----------------------------------------------------------------- leitura local


def _read(path: Path) -> str:
    if not path.exists():
        raise NotCached(f"{path} não está em cache")
    return path.read_text(encoding="utf-8")


def load_listing(day: date, sections=SECTIONS, cache: Path = CACHE) -> list[ListedAct]:
    """Lê as listagens do dia que estiverem em cache; seções ausentes são puladas."""
    acts: list[ListedAct] = []
    for sec in sections:
        path = cache / "listing" / f"{sec}_{day.isoformat()}.html"
        if path.exists():
            acts.extend(parse_listing(path.read_text(encoding="utf-8"), sec))
    return acts


def load_act(url_title: str, cache: Path = CACHE) -> Act:
    return parse_act(_read(cache / "acts" / f"{url_title}.html"), url_title)


@dataclass
class DayResult:
    day: str
    total: int
    by_section: dict[str, int]
    anm: list[ListedAct]
    normative: list[Act]
    missing: list[str]

    def funnel(self) -> str:
        secs = ", ".join(f"{k} {v}" for k, v in self.by_section.items() if v)
        line = (
            f"{self.day}: {self.total} atos ({secs}) -> {len(self.anm)} da ANM "
            f"-> {len(self.normative)} normativos"
        )
        if self.missing:
            line += f" ({len(self.missing)} normativos sem texto em cache)"
        return line


def collect_day(day: date, cache: Path = CACHE) -> DayResult:
    listed = load_listing(day, cache=cache)
    by_section = {s: sum(1 for a in listed if a.section == s) for s in SECTIONS}
    anm = [a for a in listed if a.is_anm]
    normative, missing = [], []
    for a in anm:
        if not a.is_normative:
            continue
        try:
            normative.append(load_act(a.url_title, cache))
        except NotCached:
            missing.append(a.url_title)
    return DayResult(day.isoformat(), len(listed), by_section, anm, normative, missing)


def save_day(result: DayResult, out_dir: Path = ROOT / "data" / "anm") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result.day}.json"
    payload = {
        "day": result.day,
        "total": result.total,
        "by_section": result.by_section,
        "anm": [asdict(a) | {"url": a.url, "normative": a.is_normative} for a in result.anm],
        "normative": [asdict(a) for a in result.normative],
        "missing": result.missing,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
