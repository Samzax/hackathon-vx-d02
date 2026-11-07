"""Descoberta de normas: quais normas já publicadas valem para os ativos das clientes.

O catálogo é da plataforma, e o radar do DOU cobre o que for publicado daqui para a frente. Faltava o
estoque: leis, decretos e resoluções em vigor que valem para os ativos da carteira e ainda não estão no
catálogo. Sem isso, uma cliente com barragem no Pará entraria sem a lei do Pará e ninguém perceberia.

1. Perfil: dos ativos de todas as clientes sai o que a plataforma precisa cobrir, por jurisdição e tipo
   de ativo (barragem em MG, barragem no Brasil, vaso de pressão no Brasil...).
2. Busca: cada fonte oficial com dados abertos lista as normas, ano a ano: o Senado (leis e decretos
   federais), o ANMlegis (resoluções da ANM) e a Assembleia de Minas (a legislação mineira, com a situação
   de vigência). Vira candidata a norma que cita os termos de um tipo de ativo da carteira (temas.toml);
   revogada não entra. Nada de IA aqui.
3. Triagem pela IA, pela ementa: a norma cobra algo de quem opera o ativo? De quais tipos de ativo?
4. Curadoria RegulaIA: aprova (vai para o extrator, que propõe as obrigações com o trecho literal, e
   para a curadoria) ou descarta, com nome e nota.
5. Cobertura: por cliente, cada jurisdição e tipo de ativo da carteira dela, com o que está catalogado,
   o que espera triagem ou curadoria, até quando cada fonte foi lida e as lacunas conhecidas.

O LexML, que indexa as normas de todos os estados, bloqueia acesso automático com uma verificação
anti-robô: não é usado. Estado sem conector aparece como "sem fonte automática", nunca como coberto.

Uso:
  uv run python -m regulaia.descoberta buscar [--desde ANO] [--fontes senado,anm,almg]
  uv run python -m regulaia.descoberta triar [--limite N] [--paralelo N] [--revisar]
      (paralelo: padrão 4, com Bedrock 1; revisar: relê pelo texto os descartes duvidosos)
  uv run python -m regulaia.descoberta cobertura [EMPRESA]
  uv run python -m regulaia.descoberta decidir CHAVE aprovar|descartar QUEM [NOTA]
  uv run python -m regulaia.descoberta exportar        (data/descoberta_demo.json, a fila da demo)
"""

from __future__ import annotations

import csv
import html
import io
import json
import re
import sys
import time
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from . import db
from .ia import Roteador, SemProvedor
from .triagem import normalizar

TEMAS = Path(__file__).with_name("temas.toml")
CACHE_FONTES = db.ROOT / "data" / "raw" / "fontes"      # respostas das fontes (fora do Git)
DEMO = db.ROOT / "data" / "descoberta_demo.json"         # a fila da demo (vai pro Git: só dado público)
USER_AGENT = "RegulaIA/0.1 (hackathon-vx-d02)"

SENADO = "https://legis.senado.leg.br/dadosabertos/legislacao/lista"
ALMG = "https://dadosabertos.almg.gov.br/arquivo/legislacao-mineira/download"
ANMLEGIS = "https://anmlegis.datalegis.net/action/ActionDatalegis.php"

# fonte -> (jurisdição, o que ela cobre, primeiro ano que tem)
FONTES = {
    "senado": ("BR", "leis, leis complementares, decretos-leis e decretos federais", 1967),
    "anm": ("BR", "resoluções da ANM", 2018),
    "almg": ("MG", "leis, leis complementares e decretos de Minas Gerais", 1989),
}
# fonte -> nome de tela ("Assembleia de Minas, 1989–2026, lida em ...")
NOMES_FONTES = {"senado": "Senado Federal", "anm": "ANMlegis (ANM)", "almg": "Assembleia de Minas"}
UFS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}
TIPOS_SENADO = ("LEI", "LCP", "DEL", "DEC")
TIPOS_ALMG = ("LEI", "LCP", "DEC")
STATUS = ("nova", "relevante", "irrelevante", "catalogada", "aprovada", "descartada")
VERSAO_PROMPT = "descoberta-1"
CONFIANCA_MINIMA = 0.7


class ErroDescoberta(ValueError):
    pass


def nome_jurisdicao(jurisdicao: str) -> str:
    """BR -> "Brasil (federal)"; MG -> "Minas Gerais"; o que não for UF fica como veio."""
    return "Brasil (federal)" if jurisdicao == "BR" else UFS.get(jurisdicao, jurisdicao)


@dataclass
class Candidata:
    chave: str                  # BR:LEI:12334/2010, MG:DEC:48078/2020, BR:RES-ANM:95/2022
    jurisdicao: str             # BR ou a UF
    fonte: str
    tipo: str
    numero: str
    ano: int
    titulo: str
    ementa: str = ""
    indexacao: str = ""         # assunto e indexação da ALMG, apelido do Senado
    data: str | None = None     # AAAA-MM-DD
    url: str | None = None
    situacao: str | None = None
    temas: list[str] = field(default_factory=list)


def chave(jurisdicao: str, tipo: str, numero: str, ano: int | str) -> str:
    return f"{jurisdicao}:{tipo}:{int(re.sub(r'\D', '', str(numero)) or 0)}/{ano}"


def _data_br(s: str | None) -> str | None:
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", (s or "").strip())
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def _milhar(numero: str) -> str:
    n = int(numero)
    return f"{n:,}".replace(",", ".")


# ----------------------------------------------------------------- temas e perfil


def temas(caminho: Path = TEMAS) -> dict:
    return tomllib.loads(caminho.read_text(encoding="utf-8"))


def tipos_de_ativo(cfg: dict) -> dict[str, dict]:
    return {k: v for k, v in cfg.items() if k not in ("lacunas", "descartar")}


def _padrao(termo: str) -> str:
    """'lavra' casa a palavra inteira; 'barrage*' casa o começo da palavra."""
    t = normalizar(termo)
    return r"\b" + (re.escape(t[:-1]) if t.endswith("*") else re.escape(t) + r"\b")


def temas_da(c: Candidata, cfg: dict) -> list[str]:
    """Tipos de ativo cujos termos aparecem na ementa ou na indexação (camada 0, sem IA)."""
    texto = normalizar(f"{c.ementa} {c.indexacao}")
    return [tipo for tipo, t in tipos_de_ativo(cfg).items()
            if any(re.search(_padrao(termo), texto) for termo in t["termos"])]


def descartada_pela_regra(c: Candidata, cfg: dict) -> bool:
    """Crédito orçamentário, utilidade pública, homenagem, concessão de lavra a uma empresa...: nunca
    cobra nada de quem opera o ativo. Espaço no fim do padrão conta ("concede a " não pega "concede anistia")."""
    regras = cfg.get("descartar", {})
    ementa = normalizar(c.ementa) + " "
    return (any(ementa.startswith(normalizar(p) + (" " if p.endswith(" ") else ""))
                for p in regras.get("ementa_comeca_com", []))
            or any(normalizar(p) in ementa for p in regras.get("ementa_contem", [])))


@dataclass(frozen=True)
class Necessidade:
    jurisdicao: str
    tipo_ativo: str


def perfil(conn, empresa_id: int | None = None, cfg: dict | None = None) -> dict[Necessidade, list[tuple]]:
    """{(jurisdição, tipo de ativo): [(empresa, código do ativo)]}. Todo ativo precisa da lei federal;
    o que tem UF precisa também da lei do estado. Tipo sem seção em temas.toml fica de fora."""
    cfg = cfg or temas()
    tipos = tipos_de_ativo(cfg)
    sql = "SELECT a.tipo, a.codigo, a.atributos, e.nome FROM ativo a JOIN empresa e ON e.id = a.empresa_id"
    args: tuple = ()
    if empresa_id is not None:
        sql, args = sql + " WHERE e.id = ?", (empresa_id,)
    out: dict[Necessidade, list[tuple]] = {}
    for r in conn.execute(sql + " ORDER BY e.nome, a.codigo", args):
        if r["tipo"] not in tipos:
            continue
        uf = (json.loads(r["atributos"] or "{}").get("uf") or "").strip().upper()
        for jur in ["BR"] + ([uf] if re.fullmatch(r"[A-Z]{2}", uf) else []):
            out.setdefault(Necessidade(jur, r["tipo"]), []).append((r["nome"], r["codigo"]))
    return out


# ------------------------------------------------------------------- o catálogo

_RE_NORMA = re.compile(
    r"^\s*(?P<tipo>lei complementar|lc|lei|decreto-lei|decreto|res\.|resolu[cç][aã]o)\s+"
    r"(?:(?P<orgao>anm|dc/anm)\s+|(?P<uf>[A-Z]{2})\s+)?(?:n[º°o.]*\s*)?(?P<num>[\d.]+)\s*/\s*(?P<ano>\d{4})",
    re.I)
_TIPOS_CATALOGO = {"lei complementar": "LCP", "lc": "LCP", "lei": "LEI", "decreto-lei": "DEL", "decreto": "DEC"}


def chave_da_norma(norma: str | None) -> str | None:
    """'Lei MG 23.291/2019' -> MG:LEI:23291/2019; 'Res. ANM 95/2022' -> BR:RES-ANM:95/2022.
    NR, licença e o que não for lei, decreto ou resolução da ANM: None."""
    m = _RE_NORMA.match(norma or "")
    if not m:
        return None
    t = m.group("tipo").lower()
    if t.startswith("res"):
        if not m.group("orgao"):
            return None
        tipo = "RES-ANM"
    else:
        tipo = _TIPOS_CATALOGO[t]
    uf = m.group("uf")
    if uf and uf.upper() != uf:        # "Lei mg ..." não é UF; o regex é sem diferença de maiúscula
        return None
    return chave(uf or "BR", tipo, m.group("num"), m.group("ano"))


def catalogo(conn) -> dict[str, dict]:
    """{chave: {norma, tipos_ativo}} das normas públicas do catálogo que dá para identificar."""
    out: dict[str, dict] = {}
    for r in conn.execute("SELECT DISTINCT norma, tipo_ativo FROM obrigacao WHERE empresa IS NULL"):
        if k := chave_da_norma(r["norma"]):
            item = out.setdefault(k, {"norma": r["norma"], "tipos_ativo": set()})
            item["tipos_ativo"].add(r["tipo_ativo"])
    return out


def normas_do_catalogo(conn, jurisdicao: str, tipo_ativo: str) -> list[str]:
    """Normas públicas do catálogo que valem na jurisdição para o tipo de ativo (inclusive as que a
    descoberta não identifica, como as NRs: federais)."""
    out = set()
    for r in conn.execute("SELECT DISTINCT norma FROM obrigacao WHERE empresa IS NULL AND tipo_ativo = ?",
                          (tipo_ativo,)):
        k = chave_da_norma(r["norma"])
        jur = k.split(":")[0] if k else "BR"
        if jur == jurisdicao and r["norma"]:
            out.add(r["norma"])
    return sorted(out)


# ------------------------------------------------------------------- as fontes


def ler_senado(xml: bytes) -> list[Candidata]:
    raiz = ET.fromstring(xml)
    out = []
    for d in raiz.iter("documento"):
        def txt(tag: str, d=d) -> str:
            return (d.findtext(tag) or "").strip()
        tipo = txt("tipo").split("-")[0].upper()
        numero, ano = txt("numero"), txt("anoassinatura")
        if not numero.isdigit() or not ano.isdigit():
            continue        # decreto sem número: ato de efeito concreto (nomeação, crédito...), não norma geral
        out.append(Candidata(
            chave("BR", tipo, numero, ano), "BR", "senado", tipo, numero, int(ano),
            txt("normaNome") or f"{tipo} {numero}/{ano}", txt("ementa"),
            indexacao=txt("apelido"), data=_data_br(txt("dataassinatura")),
            url=f"https://legis.senado.leg.br/norma/{d.get('id')}" if d.get("id") else None))
    return out


_NOMES_ALMG = {"LEI": "Lei", "LCP": "Lei Complementar", "DEC": "Decreto"}


def ler_almg(conteudo: bytes) -> list[Candidata]:
    texto = conteudo.decode("utf-8-sig")
    out = []
    for r in csv.DictReader(io.StringIO(texto)):
        tipo = (r.get("Tipo") or "").strip().upper()
        numero, ano = (r.get("Numero") or "").strip(), (r.get("Ano") or "").strip()
        if tipo not in TIPOS_ALMG or not numero.isdigit() or not ano.isdigit() or (r.get("Complemento") or "").strip():
            continue
        out.append(Candidata(
            chave("MG", tipo, numero, ano), "MG", "almg", tipo, numero, int(ano),
            f"{_NOMES_ALMG[tipo]} MG {_milhar(numero)}/{ano}", " ".join((r.get("Ementa") or "").split()),
            indexacao=" ".join(f"{r.get('AssuntoGeral') or ''} {r.get('Indexacao') or ''} {r.get('Resumo') or ''}".split()),
            data=_data_br(r.get("DataLegislacao")),
            url=f"https://www.almg.gov.br/legislacao-mineira/texto/{tipo}/{numero}/{ano}/",
            situacao=(r.get("Situacao") or "").strip().upper() or None))
    return out


_RE_ATO_ANM = re.compile(
    r'href="(?P<href>[^"]*abrirTextoAto[^"]*?tipo=(?P<tipo>[A-Z]+)&(?:amp;)?numeroAto=(?P<num>\d+)'
    r'&(?:amp;)?seqAto=[^&"]*&(?:amp;)?valorAno=(?P<ano>\d{4})[^"]*)"[^>]*>.*?<strong>(?P<titulo>.*?)</strong>'
    r'.*?<p(?: [^>]*)?>(?P<ementa>.*?)</p>', re.S)


def _texto_html(s: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def ler_anm(pagina: str) -> list[Candidata]:
    """Uma <article> por ato. Revogada vem marcada (ícone e "Revogada pela Resolução..." na ementa)."""
    from .triagem import MESES

    out, vistas = [], set()
    for bloco in pagina.split("<article")[1:]:
        m = _RE_ATO_ANM.search(bloco)
        if not m or m.group("tipo") != "RES":
            continue
        if (k := chave("BR", "RES-ANM", m.group("num"), m.group("ano"))) in vistas:
            continue
        vistas.add(k)
        titulo, ementa = _texto_html(m.group("titulo")), _texto_html(m.group("ementa"))
        revogada = "ico-revogado" in bloco or re.search(r"\bRevogad[ao] pel[ao]\b", ementa)
        ementa = re.split(r"\s*\bRevogad[ao] pel[ao]\b", ementa)[0].strip()
        data = None
        if (md := re.search(r"DE (\d{1,2}) DE (\w+) DE (\d{4})", normalizar(titulo).upper())) and (
                mes := MESES.get(md.group(2).lower())):
            data = f"{md.group(3)}-{mes:02d}-{int(md.group(1)):02d}"
        href = html.unescape(m.group("href")).replace("&link=S", "")
        out.append(Candidata(
            k, "BR", "anm", "RES-ANM", str(int(m.group("num"))), int(m.group("ano")), titulo, ementa, data=data,
            url=("https://anmlegis.datalegis.net" + href) if href.startswith("/") else href,
            situacao="REVOGADA" if revogada else "VIGENTE"))
    return out


class Baixador:
    """Busca nas fontes com cache em disco: ano passado não muda, o ano corrente é lido de novo.
    Um pedido por vez, com pausa: são serviços públicos."""

    def __init__(self, pasta: Path = CACHE_FONTES, http=None, pausa_s: float = 0.4, hoje: date | None = None):
        import httpx

        self.pasta, self.pausa_s, self.hoje = pasta, pausa_s, hoje or date.today()
        self.http = http or httpx.Client(follow_redirects=True, timeout=90, headers={"User-Agent": USER_AGENT})
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.vigencia = None     # vigencia.Baixador, criado no primeiro texto federal

    def _cache(self, nome: str, ano: int, baixar) -> bytes:
        arq = self.pasta / nome
        if arq.exists() and ano < self.hoje.year:
            return arq.read_bytes()
        conteudo = baixar()
        arq.write_bytes(conteudo)
        time.sleep(self.pausa_s)
        return conteudo

    def senado(self, tipo: str, ano: int) -> list[Candidata]:
        def baixar():
            r = self.http.get(SENADO, params={"tipo": tipo, "ano": str(ano)})
            r.raise_for_status()
            return r.content
        return ler_senado(self._cache(f"senado_{tipo}_{ano}.xml", ano, baixar))

    def almg(self, ano: int) -> list[Candidata]:
        def baixar():
            r = self.http.get(ALMG, params={"ano": str(ano), "tipo": "CSV"})
            r.raise_for_status()
            if b"Tipo" not in r.content[:200]:
                raise ErroDescoberta(f"a ALMG não devolveu o CSV de {ano}")
            return r.content
        return ler_almg(self._cache(f"almg_{ano}.csv", ano, baixar))

    def anm(self, ano: int) -> list[Candidata]:
        """A lista do ANMlegis vem em páginas, guardadas na sessão do servidor: abre o ano e pede a
        próxima página até vir vazia."""
        def baixar():
            menu = {"cod_modulo": "351", "cod_menu": "8731"}
            r = self.http.get(ANMLEGIS, params={"acao": "abrirResenhaAnoData", "ano": str(ano), **menu})
            r.raise_for_status()
            paginas = [r.content.decode("cp1252", errors="replace")]
            for _ in range(60):
                time.sleep(self.pausa_s)
                p = self.http.post(ANMLEGIS, params={"acao": "paginaResenhaAno", **menu})
                p.raise_for_status()
                texto = p.content.decode("cp1252", errors="replace")
                if "abrirTextoAto" not in texto:
                    break
                paginas.append(texto)
            return "\n".join(paginas).encode("utf-8")
        return ler_anm(self._cache(f"anm_res_{ano}.html", ano, baixar).decode("utf-8"))


    def texto(self, linha: dict, limite: int = 9000) -> str | None:
        """O começo do texto oficial, do artigo 1º em diante, para a segunda leitura da triagem. A ALMG e o
        ANMlegis servem a página sem verificação. A lei federal vem do texto atualizado da Câmara
        (regulaia/vigencia.py; o Planalto derruba robô); sem ficha na Câmara, None, e fica a decisão pela
        ementa."""
        if linha["fonte"] == "senado":
            return self._texto_federal(linha, limite)
        if linha["fonte"] not in ("almg", "anm") or not linha.get("url"):
            return None
        arq = self.pasta / ("texto_" + re.sub(r"[^A-Za-z0-9]+", "_", linha["chave"]) + ".txt")
        if arq.exists():
            return arq.read_text(encoding="utf-8")[:limite]
        r = self.http.get(linha["url"])
        r.raise_for_status()
        bruto = r.text if linha["fonte"] == "almg" else r.content.decode("cp1252", errors="replace")
        corpo = texto_da_pagina(bruto)
        arq.write_text(corpo, encoding="utf-8")
        time.sleep(self.pausa_s)
        return corpo[:limite] or None

    def _texto_federal(self, linha: dict, limite: int) -> str | None:
        """Lei, decreto, decreto-lei e LC federais: o texto atualizado da Câmara, pela ficha que o LexML
        aponta. Ficha sem texto (a do Senado, para decreto recente) ou falha: None."""
        from . import vigencia

        if not vigencia.suportada(linha["chave"]):
            return None
        arq = self.pasta / ("texto_" + re.sub(r"[^A-Za-z0-9]+", "_", linha["chave"]) + ".txt")
        if arq.exists():
            return arq.read_text(encoding="utf-8")[:limite] or None
        if self.vigencia is None:
            self.vigencia = vigencia.Baixador()
        try:
            pagina = self.vigencia.texto(self.vigencia.ficha(linha["chave"], linha.get("url")))
        except vigencia.ErroVigencia:
            return None
        if not pagina:
            return None
        corpo = " ".join(vigencia.paragrafos_do_texto(pagina))
        m = re.search(r"\bArt\.? ?1\s?[ºo°]", corpo)
        corpo = corpo[m.start():] if m else corpo
        arq.write_text(corpo, encoding="utf-8")
        return corpo[:limite] or None


def texto_da_pagina(pagina: str) -> str:
    """Página de norma -> texto corrido a partir do "Art. 1º"."""
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", pagina, flags=re.S | re.I)
    s = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())
    m = re.search(r"\bArt\.? ?1\s?[ºo°]", s)
    return s[m.start():] if m else s


# ------------------------------------------------------------------- a fila


def _registrar_busca(conn, fonte: str, desde: int, ate: int, lidas: int, candidatas: int) -> None:
    conn.execute(
        "INSERT INTO descoberta_busca (fonte, jurisdicao, desde, ate, lidas, candidatas, em) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (fonte) DO UPDATE SET jurisdicao = excluded.jurisdicao, "
        "desde = excluded.desde, ate = excluded.ate, lidas = excluded.lidas, candidatas = excluded.candidatas, "
        "em = excluded.em",
        (fonte, FONTES[fonte][0], desde, ate, lidas, candidatas, db.agora()))


def guardar(conn, cands: list[Candidata]) -> int:
    """Grava ou atualiza as candidatas (o que a fonte diz); triagem e decisão já feitas ficam."""
    for c in cands:
        conn.execute(
            "INSERT INTO norma_candidata (chave, jurisdicao, fonte, tipo, numero, ano, titulo, ementa, indexacao, "
            "data, url, situacao, temas) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (chave) DO UPDATE SET titulo = excluded.titulo, ementa = excluded.ementa, "
            "indexacao = excluded.indexacao, data = excluded.data, url = excluded.url, "
            "situacao = excluded.situacao, temas = excluded.temas",
            (c.chave, c.jurisdicao, c.fonte, c.tipo, c.numero, c.ano, c.titulo, c.ementa, c.indexacao, c.data,
             c.url, c.situacao, json.dumps(c.temas, ensure_ascii=False)))
    return len(cands)


def marcar_catalogadas(conn) -> int:
    """A norma que já está no catálogo sai da fila, decidida ou não."""
    n = 0
    for k in catalogo(conn):
        n += conn.execute("UPDATE norma_candidata SET status = 'catalogada' WHERE chave = ? AND status <> 'catalogada'",
                          (k,)).rowcount
    return n


def filtrar(cands: list[Candidata], cfg: dict, tipos: set[str]) -> tuple[list[Candidata], dict[str, int]]:
    """Camada 0: fica a vigente que cita os termos de um tipo de ativo da carteira e não é do tipo que
    nunca cobra nada (crédito, homenagem...). Devolve também quantas saíram por cada motivo."""
    out, fora = [], {"revogadas": 0, "pela_regra": 0}
    for c in cands:
        c.temas = [t for t in temas_da(c, cfg) if t in tipos]
        if not c.temas:
            continue
        if c.situacao and c.situacao != "VIGENTE":
            fora["revogadas"] += 1
        elif descartada_pela_regra(c, cfg):
            fora["pela_regra"] += 1
        else:
            out.append(c)
    return out, fora


@dataclass
class ResultadoBusca:
    fonte: str
    lidas: int = 0
    candidatas: int = 0
    revogadas: int = 0
    pela_regra: int = 0
    falhas: list[str] = field(default_factory=list)


_RE_CITA = re.compile(
    r"\b(lei complementar|decreto-lei|decreto|lei|resolucao anm|resolucao)\s+(?:estadual\s+|federal\s+)?"
    r"(?:n[o.]*\s*)?([\d.]+)\s*(?:,\s*de\s+\d{1,2}o?\s+de\s+[a-z]+\s+de\s+|/)(\d{4})")
_TIPOS_CITADOS = {"lei complementar": "LCP", "decreto-lei": "DEL", "decreto": "DEC", "lei": "LEI",
                  "resolucao anm": "RES-ANM", "resolucao": "RES-ANM"}


def citadas(c: Candidata) -> set[str]:
    """Chaves das normas que a ementa cita ("Regulamenta o Decreto-Lei nº 227, de 28 de fevereiro de
    1967"): na jurisdição da própria norma e na federal, porque um decreto mineiro regulamenta lei federal."""
    out = set()
    for tipo, num, ano in _RE_CITA.findall(normalizar(c.ementa)):
        t = _TIPOS_CITADOS[tipo]
        if t == "RES-ANM":
            out.add(chave("BR", t, num, ano))
            continue
        out.update({chave(c.jurisdicao, t, num, ano), chave("BR", t, num, ano)})
    return out


def _ler_fonte(baixador: Baixador, fonte: str, ano: int) -> list[Candidata]:
    if fonte == "senado":
        return [c for t in TIPOS_SENADO for c in baixador.senado(t, ano)]
    if fonte == "almg":
        return baixador.almg(ano)
    return baixador.anm(ano)


def buscar(conn, baixador: Baixador, fontes: tuple[str, ...] = tuple(FONTES), desde: int | None = None,
           ate: int | None = None, cfg: dict | None = None) -> list[ResultadoBusca]:
    """Lê as fontes das jurisdições que a carteira precisa e grava as candidatas da camada 0.

    Duas passadas, nenhuma com IA: (1) a norma que cita os termos de um tipo de ativo da carteira;
    (2) a que regulamenta ou altera uma norma já candidata ou já no catálogo, pela citação na ementa,
    até não aparecer mais nenhuma. A segunda pega o Decreto 9.406/2018, cuja ementa ("Regulamenta o
    Decreto-Lei nº 227...") não tem palavra nenhuma de mineração."""
    cfg = cfg or temas()
    precisa = perfil(conn, cfg=cfg)
    ate = ate or baixador.hoje.year
    resultados: dict[str, ResultadoBusca] = {}
    todas: list[Candidata] = []
    tipos_por_jur: dict[str, set[str]] = {}
    for fonte in fontes:
        jur, _, primeiro = FONTES[fonte]
        tipos = {n.tipo_ativo for n in precisa if n.jurisdicao == jur}
        if not tipos:
            continue        # nenhuma cliente com ativo nessa jurisdição
        tipos_por_jur[jur] = tipos
        res = resultados[fonte] = ResultadoBusca(fonte)
        for ano in range(max(desde or primeiro, primeiro), ate + 1):
            try:
                lidas = _ler_fonte(baixador, fonte, ano)
            except Exception as e:      # uma fonte fora do ar não derruba as outras; fica registrado
                res.falhas.append(f"{ano}: {type(e).__name__}: {str(e)[:120]}")
                continue
            res.lidas += len(lidas)
            todas.extend(lidas)

    # passada 1: termos
    ficam: dict[str, Candidata] = {}
    for c in todas:
        dentro, fora = filtrar([c], cfg, tipos_por_jur[c.jurisdicao])
        resultados[c.fonte].revogadas += fora["revogadas"]
        resultados[c.fonte].pela_regra += fora["pela_regra"]
        if dentro:
            ficam[c.chave] = c
    # passada 2: citação de norma conhecida (o tema vem da citada)
    temas_conhecidos: dict[str, set[str]] = {k: set(v["tipos_ativo"]) for k, v in catalogo(conn).items()}
    for r in conn.execute("SELECT chave, temas FROM norma_candidata WHERE status NOT IN ('irrelevante', 'descartada')"):
        temas_conhecidos.setdefault(r["chave"], set()).update(json.loads(r["temas"] or "[]"))
    conn.commit()
    for k, c in ficam.items():
        temas_conhecidos.setdefault(k, set()).update(c.temas)
    resto = [c for c in todas if c.chave not in ficam and (not c.situacao or c.situacao == "VIGENTE")
             and not descartada_pela_regra(c, cfg)]
    for _ in range(5):
        novas = 0
        for c in resto:
            if c.chave in ficam:
                continue
            herdados = set().union(*(temas_conhecidos.get(k, set()) for k in citadas(c)))
            herdados &= tipos_por_jur[c.jurisdicao]
            if herdados:
                c.temas = sorted(herdados)
                ficam[c.chave] = c
                temas_conhecidos.setdefault(c.chave, set()).update(herdados)
                novas += 1
        if not novas:
            break

    por_fonte: dict[str, list[Candidata]] = {}
    for c in ficam.values():
        por_fonte.setdefault(c.fonte, []).append(c)
    for fonte, res in resultados.items():
        res.candidatas = guardar(conn, por_fonte.get(fonte, []))
        with conn:
            if not res.falhas:
                jur, _, primeiro = FONTES[fonte]
                _registrar_busca(conn, fonte, max(desde or primeiro, primeiro), ate, res.lidas, res.candidatas)
    with conn:
        marcar_catalogadas(conn)
    return list(resultados.values())


# ------------------------------------------------------------------- triagem (IA)

SISTEMA = """Você faz a triagem de normas para a RegulaIA, uma torre de controle regulatório de mineradoras.
Recebe a identificação, a ementa e a indexação de uma norma brasileira e os tipos de ativo da carteira.
Decida se a norma impõe dever, prazo, proibição, documento, inspeção, cadastro, comunicação, pagamento
ou outra obrigação a quem opera algum desses ativos (o empreendedor, a mineradora).

Não é relevante: norma que só organiza o Estado (cria órgão, cargo, fundo ou programa), concede
benefício, declara utilidade pública ou trata de um empreendimento específico de outra pessoa, nomeia,
abre crédito orçamentário, cuida de barragem que não é de mineração (hidrelétrica, açude, irrigação)
sem cobrar nada da mineradora, ou só institui data comemorativa.

Responda só com JSON:
{"relevante": true|false,
 "tipos_ativo": ["tipos da lista que a norma alcança; vazio se não for relevante"],
 "deveres": "uma frase com o que a norma cobra do empreendedor; vazio se não for relevante",
 "motivo": "uma frase com a razão da decisão",
 "confianca": número de 0 a 1}
Na dúvida entre relevante e não relevante, marque relevante com confiança baixa: a curadoria lê tudo
o que for relevante, e o que for descartado aqui não chega a ninguém."""


# Segunda leitura: a ementa de "Institui a Política Estadual dos Atingidos por Barragens" parece só
# organização do Estado; o dever está no corpo da lei. Descarte com confiança abaixo deste valor relê
# pelo texto oficial, onde a fonte deixa baixar (ALMG e ANMlegis; o Planalto bloqueia robô).
CONFIANCA_DESCARTE = 0.85
VERSAO_PROMPT_TEXTO = "descoberta-texto-1"
SISTEMA_TEXTO = SISTEMA + """

Desta vez vem também o começo do texto oficial da norma (campo "texto"). Decida pelo texto, não pela
ementa: procure artigo que mande o empreendedor, o responsável pela barragem ou o titular de direito
minerário fazer, pagar, apresentar, manter, comunicar ou deixar de fazer algo. Se achar, cite o artigo
em "deveres"."""


@dataclass
class Triagem:
    relevante: bool
    tipos_ativo: list[str]
    deveres: str
    motivo: str
    confianca: float
    modelo: str
    custo_usd: float
    leu_texto: bool = False     # a decisão saiu do texto oficial, não só da ementa


def _ler_triagem(dados: dict, tipos: set[str]) -> tuple[bool, list[str], str, str, float]:
    if not isinstance(dados.get("relevante"), bool):
        raise ErroDescoberta("resposta sem 'relevante' booleano")
    alcance = [t for t in dados.get("tipos_ativo") or [] if t in tipos]
    try:
        confianca = max(0.0, min(1.0, float(dados.get("confianca", 0))))
    except (TypeError, ValueError):
        confianca = 0.0
    relevante = dados["relevante"]
    if relevante and not alcance:
        confianca = min(confianca, 0.5)         # relevante para nada da carteira: a curadoria olha
    return relevante, alcance, str(dados.get("deveres") or ""), str(dados.get("motivo") or ""), confianca


def _pedir(roteador: Roteador, sistema: str, usuario: str, versao: str, tipos: set[str],
           leu_texto: bool) -> Triagem:
    """Camada 2; se a confiança vier baixa, camada 3. Devolve a última resposta válida."""
    falhas, ultima = [], None
    for camada in (2, 3):
        try:
            r = roteador.pedir_json("descoberta", camada, sistema, usuario, versao, max_tokens=3000)
            relevante, alcance, deveres, motivo, conf = _ler_triagem(r.dados, tipos)
        except (SemProvedor, ErroDescoberta) as e:
            falhas.append(f"camada {camada}: {e}")
            continue
        ultima = Triagem(relevante, alcance, deveres, motivo, conf, r.modelo.rotulo + (" (cache)" if r.do_cache else ""),
                         0.0 if r.do_cache else r.custo_usd, leu_texto)
        if conf >= CONFIANCA_MINIMA:
            return ultima
    if ultima is None:
        raise SemProvedor("; ".join(falhas))
    return ultima


def triar_uma(roteador: Roteador, linha: dict, cfg: dict, texto=None) -> Triagem:
    """Pela ementa; descarte com confiança abaixo de CONFIANCA_DESCARTE relê pelo texto oficial, se
    `texto(linha)` devolver o texto."""
    tipos = tipos_de_ativo(cfg)
    pedido = {
        "norma": linha["titulo"], "jurisdicao": "federal" if linha["jurisdicao"] == "BR" else linha["jurisdicao"],
        "ementa": linha["ementa"], "indexacao": (linha.get("indexacao") or "")[:1500],
        "tipos_de_ativo": {t: v["descricao"] for t, v in tipos.items()},
    }
    t = _pedir(roteador, SISTEMA, json.dumps(pedido, ensure_ascii=False, indent=1), VERSAO_PROMPT, set(tipos), False)
    if t.relevante or t.confianca >= CONFIANCA_DESCARTE or texto is None:
        return t
    try:
        corpo = texto(linha)
    except Exception:           # fonte fora do ar: fica a decisão pela ementa
        corpo = None
    if not corpo:
        return t
    segunda = _pedir(roteador, SISTEMA_TEXTO, json.dumps(pedido | {"texto": corpo}, ensure_ascii=False, indent=1),
                     VERSAO_PROMPT_TEXTO, set(tipos), True)
    segunda.custo_usd += t.custo_usd
    return segunda


def _tentar(f, *args):
    """Resultado ou a falha de provedor, para tratar na linha principal."""
    try:
        return f(*args)
    except SemProvedor as e:
        return e


def triar(conn, roteador: Roteador, limite: int | None = None, cfg: dict | None = None,
          paralelo: int = 1, novo_roteador=None, texto=None, revisar: bool = False) -> dict:
    """Passa pela IA as candidatas novas. A que falhar (resposta inválida em todos os modelos) fica
    'nova' para a próxima rodada; sem provedor, teto do dia ou cinco falhas seguidas, para.

    `paralelo` > 1 com `novo_roteador` (um Roteador por linha de execução, cada um com a sua conexão de
    cache): várias normas ao mesmo tempo. Com Bedrock no ar, sempre uma por vez: a regra do evento é
    menos de 1 pedido por segundo, e cada Roteador só controla o próprio ritmo.

    `texto(linha)`: o texto oficial, para a segunda leitura dos descartes duvidosos. `revisar`: em vez das
    novas, passa de novo os descartes duvidosos que ainda não leram o texto (a ementa vem do cache)."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from .ia import TetoAtingido

    cfg = cfg or temas()
    status = "irrelevante" if revisar else "nova"
    sql = "SELECT * FROM norma_candidata WHERE status = ? ORDER BY jurisdicao, ano DESC, chave"
    linhas = [dict(r) for r in conn.execute(sql, (status,))]
    conn.commit()
    if revisar:
        def duvidosa(linha: dict) -> bool:
            t = json.loads(linha["triagem"] or "{}")
            return not t.get("leu_texto") and t.get("confianca", 0) < CONFIANCA_DESCARTE
        linhas = [linha for linha in linhas if duvidosa(linha)]
    if limite is not None:
        linhas = linhas[:limite]
    if "bedrock" in getattr(roteador, "provedores", {}) or novo_roteador is None:
        paralelo = 1
    local = threading.local()

    def uma(linha: dict) -> Triagem:
        if paralelo == 1:
            return triar_uma(roteador, linha, cfg, texto)
        if not hasattr(local, "roteador"):
            local.roteador = novo_roteador()
        return triar_uma(local.roteador, linha, cfg, texto)

    if paralelo == 1:       # na linha principal: o cache pode ser a mesma conexão do banco
        resultados = ((linha, _tentar(uma, linha)) for linha in linhas)
        pool = None
    else:
        pool = ThreadPoolExecutor(max_workers=paralelo)
        futuros = {pool.submit(uma, linha): linha for linha in linhas}
        resultados = ((futuros[f], _tentar(f.result)) for f in as_completed(futuros))
    feitas, custo, falhas, seguidas, erro = 0, 0.0, [], 0, None
    try:
        for linha, t in resultados:
            if isinstance(t, SemProvedor):
                e = t
                if isinstance(e, TetoAtingido) or "nenhum provedor" in str(e) or seguidas >= 4:
                    erro = str(e)
                    break
                falhas.append(f"{linha['chave']}: {str(e)[:200]}")
                seguidas += 1
                continue
            seguidas = 0
            feitas += 1
            custo += t.custo_usd
            if revisar:     # a leitura pela ementa veio do cache: o que ela custou na primeira rodada continua
                t.custo_usd += json.loads(linha["triagem"] or "{}").get("custo_usd", 0.0)
            with conn:
                conn.execute("UPDATE norma_candidata SET status = ?, triagem = ? WHERE chave = ? AND status = ?",
                             ("relevante" if t.relevante else "irrelevante",
                              json.dumps(asdict(t), ensure_ascii=False), linha["chave"], status))
    finally:
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)
    restam = conn.execute("SELECT COUNT(*) FROM norma_candidata WHERE status = 'nova'").fetchone()[0]
    conn.commit()
    return {"triadas": feitas, "custo_usd": round(custo, 6), "restam": restam, "falhas": falhas, "erro": erro}


# ------------------------------------------------------------------- curadoria


def decidir(conn, chave_norma: str, decisao: str, por: str, nota: str | None = None) -> dict:
    """Curadoria RegulaIA: aprovar (a norma vai para o extrator) ou descartar. Vale também para a que
    a IA achou irrelevante: a pessoa pode discordar. Catalogada não se decide."""
    if decisao not in ("aprovar", "descartar"):
        raise ErroDescoberta("decisão é 'aprovar' ou 'descartar'")
    if not (por or "").strip():
        raise ErroDescoberta("quem decide é obrigatório")
    r = conn.execute("SELECT status FROM norma_candidata WHERE chave = ?", (chave_norma,)).fetchone()
    if r is None:
        raise ErroDescoberta(f"norma não encontrada na fila: {chave_norma}")
    if r["status"] == "catalogada":
        raise ErroDescoberta(f"{chave_norma} já está no catálogo")
    if r["status"] == "nova":
        raise ErroDescoberta(f"{chave_norma} ainda não passou pela triagem")
    novo = "aprovada" if decisao == "aprovar" else "descartada"
    with conn:
        conn.execute("UPDATE norma_candidata SET status = ?, decidida_por = ?, decidida_em = ?, nota = ? "
                     "WHERE chave = ?", (novo, por.strip(), db.agora(), (nota or "").strip() or None, chave_norma))
    return candidata(conn, chave_norma)


def _linha(r, cat: dict | None = None) -> dict:
    """Com `cat` (o catálogo), diz também quais normas do catálogo a ementa cita: quem altera a Res. 95
    pode já estar no texto consolidado que o catálogo usa, e a curadoria confere antes de extrair."""
    d = dict(r)
    d["temas"] = json.loads(d.get("temas") or "[]")
    d["triagem"] = json.loads(d["triagem"]) if d.get("triagem") else None
    if cat is not None:
        cita = citadas(Candidata(d["chave"], d["jurisdicao"], d["fonte"], d["tipo"], d["numero"], d["ano"],
                                 d["titulo"], d.get("ementa") or ""))
        d["cita_catalogo"] = sorted(cat[k]["norma"] for k in cita if k in cat and k != d["chave"])
    return d


def candidata(conn, chave_norma: str) -> dict | None:
    cat = catalogo(conn)
    r = conn.execute("SELECT * FROM norma_candidata WHERE chave = ?", (chave_norma,)).fetchone()
    conn.commit()
    return _linha(r, cat) if r else None


def fila(conn, status: tuple[str, ...] = ("relevante",), jurisdicao: str | None = None) -> list[dict]:
    """Para a curadoria: relevantes primeiro pela confiança mais baixa (as que mais precisam de olho)."""
    marcas = ",".join("?" * len(status))
    sql = f"SELECT * FROM norma_candidata WHERE status IN ({marcas})"
    args: list = list(status)
    if jurisdicao:
        sql += " AND jurisdicao = ?"
        args.append(jurisdicao)
    cat = catalogo(conn)
    linhas = [_linha(r, cat) for r in conn.execute(sql + " ORDER BY jurisdicao, ano DESC, chave", args)]
    conn.commit()
    return sorted(linhas, key=lambda d: (d["jurisdicao"], (d["triagem"] or {}).get("confianca", 0)))


# ------------------------------------------------------------------- cobertura


@dataclass
class ItemCobertura:
    jurisdicao: str
    tipo_ativo: str
    ativos: list[str]
    fontes: list[dict]          # [{fonte, cobre, desde, ate, em}] das fontes lidas para a jurisdição
    sem_fonte: bool             # nenhuma fonte automática: a cobertura não foi verificada
    lacunas: list[str]          # o que a plataforma sabe que não cobre nessa jurisdição
    catalogadas: list[str]
    triagem_pendente: int
    em_curadoria: list[dict]    # relevantes ainda não decididas
    aprovadas: list[dict]       # aprovadas, esperando a extração das obrigações
    estado: str                 # sem_fonte | nao_buscada | triagem_pendente | curadoria_pendente |
                                # extracao_pendente | coberta


def _alcanca(c: dict, nec: Necessidade) -> bool:
    """A candidata vale para a necessidade: mesma jurisdição e o tipo de ativo que a IA (ou, antes da
    triagem, os termos) apontou."""
    if c["jurisdicao"] != nec.jurisdicao:
        return False
    if c["triagem"]:
        return nec.tipo_ativo in (c["triagem"].get("tipos_ativo") or c["temas"])
    return nec.tipo_ativo in c["temas"]


def cobertura(conn, empresa_id: int | None = None, cfg: dict | None = None) -> list[ItemCobertura]:
    cfg = cfg or temas()
    buscas = {r["fonte"]: dict(r) for r in conn.execute("SELECT * FROM descoberta_busca")}
    cat = catalogo(conn)
    candidatas = [_linha(r, cat) for r in conn.execute(
        "SELECT * FROM norma_candidata WHERE status IN ('nova', 'relevante', 'aprovada')")]
    conn.commit()
    itens = []
    for nec, ativos in sorted(perfil(conn, empresa_id, cfg).items(),
                              key=lambda kv: (kv[0].jurisdicao != "BR", kv[0].jurisdicao, kv[0].tipo_ativo)):
        conectores = [f for f, (jur, _, _) in FONTES.items() if jur == nec.jurisdicao]
        lidas = [{"fonte": f, "cobre": FONTES[f][1], "desde": buscas[f]["desde"], "ate": buscas[f]["ate"],
                  "em": buscas[f]["em"]} for f in conectores if f in buscas]
        minhas = [c for c in candidatas if _alcanca(c, nec)]
        resumo = [{"chave": c["chave"], "titulo": c["titulo"], "ementa": c["ementa"], "url": c["url"],
                   "deveres": (c["triagem"] or {}).get("deveres", ""), "cita_catalogo": c["cita_catalogo"]}
                  for c in minhas]
        pend = sum(1 for c in minhas if c["status"] == "nova")
        cur = [r for r, c in zip(resumo, minhas, strict=True) if c["status"] == "relevante"]
        apr = [r for r, c in zip(resumo, minhas, strict=True) if c["status"] == "aprovada"]
        if not conectores:
            estado = "sem_fonte"
        elif len(lidas) < len(conectores):
            estado = "nao_buscada"
        elif pend:
            estado = "triagem_pendente"
        elif cur:
            estado = "curadoria_pendente"
        elif apr:
            estado = "extracao_pendente"
        else:
            estado = "coberta"
        itens.append(ItemCobertura(
            nec.jurisdicao, nec.tipo_ativo, [f"{e} / {a}" if empresa_id is None else a for e, a in ativos],
            lidas, not conectores, list(cfg.get("lacunas", {}).get(nec.jurisdicao, [])),
            normas_do_catalogo(conn, nec.jurisdicao, nec.tipo_ativo), pend, cur, apr, estado))
    return itens


ROTULOS_ESTADO = {
    "sem_fonte": "sem fonte automática: cobertura não verificada",
    "nao_buscada": "fonte ainda não lida",
    "triagem_pendente": "candidatas esperando a triagem",
    "curadoria_pendente": "normas relevantes esperando a curadoria",
    "extracao_pendente": "aprovadas pela curadoria, esperando a extração das obrigações",
    "coberta": "fontes automáticas lidas, nada relevante fora do catálogo (as lacunas conhecidas seguem abertas)",
}
# Só estes dizem que a fonte foi lida de ponta a ponta: "sem fonte" e "não lida" nunca são cobertura.
VERIFICADOS = ("triagem_pendente", "curadoria_pendente", "extracao_pendente", "coberta")

ROTULOS_STATUS = {
    "nova": "esperando triagem",
    "relevante": "esperando curadoria",
    "irrelevante": "descartada pela IA",
    "catalogada": "já no catálogo",
    "aprovada": "aprovada, falta extrair",
    "descartada": "descartada pela curadoria",
}


# ------------------------------------------------------------------- demo


def exportar(conn, destino: Path = DEMO) -> int:
    """A fila de hoje vira a da demo: buscas e candidatas (dado público, sem nada de cliente)."""
    buscas = [dict(r) for r in conn.execute("SELECT * FROM descoberta_busca ORDER BY fonte")]
    cands = [dict(r) for r in conn.execute("SELECT * FROM norma_candidata ORDER BY chave")]
    conn.commit()
    for c in cands:
        c.pop("id", None)
    destino.write_text(json.dumps({"buscas": buscas, "candidatas": cands}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    return len(cands)


def semear(conn, origem: Path = DEMO) -> int:
    """Num banco novo, carrega a fila da demo sem sobrescrever o que a curadoria já decidiu."""
    if not origem.exists():
        return 0
    dados = json.loads(origem.read_text(encoding="utf-8"))
    with conn:
        for b in dados.get("buscas", []):
            conn.execute("INSERT INTO descoberta_busca (fonte, jurisdicao, desde, ate, lidas, candidatas, em) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (fonte) DO NOTHING",
                         tuple(b[k] for k in ("fonte", "jurisdicao", "desde", "ate", "lidas", "candidatas", "em")))
        cols = ("chave", "jurisdicao", "fonte", "tipo", "numero", "ano", "titulo", "ementa", "indexacao", "data",
                "url", "situacao", "temas", "triagem", "status", "decidida_por", "decidida_em", "nota")
        for c in dados.get("candidatas", []):
            conn.execute(f"INSERT INTO norma_candidata ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
                         "ON CONFLICT (chave) DO NOTHING", tuple(c.get(k) for k in cols))
        marcar_catalogadas(conn)
    return len(dados.get("candidatas", []))


# ------------------------------------------------------------------- CLI


def _empresa_id(conn, nome: str | None) -> int | None:
    if not nome:
        return None
    r = conn.execute("SELECT id FROM empresa WHERE nome = ? OR CAST(id AS TEXT) = ?", (nome, nome)).fetchone()
    if r is None:
        raise ErroDescoberta(f"empresa não encontrada: {nome}")
    return r["id"]


def _imprimir_cobertura(itens: list[ItemCobertura]) -> None:
    for i in itens:
        print(f"\n## {i.tipo_ativo} — {nome_jurisdicao(i.jurisdicao)}: {ROTULOS_ESTADO[i.estado]}")
        print(f"   ativos: {', '.join(i.ativos)}")
        for f in i.fontes:
            print(f"   fonte: {NOMES_FONTES[f['fonte']]} ({f['cobre']}), {f['desde']}–{f['ate']}, lida em {f['em']}")
        for lac in i.lacunas:
            print(f"   lacuna conhecida: {lac}")
        print(f"   no catálogo: {', '.join(i.catalogadas) or 'nada'}")
        if i.triagem_pendente:
            print(f"   esperando triagem: {i.triagem_pendente}")
        for c in i.em_curadoria:
            altera = f" [cita {', '.join(c['cita_catalogo'])}: conferir o texto consolidado]" if c["cita_catalogo"] else ""
            print(f"   curadoria: {c['titulo']} — {c['deveres'] or c['ementa'][:120]}{altera}")
        for c in i.aprovadas:
            print(f"   aprovada, falta extrair: {c['titulo']}")


def main(argv: list[str]) -> int:
    from .impacto import CACHE_IA

    if not argv or argv[0] not in ("buscar", "triar", "cobertura", "decidir", "exportar"):
        print(__doc__)
        return 2
    conn = db.conectar(db.DB_PADRAO)
    cmd, resto = argv[0], argv[1:]
    if cmd == "buscar":
        desde = int(resto[resto.index("--desde") + 1]) if "--desde" in resto else None
        fontes = tuple(resto[resto.index("--fontes") + 1].split(",")) if "--fontes" in resto else tuple(FONTES)
        for r in buscar(conn, Baixador(), fontes, desde):
            print(f"{r.fonte}: {r.lidas} normas lidas, {r.candidatas} candidatas, {r.revogadas} revogadas e "
                  f"{r.pela_regra} sem dever (crédito, homenagem...) fora"
                  + (f"; FALHAS: {r.falhas}" if r.falhas else ""))
    elif cmd == "triar":
        limite = int(resto[resto.index("--limite") + 1]) if "--limite" in resto else None
        paralelo = int(resto[resto.index("--paralelo") + 1]) if "--paralelo" in resto else 4
        print(triar(conn, Roteador(db.conectar(CACHE_IA)), limite, paralelo=paralelo,
                    novo_roteador=lambda: Roteador(db.conectar(CACHE_IA)), texto=Baixador().texto,
                    revisar="--revisar" in resto))
    elif cmd == "cobertura":
        _imprimir_cobertura(cobertura(conn, _empresa_id(conn, resto[0] if resto else None)))
    elif cmd == "decidir":
        if len(resto) < 3:
            print("uso: decidir CHAVE aprovar|descartar QUEM [NOTA]")
            return 2
        d = decidir(conn, resto[0], resto[1], resto[2], " ".join(resto[3:]) or None)
        print(f"{d['chave']}: {d['status']}")
    else:
        print(f"{exportar(conn)} candidatas em {DEMO}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
