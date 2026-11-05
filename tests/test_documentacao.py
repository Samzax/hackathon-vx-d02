"""Os números que a documentação e o roteiro da demo citam batem com o cadastro."""

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _linhas(caminho: Path) -> int:
    with open(caminho, encoding="utf-8", newline="") as f:
        return len(list(csv.DictReader(f)))


def test_numeros_do_cadastro_na_documentacao():
    res220 = _linhas(RAIZ / "seed_obligations.csv")
    total = res220 + sum(_linhas(p) for p in (RAIZ / "cadastro").glob("*.csv"))
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    roteiro = (RAIZ / "docs" / "ROTEIRO_DEMO.md").read_text(encoding="utf-8")
    arquitetura = (RAIZ / "docs" / "ARQUITETURA.md").read_text(encoding="utf-8")
    assert f"{total} obrigações cadastradas" in readme
    assert f"8 ativos e {total} obrigações" in roteiro
    assert f"Res. ANM 220/2025 (vale a partir de 2/8/2027) | {res220} |" in readme
    assert f"as {res220} da Res. 220/2025" in arquitetura
    assert f"Cada uma das {res220} obrigações" in arquitetura
    assert f"outras {res220 - 1} da Res. 220" in readme and f"outras {res220 - 1} da Res. 220" in roteiro
    prep = (RAIZ / "PREP.md").read_text(encoding="utf-8")
    res95 = _linhas(RAIZ / "cadastro" / "res95_2022.csv")
    assert f"`seed_obligations.csv` has {res220} obligations" in prep and f"({res95} obligations" in prep


def test_numero_de_tipos_de_documento():
    from regulaia.evidencias import DOCUMENTOS

    tipos = len(DOCUMENTOS) + 1          # + exame interno do vaso, que sai do mesmo documento
    assert f"São {tipos} tipos de documento" in (RAIZ / "docs" / "ARQUITETURA.md").read_text(encoding="utf-8")


def test_numeros_do_topo_no_roteiro():
    """O roteiro manda apontar os números do topo da aba Hoje; eles saem do painel da demo."""
    from collections import Counter
    from datetime import date

    from regulaia import agenda, db, demo, torre

    conn = db.conectar(":memory:")
    demo.montar(conn)
    n = Counter(l.status for l in torre.painel(conn, 1, date(2026, 11, 7), date(2026, 5, 1)))
    roteiro = (RAIZ / "docs" / "ROTEIRO_DEMO.md").read_text(encoding="utf-8")
    assert (f"{n[agenda.ATRASADA]} atrasadas, {n[torre.DADO_FALTANDO]} dado faltando, "
            f"{n[agenda.VENCE_LOGO]} vencendo") in roteiro


def test_config_do_streamlit():
    import tomllib

    cfg = tomllib.loads((RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["server"]["maxUploadSize"] == 20
    assert cfg["browser"]["gatherUsageStats"] is False


def test_todos_os_exemplos_estao_documentados():
    from regulaia import exemplos

    arquitetura = (RAIZ / "docs" / "ARQUITETURA.md").read_text(encoding="utf-8")
    faltando = [n for n in exemplos.DOCS if f"`{n}`" not in arquitetura]
    assert not faltando, f"documente em ARQUITETURA.md: {faltando}"


def _ignorado_no_docker(caminho: str, padroes: list[str]) -> bool:
    """Aproximação das regras do .dockerignore: último padrão que casa decide; '!' reinclui; pasta inclui o conteúdo."""
    from fnmatch import fnmatch

    ignorado = False
    for p in padroes:
        nega = p.startswith("!")
        p = p.lstrip("!").rstrip("/")
        partes = caminho.split("/")
        prefixos = ["/".join(partes[:i]) for i in range(1, len(partes) + 1)]
        if any(fnmatch(x, p) or fnmatch(x.split("/")[-1], p) and "/" not in p for x in prefixos):
            ignorado = not nega
    return ignorado


def test_imagem_docker_leva_o_que_a_demo_precisa_e_nada_secreto():
    """Sem Docker nesta máquina: confere o .dockerignore contra os arquivos que o app lê ao iniciar."""
    padroes = [l.strip() for l in (RAIZ / ".dockerignore").read_text(encoding="utf-8").splitlines()
               if l.strip() and not l.startswith("#")]
    precisa = ["app.py", "seed_obligations.csv", "cadastro/res95_2022.csv", "data/cache_ia_demo.json",
               "data/historico_serra_azul.json", "data/serra_azul.json", "data/mercado_sigbm.json",
               "tests/fixtures/dou/S01_amostra.zip", ".streamlit/config.toml", "uv.lock", ".env.example"]
    for f in precisa:
        assert (RAIZ / f).exists(), f
        assert not _ignorado_no_docker(f, padroes), f"{f} ficaria fora da imagem"
    for f in [".env", ".env.local", "data/raw/sigbm.csv", "data/regulaia.db", ".git/config", ".venv/x"]:
        assert _ignorado_no_docker(f, padroes), f"{f} entraria na imagem"


def test_readme_cita_testes_que_existem():
    """A tabela 'O que os testes garantem' só pode citar teste e arquivo que existem."""
    import re

    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    secao = readme.split("## O que os testes garantem")[1].split("\n## ")[0]
    codigo = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests").glob("test_*.py"))
    for nome in re.findall(r"`(test_\w+?)(?:…)?`", secao):
        assert f"def {nome}" in codigo, nome
    for arquivo in re.findall(r"`(tests/[\w/]+\.py)`", secao):
        assert (RAIZ / arquivo).exists(), arquivo
