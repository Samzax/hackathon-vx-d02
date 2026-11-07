"""Vigência e alterações das normas federais, pela Câmara dos Deputados (Legislação Informatizada).

O Senado (fonte da descoberta) não diz se a norma está em vigor, e o Planalto derruba conexão que não
vem de navegador. A ficha de cada norma federal na Câmara tem as duas coisas que faltavam:

- "Situação" ("Revogada" ou "Não consta revogação expressa") e "Vide Norma(s)": quem alterou,
  acrescentou, regulamentou ou revogou a norma, quando e em quais dispositivos;
- o "Texto Atualizado" (consolidado, com as notas "redação dada pela Lei ...").

Para chegar na ficha sem adivinhar endereço, o resolvedor de URN do LexML (`/urn/...`, liberado no
robots.txt do LexML, que pede 5 s entre pedidos) devolve os links oficiais da norma, entre eles o da
Câmara. A busca do LexML (`/busca/`) tem desafio anti-robô e não é usada.

O que sai daqui:

- `revisar_catalogo`: para cada norma federal do catálogo, as alterações com os artigos que mudaram,
  quais obrigações do catálogo citam esses artigos, e quais trechos citados já não estão, palavra por
  palavra, no texto atualizado. É o alarme de "a norma mudou depois que a catalogamos".
- `marcar_candidatas`: a vigência das candidatas federais da descoberta; revogada sai da fila
  (descartada, com a fonte na nota), aprovada e revogada fica, para a curadoria ver.
- `texto_atualizado`: o texto consolidado, para a segunda leitura da triagem nas normas federais.

    uv run python -m regulaia.vigencia catalogo
    uv run python -m regulaia.vigencia candidatas [--limite N]
    uv run python -m regulaia.vigencia norma BR:LEI:12334/2010
"""

from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from . import db
from .impacto import _limpo

CACHE = db.ROOT / "data" / "raw" / "fontes" / "vigencia"
LEXML = "https://www.lexml.gov.br/urn/"
INTERVALO = {"www.lexml.gov.br": 5.0, "www2.camara.leg.br": 1.0, "legis.senado.leg.br": 1.0}   # segundos entre pedidos ao mesmo host
AGENTE = "RegulaIA/0.1 (pesquisa regulatoria)"
FONTE = "Câmara dos Deputados, Legislação Informatizada"
FONTE_SENADO = "Senado Federal, dados abertos (detalhe da norma)"
SENADO_DETALHE = "https://legis.senado.leg.br/dadosabertos/legislacao/{id}"

# tipo da chave da descoberta -> tipo na URN do LexML (só os que a Câmara tem)
URN_TIPO = {"LEI": "lei", "LCP": "lei.complementar", "DEL": "decreto.lei", "DEC": "decreto"}
# tipo como a Câmara escreve -> tipo da chave
TIPO_CAMARA = {
    "lei ordinaria": "LEI", "lei": "LEI", "lei complementar": "LCP", "decreto-lei": "DEL", "decreto lei": "DEL",
    "decreto": "DEC", "medida provisoria": "MPV", "emenda constitucional": "EMC", "lei delegada": "LDL",
    "decreto legislativo": "DLG", "resolucao": "RES", "constituicao": "CF",
}
MESES = {m: i for i, m in enumerate(("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto",
                                     "setembro", "outubro", "novembro", "dezembro"), 1)}
# relações que mudam o texto (as outras, como regulamentação e norma complementar, só informam)
MUDAM_TEXTO = ("alteracao", "acrescimo", "revogacao", "nova redacao", "renumeracao", "supressao")


class ErroVigencia(ValueError):
    pass


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower().strip()


def _texto(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


# --------------------------------------------------------------------------- endereços


def urn(chave_norma: str) -> str:
    """BR:LEI:12334/2010 -> urn:lex:br:federal:lei:2010;12334 (o LexML aceita só o ano no lugar da data)."""
    m = re.fullmatch(r"BR:([A-Z-]+):(\d+)/(\d{4})", chave_norma)
    if not m or m.group(1) not in URN_TIPO:
        raise ErroVigencia(f"{chave_norma}: só lei, lei complementar, decreto e decreto-lei federais")
    tipo, numero, ano = m.groups()
    return f"urn:lex:br:federal:{URN_TIPO[tipo]}:{ano};{numero}"


def suportada(chave_norma: str) -> bool:
    try:
        urn(chave_norma)
        return True
    except ErroVigencia:
        return False


def _https_camara(url: str) -> str:
    return re.sub(r"^https?://www2\.camara\.(gov|leg)\.br", "https://www2.camara.leg.br", url)


def senado_no_lexml(pagina: str) -> str | None:
    """Da página do resolvedor de URN, o código da norma no Senado (para o detalhe nos dados abertos)."""
    m = re.search(r"legis\.senado\.leg\.br/norma/(\d+)", pagina)
    return m.group(1) if m else None


def ficha_no_lexml(pagina: str) -> str | None:
    """Da página do resolvedor de URN, o link para a ficha da norma na Câmara."""
    for a in BeautifulSoup(pagina, "html.parser").find_all("a", href=True):
        if re.search(r"camara\.(gov|leg)\.br/legin/.+-norma-p[a-z]\.html$", a["href"]):
            return _https_camara(a["href"])
    return None


# --------------------------------------------------------------------------- a ficha


@dataclass
class Relacao:
    """Uma linha do "Vide Norma(s)": outra norma que fez algo com esta."""
    norma: str            # "Lei Ordinária nº 15355 de 11 de Março de 2026"
    chave: str | None     # BR:LEI:15355/2026
    data: str | None      # 2026-03-11
    relacao: str          # "Alteração", "Revogação", "Regulamentação"...
    dispositivos: str     # 'Art. 3º, "caput", inciso I ; Art. 15, "caput", inciso VI'
    artigos: list[str]    # ["3", "15"]
    url: str | None

    @property
    def muda_texto(self) -> bool:
        r = _sem_acento(self.relacao)
        return any(r.startswith(x) for x in MUDAM_TEXTO)

    @property
    def revoga(self) -> bool:
        return _sem_acento(self.relacao).startswith("revogacao")


@dataclass
class Ficha:
    chave: str
    titulo: str
    ementa: str
    situacao: str
    revogada: bool
    relacoes: list[Relacao] = field(default_factory=list)
    ficha_url: str | None = None
    texto_url: str | None = None          # texto atualizado (consolidado)
    original_url: str | None = None       # publicação original
    fonte: str = FONTE

    @property
    def revogada_por(self) -> list[Relacao]:
        return [r for r in self.relacoes if r.revoga and "parcial" not in _sem_acento(r.relacao)]


_RE_NORMA = re.compile(r"^(?P<tipo>.+?) n[º°o]\.? ?(?P<num>[\d.]+),? de (?P<dia>\d{1,2})[º°o]? de (?P<mes>[^\s]+) de "
                       r"(?P<ano>\d{4})", re.I)
_RE_NORMA_SENADO = re.compile(r"^(?P<tipo>.+?) n[º°o]\.? ?(?P<num>[\d.]+) de (?P<dia>\d{2})/(?P<mes>\d{2})/(?P<ano>\d{4})")
_RE_REL = re.compile(r"^(?P<norma>.+?)\s+-\s+\((?P<rel>[^()]+)\)\.?\s*(?P<disp>.*?)\.?$", re.S)
_RE_ART = re.compile(r"\bart(?:igo)?s?\.?\s*(\d+)\s*[º°o]?\s*(-\s*[A-Z]\b)?", re.I)


def artigos(texto: str) -> list[str]:
    """'Art. 2º-A, "caput"; Art. 18-C' -> ["2-A", "18-C"]; 'art. 17, XXI' -> ["17"]."""
    out: list[str] = []
    for num, letra in _RE_ART.findall(texto or ""):
        a = num + (letra.replace(" ", "").upper() if letra else "")
        if a not in out:
            out.append(a)
    return out


def _chave_relacionada(norma: str) -> tuple[str | None, str | None]:
    if s := _RE_NORMA_SENADO.match(norma):
        tipo = TIPO_CAMARA.get(_sem_acento(s.group("tipo")))
        numero, ano = s.group("num").replace(".", ""), s.group("ano")
        return (f"BR:{tipo}:{numero}/{ano}" if tipo else None), f"{ano}-{s.group('mes')}-{s.group('dia')}"
    m = _RE_NORMA.match(norma)
    if not m:
        return None, None
    tipo = TIPO_CAMARA.get(_sem_acento(re.sub(r"\s*\(.*$", "", m.group("tipo"))))
    mes = MESES.get(_sem_acento(m.group("mes")))
    data = f"{m.group('ano')}-{mes:02d}-{int(m.group('dia')):02d}" if mes else None
    numero = m.group("num").replace(".", "")
    return (f"BR:{tipo}:{numero}/{m.group('ano')}" if tipo else None), data


def ler_ficha(pagina: str, url: str | None = None, chave_norma: str = "") -> Ficha:
    """A ficha 'Dados da Norma' da Legislação Informatizada da Câmara."""
    soup = BeautifulSoup(pagina, "html.parser")
    dados = soup.find(class_="dadosNorma")
    if dados is None:
        raise ErroVigencia(f"{url or chave_norma}: não é uma ficha da Legislação Informatizada")
    ementa_el = dados.find(class_="ementa")
    ementa = _texto(ementa_el)
    ementa = re.sub(r"^EMENTA:\s*", "", ementa, flags=re.I)
    situacao, vide = "", []
    for sessao in dados.find_all(class_="sessao"):
        rotulo = _sem_acento(_texto(sessao.find("strong")))
        if rotulo.startswith("situacao"):
            spans = sessao.find_all("span")
            situacao = _texto(spans[-1]) if spans else ""
        elif rotulo.startswith("vide norma"):
            vide = sessao.find_all("li")
    relacoes = []
    for li in vide:
        a = li.find("a")
        m = _RE_REL.match(_texto(a or li))
        if not m:
            continue
        norma = re.sub(r"\s*\((Poder [^)]+|[^)]*Executivo|[^)]*Legislativo)\)\s*$", "", m.group("norma")).strip()
        chave_rel, data = _chave_relacionada(norma)
        disp = m.group("disp").strip().rstrip(".").strip()
        relacoes.append(Relacao(norma=norma, chave=chave_rel, data=data, relacao=m.group("rel").strip(),
                                dispositivos=disp, artigos=artigos(disp),
                                url=_https_camara(urljoin(url, a["href"])) if a and a.get("href") and url else None))
    texto_url = original_url = None
    for a in dados.find_all("a", href=True):
        h = a["href"]
        if texto_url is None and re.search(r"-normaatualizada-p[a-z]\.html$", h):
            texto_url = urljoin(url, h) if url else h
        elif original_url is None and re.search(r"-publicacaooriginal-\d+-p[a-z]\.html$", h):
            original_url = urljoin(url, h) if url else h
    return Ficha(chave=chave_norma, titulo=_texto(dados.find("h1")), ementa=ementa, situacao=situacao,
                 revogada=_sem_acento(situacao).startswith("revogad"), relacoes=relacoes, ficha_url=url,
                 texto_url=texto_url and _https_camara(texto_url), original_url=original_url and _https_camara(original_url))


def _relacao_senado(comentario: str) -> str:
    c = _sem_acento(comentario)
    if "revogacao" in c:
        return "Revogação Parcial" if "parcial" in c or "no todo" not in c and "permanente da norma" not in c else "Revogação"
    for chave, rotulo in (("alteracao", "Alteração"), ("acrescimo", "Acréscimo"), ("regulamentacao", "Regulamentação"),
                          ("correlata", "Legislação Correlata"), ("prorrogacao", "Prorrogação")):
        if chave in c:
            return rotulo
    return comentario.strip()


def ler_senado_detalhe(xml: str, chave_norma: str = "", url: str | None = None) -> Ficha:
    """O detalhe de uma norma nos dados abertos do Senado: situação ("R" = revogada) e as normas posteriores
    que agiram sobre ela (vides), com os dispositivos. Usado quando o LexML não liga a norma à Câmara
    (decretos e leis recentes). Não traz texto consolidado."""
    with warnings.catch_warnings():     # o html.parser lê bem este XML simples; o aviso é só conselho
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(xml, "html.parser")
    doc = soup.find("documento")
    if doc is None:
        raise ErroVigencia(f"{url or chave_norma}: não é um detalhe de norma do Senado")
    situacao_cod = _texto(doc.find("situacao")).upper()
    relacoes = []
    for vide in doc.find_all("vide"):
        nome = _texto(vide.find("nomenormaposterior"))
        chave_rel, data = _chave_relacionada(nome)
        disp = "; ".join(_texto(i.find("dispositivo")) for i in vide.find_all("item"))
        cod = _texto(vide.find("codnormaposterior"))
        relacoes.append(Relacao(norma=nome, chave=chave_rel, data=data,
                                relacao=_relacao_senado(_texto(vide.find("comentario"))), dispositivos=disp,
                                artigos=artigos(disp), url=f"https://legis.senado.leg.br/norma/{cod}" if cod else None))
    relacoes.sort(key=lambda r: r.data or "", reverse=True)
    revogada = situacao_cod == "R" or any(r.relacao == "Revogação" for r in relacoes)
    ident = doc.find("identificacao")
    return Ficha(chave=chave_norma, titulo=_texto(ident.find("normanome")) if ident else "",
                 ementa=_texto(doc.find("ementa")), situacao="Revogada" if revogada else "Não consta revogação",
                 revogada=revogada, relacoes=relacoes, ficha_url=url, fonte=FONTE_SENADO)


def paragrafos_do_texto(pagina: str) -> list[str]:
    """Parágrafos do texto atualizado da Câmara, sem o que está riscado (revogado) e sem as notas
    "(Redação dada pela Lei ...)" no fim, que não fazem parte da norma."""
    soup = BeautifulSoup(pagina, "html.parser")
    for s in soup.find_all(["strike", "s", "del", "script", "style"]):
        s.decompose()
    corpo = soup.find(class_="texto") or soup.find(id="content") or soup.body or soup
    out = []
    for p in corpo.find_all(["p", "div"], recursive=True):
        if p.find(["p", "div"]):
            continue
        t = _texto(p)
        t = re.sub(r"\s*\((?:[A-Za-zçãáéíóúâêôõ ]+ )?(?:com )?reda[cç][aã]o dada pel[ao][^)]*\)\s*", " ", t, flags=re.I)
        t = re.sub(r"\s*\((?:[A-Za-zçãáéíóúâêôõ ]+ )?acrescid[oa] pel[ao][^)]*\)\s*", " ", t, flags=re.I)
        t = re.sub(r"\s+", " ", t).strip()
        if t and not re.fullmatch(r"\(?\s*revogad[oa][^)]*\)?\.?", t, flags=re.I):
            out.append(t)
    return out


# --------------------------------------------------------------------------- baixar


class Baixador:
    """Baixa com cache em disco e respeitando o intervalo de cada host (o LexML pede 5 s)."""

    def __init__(self, cache: Path = CACHE, http=None, refazer: bool = False):
        self.cache = cache
        self.http = http
        self.refazer = refazer
        self._ultimo: dict[str, float] = {}

    def _cliente(self):
        if self.http is None:
            import httpx

            self.http = httpx.Client(follow_redirects=True, timeout=60, headers={"User-Agent": AGENTE})
        return self.http

    def _arquivo(self, url: str) -> Path:
        nome = re.sub(r"[^A-Za-z0-9._-]+", "_", re.sub(r"^https?://", "", url))[-180:]
        return self.cache / nome

    def get(self, url: str) -> str:
        arq = self._arquivo(url)
        if arq.exists() and not self.refazer:
            return arq.read_text(encoding="utf-8")
        host = re.sub(r"^https?://([^/]+).*$", r"\1", url)
        espera = INTERVALO.get(host, 1.0) - (time.monotonic() - self._ultimo.get(host, -1e9))
        if espera > 0:
            time.sleep(espera)
        r = self._cliente().get(url)
        self._ultimo[host] = time.monotonic()
        if r.status_code != 200:
            raise ErroVigencia(f"{url}: HTTP {r.status_code}")
        texto = r.text
        self.cache.mkdir(parents=True, exist_ok=True)
        arq.write_text(texto, encoding="utf-8")
        return texto

    def ficha(self, chave_norma: str) -> Ficha:
        pagina = self.get(LEXML + urn(chave_norma))
        url = ficha_no_lexml(pagina)
        if url is not None:
            return ler_ficha(self.get(url), url, chave_norma)
        if sid := senado_no_lexml(pagina):
            return ler_senado_detalhe(self.get(SENADO_DETALHE.format(id=sid)),
                                      chave_norma, f"https://legis.senado.leg.br/norma/{sid}")
        raise ErroVigencia(f"{chave_norma}: o LexML não liga esta norma nem à Câmara nem ao Senado")

    def texto(self, ficha: Ficha) -> str | None:
        """O texto atualizado. Norma que nunca teve o texto mudado não tem página de texto atualizado na
        Câmara: aí a publicação original é o texto de hoje. Alterada e sem texto atualizado: None."""
        if ficha.texto_url:
            return self.get(ficha.texto_url)
        if ficha.original_url and not any(r.muda_texto for r in ficha.relacoes):
            return self.get(ficha.original_url)
        return None


# --------------------------------------------------------------------------- guardar


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def guardar(conn, f: Ficha) -> None:
    rel = json.dumps([asdict(r) for r in f.relacoes], ensure_ascii=False)
    conn.execute("DELETE FROM norma_vigencia WHERE chave = ?", (f.chave,))
    conn.execute(
        "INSERT INTO norma_vigencia (chave, titulo, ementa, situacao, revogada, relacoes, ficha_url, texto_url,"
        " original_url, fonte, lida_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (f.chave, f.titulo, f.ementa, f.situacao, 1 if f.revogada else 0, rel, f.ficha_url, f.texto_url,
         f.original_url, f.fonte, _agora()))


def lida(conn, chave_norma: str) -> Ficha | None:
    r = conn.execute("SELECT * FROM norma_vigencia WHERE chave = ?", (chave_norma,)).fetchone()
    if r is None:
        return None
    return Ficha(chave=r["chave"], titulo=r["titulo"], ementa=r["ementa"] or "", situacao=r["situacao"] or "",
                 revogada=bool(r["revogada"]), relacoes=[Relacao(**x) for x in json.loads(r["relacoes"] or "[]")],
                 ficha_url=r["ficha_url"], texto_url=r["texto_url"], original_url=r["original_url"],
                 fonte=r["fonte"] or FONTE)


def consultar(conn, baixador: Baixador, chave_norma: str) -> Ficha:
    f = baixador.ficha(chave_norma)
    with conn:
        guardar(conn, f)
    return f


# --------------------------------------------------------------------------- o catálogo


@dataclass
class Alteracao:
    por: str
    chave: str | None
    data: str | None
    relacao: str
    dispositivos: str
    artigos: list[str]
    afeta: list[str]          # códigos das obrigações do catálogo que citam um desses artigos
    url: str | None


@dataclass
class RevisaoNorma:
    norma: str                # como o catálogo escreve ("Lei 12.334/2010")
    chave: str
    situacao: str
    revogada: bool
    revogada_por: list[str]
    alteracoes: list[Alteracao]
    trechos_conferidos: int
    trechos_fora: list[str]   # códigos cujo trecho não está mais no texto atualizado
    texto_url: str | None
    ficha_url: str | None
    erro: str | None = None

    @property
    def precisa_curadoria(self) -> bool:
        return self.revogada or bool(self.trechos_fora) or self.erro is not None


def _citacoes(conn, norma: str) -> list[tuple[str, str, str]]:
    """(código, artigo, trecho) das obrigações públicas do catálogo desta norma, na versão em vigor."""
    rows = conn.execute(
        "SELECT o.codigo, v.artigo, v.trecho FROM obrigacao o JOIN obrigacao_versao v ON v.obrigacao_id = o.id"
        " WHERE o.norma = ? AND o.empresa IS NULL AND v.status = 'vigente' ORDER BY o.codigo", (norma,)).fetchall()
    return [(r["codigo"], r["artigo"] or "", r["trecho"] or "") for r in rows]


def revisar_norma(conn, baixador: Baixador, norma: str, chave_norma: str) -> RevisaoNorma:
    cits = _citacoes(conn, norma)
    try:
        f = consultar(conn, baixador, chave_norma)
        pagina = baixador.texto(f)
    except Exception as e:   # rede, ficha que mudou de formato: vira pendência visível, não some
        return RevisaoNorma(norma, chave_norma, "", False, [], [], 0, [], None, None, erro=str(e))
    alts = []
    for r in f.relacoes:
        if not r.muda_texto:
            continue
        afeta = [cod for cod, art, _ in cits if set(artigos(art)) & set(r.artigos)]
        alts.append(Alteracao(r.norma, r.chave, r.data, r.relacao, r.dispositivos, r.artigos, afeta, r.url))
    alts.sort(key=lambda a: a.data or "", reverse=True)
    fora, conferidos = [], 0
    if pagina:
        texto = _limpo(" ".join(paragrafos_do_texto(pagina)))
        for cod, _, trecho in cits:
            if trecho.strip():
                conferidos += 1
                if _limpo(trecho) not in texto:
                    fora.append(cod)
    return RevisaoNorma(norma, chave_norma, f.situacao, f.revogada, [r.norma for r in f.revogada_por], alts,
                        conferidos, fora, f.texto_url, f.ficha_url)


def revisar_catalogo(conn, baixador: Baixador) -> list[RevisaoNorma]:
    """Cada norma federal do catálogo (lei, LC, decreto, decreto-lei) contra a ficha e o texto da Câmara."""
    from .descoberta import catalogo

    out = []
    for chave_norma, item in sorted(catalogo(conn).items()):
        if suportada(chave_norma):
            out.append(revisar_norma(conn, baixador, item["norma"], chave_norma))
    return out


# --------------------------------------------------------------------------- a descoberta


@dataclass
class ResultadoCandidatas:
    lidas: int = 0
    revogadas: int = 0
    descartadas: int = 0
    aprovadas_revogadas: list[str] = field(default_factory=list)
    erros: dict[str, str] = field(default_factory=dict)


def marcar_candidatas(conn, baixador: Baixador, limite: int | None = None,
                      status: tuple[str, ...] = ("relevante", "aprovada", "nova")) -> ResultadoCandidatas:
    """Vigência das candidatas federais. Revogada e ainda não decidida sai da fila como descartada, com a
    fonte na nota; aprovada e revogada fica como está e entra no resultado, para a curadoria rever."""
    marcas = ",".join("?" * len(status))
    rows = conn.execute(
        f"SELECT chave, status FROM norma_candidata WHERE jurisdicao = 'BR' AND status IN ({marcas})"
        " AND chave NOT IN (SELECT chave FROM norma_vigencia) ORDER BY ano DESC, chave", status).fetchall()
    res = ResultadoCandidatas()
    for r in rows:
        if limite is not None and res.lidas >= limite:
            break
        if not suportada(r["chave"]):
            continue
        try:
            f = consultar(conn, baixador, r["chave"])
        except Exception as e:
            res.erros[r["chave"]] = str(e)
            continue
        res.lidas += 1
        if not f.revogada:
            continue
        res.revogadas += 1
        por = "; ".join(x.norma for x in f.revogada_por) or "revogação registrada sem a norma"
        with conn:
            conn.execute("UPDATE norma_candidata SET situacao = ? WHERE chave = ?", (f"Revogada ({por})", r["chave"]))
            if r["status"] == "aprovada":
                res.aprovadas_revogadas.append(r["chave"])
            else:
                conn.execute(
                    "UPDATE norma_candidata SET status = 'descartada', decidida_por = ?, decidida_em = ?, nota = ?"
                    " WHERE chave = ?",
                    ("vigência (Câmara dos Deputados)", _agora(), f"Revogada pela {por}. Fonte: {f.ficha_url}",
                     r["chave"]))
                res.descartadas += 1
    return res


def texto_atualizado(conn, baixador: Baixador, chave_norma: str) -> str | None:
    """Texto consolidado de uma norma federal, para a segunda leitura da triagem."""
    if not suportada(chave_norma):
        return None
    f = lida(conn, chave_norma) or consultar(conn, baixador, chave_norma)
    pagina = baixador.texto(f)
    return "\n".join(paragrafos_do_texto(pagina)) if pagina else None


# --------------------------------------------------------------------------- linha de comando


def _imprimir_revisao(revs: list[RevisaoNorma]) -> None:
    for r in revs:
        print(f"\n{r.norma} ({r.chave}): {r.erro or r.situacao}")
        if r.revogada:
            print(f"  REVOGADA por {', '.join(r.revogada_por) or '?'}")
        if r.trechos_conferidos:
            print(f"  trechos: {r.trechos_conferidos - len(r.trechos_fora)}/{r.trechos_conferidos} no texto atualizado"
                  + (f"; fora: {', '.join(r.trechos_fora)}" if r.trechos_fora else ""))
        for a in r.alteracoes[:8]:
            alvo = f" -> afeta {', '.join(a.afeta)}" if a.afeta else ""
            print(f"  {a.data or '?'} {a.relacao}: {a.por} [{', '.join(a.artigos) or a.dispositivos[:60]}]{alvo}")


def main(argv: list[str]) -> int:
    conn = db.conectar()
    b = Baixador(refazer="--refazer" in argv)
    if argv[:1] == ["catalogo"]:
        _imprimir_revisao(revisar_catalogo(conn, b))
        return 0
    if argv[:1] == ["candidatas"]:
        limite = int(argv[argv.index("--limite") + 1]) if "--limite" in argv else None
        res = marcar_candidatas(conn, b, limite)
        print(f"{res.lidas} lidas, {res.revogadas} revogadas, {res.descartadas} descartadas da fila;"
              f" aprovadas e revogadas: {res.aprovadas_revogadas or 'nenhuma'}; erros: {len(res.erros)}")
        return 0
    if argv[:1] == ["norma"] and len(argv) > 1:
        f = consultar(conn, b, argv[1])
        print(f"{f.titulo}: {f.situacao}\n{f.ementa}\ntexto: {f.texto_url}")
        for r in f.relacoes:
            print(f"  {r.data} {r.relacao}: {r.norma} {r.artigos}")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
