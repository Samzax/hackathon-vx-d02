"""Barragens reais do SIGBM: achar a mineradora pelo CNPJ ou pelo nome e montar a torre dela.

O export público do SIGBM (data/raw/sigbm/barragens.csv, fora do git) traz CPF de pessoa
física em parte das linhas. `extrair()` grava em data/sigbm_barragens_pj.csv só as linhas de
empresa (CNPJ) e só as colunas que a torre usa: sem CPF, sem nome de pessoa, sem coordenada.

O SIGBM não diz tudo que as regras pedem (DPA em pontos, trabalhadores na ZAS, mapa de
inundação validado...). Esses campos ficam de fora do ativo importado, e a torre mostra a
obrigação como "dado faltando" até alguém preencher. Nada é presumido.

    uv run python -m mitra.sigbm extrair
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import db

BRUTO = db.ROOT / "data" / "raw" / "sigbm" / "barragens.csv"
ARQUIVO = db.ROOT / "data" / "sigbm_barragens_pj.csv"
EXPORTADO_EM = "2026-11-05"
EXPORTADO_BR = "05/11/2026"

COLUNAS = {   # coluna do SIGBM -> coluna do arquivo versionado
    "Codigo": "codigo", "NomeBarragem": "barragem", "NomeEmpreendedor": "empresa",
    "CpfCnpjFormatado": "cnpj", "Municipio": "municipio", "UF": "uf", "Minerio": "minerio",
    "Altura": "altura_m", "VolumeAtualFormatado": "volume_m3",
    "MetodoConstrutivoFormatado": "metodo", "CategoriaRisco": "cri", "DanoPotencial": "dpa",
    "InseridaPNSBFormatada": "pnsb", "SituacaoNivelEmergencial": "nivel_emergencia",
    "SituacaoDeclaracaoCondicaoEstabilidade": "dce",
    "SituacaoDeclaracaoConformidadeOperacionalidade": "dco",
    "SituacaoOperacionalFormatado": "situacao", "StatusEmbargo": "embargo",
}
_CNPJ = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")

# O que o SIGBM não informa e as regras do cadastro usam: fica para a empresa preencher.
FALTAM_NO_SIGBM = {
    "dpa2": "pontuação do DPA (0 a 10) do PSB",
    "trabalhadores_zas": "há trabalhadores na Zona de Autossalvamento?",
    "mapa_inundacao_validado": "o mapa de inundação já foi validado pela ANM?",
    "alteamento_continuo": "a barragem tem alteamento contínuo?",
    "modificacao_estrutural": "houve modificação estrutural desde o último estudo de ruptura?",
}


def extrair(bruto: Path = BRUTO, destino: Path = ARQUIVO) -> int:
    """Do export bruto para o arquivo versionado: só CNPJ, só as colunas de COLUNAS."""
    with open(bruto, encoding="utf-8-sig", newline="") as f:
        linhas = [l for l in csv.DictReader(f, delimiter=";") if _CNPJ.fullmatch(l["CpfCnpjFormatado"].strip())]
    linhas.sort(key=lambda l: (l["NomeEmpreendedor"].strip(), l["NomeBarragem"].strip()))
    with open(destino, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(COLUNAS.values()))
        w.writeheader()
        for l in linhas:
            w.writerow({novo: " ".join(l[velho].split()) for velho, novo in COLUNAS.items()})
    return len(linhas)


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c)).lower()


def _digitos(t: str) -> str:
    return re.sub(r"\D", "", t)


def barragens(arquivo: Path = ARQUIVO) -> list[dict]:
    with open(arquivo, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class Empresa:
    cnpj: str
    nome: str
    barragens: list[dict] = field(default_factory=list)

    @property
    def raiz(self) -> str:
        return _digitos(self.cnpj)[:8]

    @property
    def na_pnsb(self) -> list[dict]:
        return [b for b in self.barragens if b["pnsb"] == "Sim"]


def buscar(termo: str, arquivo: Path = ARQUIVO, limite: int = 15) -> list[Empresa]:
    """CNPJ (inteiro ou só a raiz de 8 dígitos) ou pedaço do nome. Agrupa por CNPJ; as que
    têm mais barragens na PNSB vêm primeiro."""
    termo = termo.strip()
    if len(termo) < 3:
        return []
    num = _digitos(termo)
    por_numero = len(num) >= 8 and re.fullmatch(r"[\d./\-\s]+", termo)
    por_cnpj: dict[str, Empresa] = {}
    for b in barragens(arquivo):
        if por_numero:
            ok = _digitos(b["cnpj"]).startswith(num[:14])
        else:
            ok = _sem_acento(termo) in _sem_acento(b["empresa"])
        if ok:
            por_cnpj.setdefault(b["cnpj"], Empresa(b["cnpj"], b["empresa"])).barragens.append(b)
    achadas = sorted(por_cnpj.values(), key=lambda e: (-len(e.na_pnsb), -len(e.barragens), e.nome))
    return achadas[:limite]


def _numero(t: str) -> float | None:
    t = t.strip().replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _nivel(t: str) -> int:
    m = re.search(r"Emerg[eê]ncia (\d)", t)
    return int(m.group(1)) if m else 0


def _metodo(t: str) -> str | None:
    t = _sem_acento(t)
    for chave, valor in (("montante", "montante"), ("jusante", "jusante"),
                         ("linha de centro", "linha_de_centro"), ("etapa unica", "etapa_unica")):
        if chave in t:
            return valor
    return None   # "Indefinido" / "Desconhecido": melhor faltar do que chutar


def _situacao(t: str) -> str:
    t = _sem_acento(t)
    if "descaracteriza" in t:
        return "em_descaracterizacao"
    return {"ativa": "ativa", "inativa": "inativa", "em construcao": "em_construcao"}.get(t, t.replace(" ", "_"))


def atributos(b: dict) -> dict:
    """Linha do SIGBM -> atributos com os nomes das regras do cadastro. Só o que o SIGBM diz."""
    a = {
        "uf": b["uf"],
        "altura_m": _numero(b["altura_m"]),
        "volume_m3": _numero(b["volume_m3"]),
        "inserida_pnsb": b["pnsb"] == "Sim",
        "metodo_construtivo": _metodo(b["metodo"]),
        "cri": _sem_acento(b["cri"]) or None,
        "dpa": _sem_acento(b["dpa"]) or None,
        "situacao_operacional": _situacao(b["situacao"]),
        "nivel_emergencia": _nivel(b["nivel_emergencia"]),
    }
    return {k: v for k, v in a.items() if v is not None}


def alertas(b: dict) -> list[str]:
    """O que o próprio SIGBM já mostra de problema nesta barragem."""
    out = []
    if b["embargo"] == "Embargada":
        out.append("embargada no SIGBM")
    if "Alerta" in b["nivel_emergencia"] or _nivel(b["nivel_emergencia"]):
        out.append(b["nivel_emergencia"].lower())
    for sigla, st in (("DCE", b["dce"]), ("DCO", b["dco"])):
        if "Não Atestado" in st:
            out.append(f"{sigla} não atestada ({st.split(' - ')[0]})")
        elif "Não Enviado" in st:
            out.append(f"{sigla} não enviada ({st.split(' - ')[0]})")
    return out


def importar(conn, empresa: Empresa, monitorado_desde: date, so_pnsb: bool = True) -> int:
    """Cria a empresa (não fictícia) e uma barragem por linha do SIGBM. Devolve o id da empresa.
    Importar de novo a mesma empresa devolve a que já existe."""
    nome = f"{empresa.nome} ({empresa.cnpj})"
    if r := conn.execute("SELECT id FROM empresa WHERE nome = ?", (nome,)).fetchone():
        return r["id"]
    lista = empresa.na_pnsb if so_pnsb else empresa.barragens
    with conn:
        eid = db.criar_empresa(conn, nome, ficticia=False, monitorado_desde=monitorado_desde.isoformat(),
                               origem=f"SIGBM, exportação pública de {EXPORTADO_BR}")
        for b in lista:
            a = atributos(b) | {"sigbm_codigo": b["codigo"], "municipio": b["municipio"], "minerio": b["minerio"],
                                "alertas_sigbm": alertas(b)}
            db.criar_ativo(conn, eid, "barragem", f"SIGBM-{b['codigo']}", b["barragem"] or f"Barragem {b['codigo']}", a)
    return eid


def main(argv: list[str]) -> int:
    if argv[:1] == ["extrair"]:
        n = extrair()
        print(f"{n} barragens de empresa (CNPJ) -> {ARQUIVO.relative_to(db.ROOT)}")
        return 0
    if argv[:1] == ["buscar"] and len(argv) > 1:
        for e in buscar(" ".join(argv[1:])):
            print(f"{e.cnpj}  {e.nome}: {len(e.barragens)} barragens, {len(e.na_pnsb)} na PNSB")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
