"""Os números que a documentação e o roteiro da demo citam batem com o cadastro."""

import csv
import re
from pathlib import Path

import pytest

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
    """O roteiro manda apontar os números do topo da caixa de entrada; eles saem do painel da demo."""
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
    assert cfg["client"]["toolbarMode"] == "minimal"     # sem botão "Deploy" na demo


def test_imagens_dos_documentos_existem():
    import re

    for doc in [RAIZ / "README.md", *(RAIZ / "docs").glob("*.md")]:
        for img in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", doc.read_text(encoding="utf-8")):
            assert (doc.parent / img).is_file(), f"{doc.name}: {img}"
    assert len(re.findall(r"!\[", (RAIZ / "README.md").read_text(encoding="utf-8"))) >= 2


def test_todos_os_exemplos_estao_documentados():
    from regulaia import exemplos

    arquitetura = (RAIZ / "docs" / "ARQUITETURA.md").read_text(encoding="utf-8")
    faltando = [n for n in exemplos.DOCS if f"`{n}`" not in arquitetura]
    assert not faltando, f"documente em ARQUITETURA.md: {faltando}"


def test_roteiro_so_cita_o_que_existe_na_tela():
    """Botões e abas em negrito no roteiro existem no app; os PDFs citados existem nos exemplos."""
    import re

    from regulaia import exemplos

    roteiro = (RAIZ / "docs" / "ROTEIRO_DEMO.md").read_text(encoding="utf-8")
    app = (RAIZ / "app.py").read_text(encoding="utf-8")
    nao_sao_rotulos = {"Fala:", "B3 · Barragem Córrego Fundo", "26/12/2029"}
    rotulos = [r.lstrip("📄📨 ") for r in re.findall(r"\*\*([^*]+)\*\*", roteiro) if r not in nao_sao_rotulos]
    assert len(rotulos) >= 8
    assert not [r for r in rotulos if r not in app], "rótulo do roteiro que não existe no app.py"
    for r in re.findall(r'"([^"]+)"', roteiro[:roteiro.index("**Fala:**")]):
        assert r in app, r
    pdfs = re.findall(r"`([^`]+\.pdf)`", roteiro)
    assert len(pdfs) >= 5
    assert not [n for n in pdfs if n not in exemplos.DOCS], "PDF do roteiro que não existe nos exemplos"


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
               "tests/fixtures/dou/S01_amostra.zip", ".streamlit/config.toml", "uv.lock", ".env.example",
               "assets/marca.svg", "assets/logo_claro.svg", "assets/logo_escuro.svg", "data/posicoes_demo.json"]
    for f in precisa:
        assert (RAIZ / f).exists(), f
        assert not _ignorado_no_docker(f, padroes), f"{f} ficaria fora da imagem"
    for f in [".env", ".env.local", "data/raw/sigbm.csv", "data/regulaia.db", ".git/config", ".venv/x",
              "docs/img/torre_hoje.png"]:
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


def test_custos_citados_batem_com_o_que_foi_gasto():
    """Custos de extração na ARQUITETURA e no roteiro vêm de data/extraido/*.json (o que a IA cobrou)."""
    import json

    def usd(x: float, casas: int = 3) -> str:
        return f"US$ {x:.{casas}f}".replace(".", ",")

    arq = (RAIZ / "docs" / "ARQUITETURA.md").read_text(encoding="utf-8")
    roteiro = (RAIZ / "docs" / "ROTEIRO_DEMO.md").read_text(encoding="utf-8")
    custo = {n: json.loads((RAIZ / "data" / "extraido" / f"{n}.json").read_text(encoding="utf-8"))["custo_usd"]
             for n in ("res95_2022", "nr13", "nr22")}
    assert f"Res. ANM 95/2022 (norma inteira) | 1 vez por norma | {usd(custo['res95_2022'])} |" in arq
    assert f"NR-13 | 1 vez por norma | {usd(custo['nr13'])} |" in arq
    assert f"NR-22 (capítulo de barragens) | 1 vez por norma | {usd(custo['nr22'])} |" in arq
    assert f"Res. 95 inteira custou {usd(custo['res95_2022'])}. A NR-13, {usd(custo['nr13'])}" in roteiro
    radar = json.loads((RAIZ / "data" / "radar_demo.json").read_text(encoding="utf-8")) \
        if (RAIZ / "data" / "radar_demo.json").exists() else None
    assert "| Analisar o impacto de um ato candidato do DOU | ~2 mil tokens de entrada | US$ 0,0005 a 0,003 |" in arq
    assert "Cada análise custou menos de meio centavo de dólar" in roteiro
    if radar:      # gerado por demo.preparar (fora do Git): por ato, a análise fica na faixa citada
        for r in radar:
            assert 0.0005 <= r.get("custo_original_usd", r["custo_usd"]) <= 0.003, r["ato"]


def test_o_que_o_app_importa_esta_nas_dependencias_de_producao():
    """A imagem Docker instala só [project].dependencies (uv sync --no-dev): tudo que o app,
    a regulaia e o coletor importam de fora tem de estar lá, senão a tela quebra só na nuvem."""
    import ast
    import sys
    import tomllib

    pacote = {"bs4": "beautifulsoup4", "dotenv": "python-dotenv", "PIL": "pillow",   # módulo -> nome no PyPI
              "botocore": "boto3", "starlette": "fastapi", "pydantic": "fastapi",
              "multipart": "python-multipart"}                                             # o botocore vem com o boto3
    deps = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    nomes = {d.split(">")[0].split("=")[0].split("<")[0].split("[")[0].strip().lower() for d in deps}
    locais = {"regulaia", "collector", "app", "api"}
    faltando = set()
    for arq in [RAIZ / "app.py", *(RAIZ / "regulaia").glob("*.py"), *(RAIZ / "collector").glob("*.py"),
                *(RAIZ / "api").rglob("*.py")]:
        for no in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Import):
                mods = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom) and not no.level:
                mods = [no.module]
            else:
                continue
            for m in mods:
                raiz = m.split(".")[0]
                if raiz in sys.stdlib_module_names or raiz in locais:
                    continue
                if pacote.get(raiz, raiz).lower() not in nomes:
                    faltando.add(f"{arq.name}: {raiz}")
    assert not faltando, f"falta em [project].dependencies: {sorted(faltando)}"


def test_requirements_txt_acompanha_o_uv_lock():
    """O Streamlit Community Cloud instala pelo requirements.txt; ele sai do uv.lock com
    `uv export --no-dev --no-hashes --no-emit-project --format requirements-txt -o requirements.txt`.
    Cada pacote travado no uv.lock (fora os de desenvolvimento) tem de estar lá na mesma versão."""
    import re
    import tomllib

    req = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
    fixados = dict(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", req, re.M))
    fixados = {k.lower(): v for k, v in fixados.items()}
    proj = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    diretos = {re.split(r"[<>=!~\[ ]", d, maxsplit=1)[0].lower() for d in proj}
    trava = {p["name"].lower(): p["version"]
             for p in tomllib.loads((RAIZ / "uv.lock").read_text(encoding="utf-8"))["package"] if "version" in p}
    assert diretos <= fixados.keys(), diretos - fixados.keys()
    diferentes = {n: (fixados[n], trava[n]) for n in fixados if n in trava and fixados[n] != trava[n]}
    assert not diferentes, f"requirements.txt desatualizado, rode o uv export: {diferentes}"


def test_caminhos_no_codigo_com_a_mesma_caixa_do_disco():
    """Windows não distingue 'Exemplos' de 'exemplos'; o Linux da imagem Docker distingue.
    Todo nome de arquivo ou pasta citado no código tem de bater letra por letra com o disco."""
    import re

    ignorar = {".venv", ".git", "__pycache__", ".pytest_cache"}
    nomes: dict[str, set[str]] = {}
    for p in RAIZ.rglob("*"):
        rel = p.relative_to(RAIZ)
        if ignorar & set(rel.parts):
            continue
        for parte in rel.parts:
            nomes.setdefault(parte.lower(), set()).add(parte)
        assert rel.as_posix().isascii(), f"nome de arquivo com acento: {rel}"
    citado = re.compile(r"""["']([\w./-]+\.(?:csv|json|pdf|zip|toml|txt|sql|md|py))["']|/\s*["']([\w.-]+)["']""")
    errados = []
    for arq in [RAIZ / "app.py", *(RAIZ / "regulaia").glob("*.py"), *(RAIZ / "collector").glob("*.py"),
                *(RAIZ / "api").rglob("*.py")]:
        for m in citado.finditer(arq.read_text(encoding="utf-8")):
            for parte in (m.group(1) or m.group(2)).split("/"):
                variantes = nomes.get(parte.lower())
                if variantes and parte not in variantes:
                    errados.append(f"{arq.name}: {parte} (no disco: {sorted(variantes)})")
    assert not errados, errados
    colisoes = [v for v in nomes.values() if len(v) > 1]
    assert not colisoes, f"nomes que só diferem na caixa: {colisoes}"


def test_numeros_do_pitch_saem_dos_dados():
    """docs/PITCH.md: mercado do SIGBM, conta da receita com as premissas da aba Mercado, números da demo."""
    import json
    from collections import Counter
    from datetime import date

    from regulaia import agenda, db, demo, torre

    pitch = (RAIZ / "docs" / "PITCH.md").read_text(encoding="utf-8")
    m = json.loads((RAIZ / "data" / "mercado_sigbm.json").read_text(encoding="utf-8"))
    alerta = sum(n for nivel, n in m["pnsb_por_nivel_emergencia"].items() if nivel != "Sem emergência")
    assert f"As {m['empresas_com_barragem_na_pnsb']} empresas com barragem" in pitch
    assert f"{m['barragens_na_pnsb']} barragens, vão refazer" in pitch
    assert f"Hoje, {alerta} dessas barragens estão em nível de alerta ou emergência" in pitch
    assert f"as outras {m['barragens_mineracao'] - m['barragens_na_pnsb']} barragens de mineração" in pitch

    # premissas = valores iniciais da aba Mercado no app.py
    app = (RAIZ / "app.py").read_text(encoding="utf-8")
    assert '"Preço por barragem por mês (R$)", 0, 50_000, 1_500' in app
    assert '"Outros ativos por barragem", 0, 50, 5' in app
    assert '"Preço por outro ativo por mês (R$)", 0, 10_000, 150' in app
    assert '"Adoção entre as barragens na PNSB (%)", 1, 100, 10)' in app
    anual = m["barragens_na_pnsb"] * (1500 + 5 * 150) * 12
    assert f"R$ {anual / 1e6:.1f} milhões por ano".replace(".", ",") in pitch
    assert f"com 10% de adoção, R$ {anual * 0.10 / 1e6:.1f} milhão".replace(".", ",") in pitch
    assert f"Conta: {m['barragens_na_pnsb']} × (R$ 1.500 + 5 × R$ 150) × 12" in pitch

    # números da demo
    conn = db.conectar(":memory:")
    demo.montar(conn)
    n = Counter(l.status for l in torre.painel(conn, 1, date(2026, 11, 7), date(2026, 5, 1)))
    assert (f"{n[agenda.ATRASADA]} atrasadas, {n[torre.DADO_FALTANDO]} dado faltando, "
            f"{n[agenda.VENCE_LOGO]} vencendo") in pitch
    ativos = conn.execute("SELECT COUNT(*) FROM ativo").fetchone()[0]
    assert f"{ativos} ativos, 72 obrigações de 5 normas" in pitch
    for trecho in ("7.884 atos → 825 da ANM → 2 para a IA → 1 muda o cadastro", "99,97%", "US$ 0,065",
                   "os 66 trechos", "menos de meio centavo de dólar"):
        assert trecho in pitch, trecho

    # abertura e mercado: embargo, dano potencial e grupos saem do SIGBM
    emb = m["pnsb_por_embargo"]
    ja = emb["Embargada"] + emb["Desembargada"]
    assert f'"{ja} de {m["barragens_na_pnsb"]}"' in pitch
    assert f"{m['barragens_na_pnsb']} barragens de mineração que a lei" in pitch
    assert f"{ja} já foram embargadas, quase metade. {emb['Embargada']} estão embargadas hoje" in pitch
    assert 0.45 < ja / m["barragens_na_pnsb"] < 0.5
    faixas = m["grupos_por_raiz_cnpj"]["por_faixa_de_barragens"]
    entrada = faixas["2 a 4"]["barragens"] + faixas["5 a 9"]["barragens"]
    assert (f"{m['barragens_mineracao']} → {m['barragens_na_pnsb']} → {entrada} → "
            f"{round(m['barragens_na_pnsb'] * 0.10)} barragens") in pitch
    fisc = json.loads((RAIZ / "data" / "fiscalizacao_anm.json").read_text(encoding="utf-8"))
    assert f"só em {fisc['ano']} a ANM lavrou {fisc['autos_de_embargo']} autos de embargo" in pitch
    assert f"{fisc['ano']}: {fisc['autos_de_embargo']} autos de embargo. Fonte: ANM" in pitch
    assert f"pelos {faixas['2 a 4']['grupos'] + faixas['5 a 9']['grupos']} grupos que têm de 2 a 9" in pitch

    # "mais de 170 testes" no slide 6 (funções de teste, sem contar os casos parametrizados)
    testes = sum(len(re.findall(r"^def test_", f.read_text(encoding="utf-8"), re.M))
                 for f in (RAIZ / "tests").glob("test_*.py"))
    assert "mais de 170 testes" in pitch and testes > 170, testes


def test_pitch_cabe_em_cinco_minutos():
    """Falas e narração do docs/PITCH.md: até 750 palavras, 5 min a 150 palavras por minuto."""
    pitch = (RAIZ / "docs" / "PITCH.md").read_text(encoding="utf-8")
    falas = re.findall(r'\*\*(?:Fala|Narração):\*\* "([^"]+)"', pitch)
    assert len(falas) >= 14, len(falas)
    palavras = sum(len(f.split()) for f in falas)
    assert palavras <= 750, palavras
    assert f"cerca de {round(palavras, -1)} palavras" in pitch, palavras


def test_git_nao_versiona_segredo_nem_cpf():
    """O que vai para o GitHub: nada de .env, export bruto do SIGBM (tem CPF), banco ou cache local;
    nenhum arquivo versionado com cara de chave de API ou de CPF formatado."""
    import re
    import shutil
    import subprocess

    if not shutil.which("git") or not (RAIZ / ".git").exists():
        pytest.skip("fora de um clone do Git")
    versionados = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True,
                                 check=True).stdout.splitlines()
    proibidos = re.compile(r"(^|/)\.env$|(^|/)\.env\.(?!example$)|^data/raw/|^cache/|\.db$|\.pem$")
    assert not [f for f in versionados if proibidos.search(f)]
    chave = re.compile(r"sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|_API_KEY\s*=\s*\S{8,}")
    cpf = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
    for f in versionados:
        caminho = RAIZ / f
        if caminho.suffix.lower() in {".pdf", ".zip", ".png", ".db"} or not caminho.is_file():
            continue
        texto = caminho.read_text(encoding="utf-8", errors="ignore")
        assert not chave.search(texto), f"parece chave de API: {f}"
        assert not cpf.search(texto), f"parece CPF: {f}"


def test_numeros_da_analise_de_mercado_saem_dos_dados():
    """docs/ANALISE_MERCADO.md: cada número do SIGBM sai de data/mercado_sigbm.json; a receita, das premissas
    da aba Mercado; as entregas por barragem, do cadastro da demo."""
    import json
    from datetime import date

    from regulaia import agenda, db, demo

    doc = (RAIZ / "docs" / "ANALISE_MERCADO.md").read_text(encoding="utf-8")
    m = json.loads((RAIZ / "data" / "mercado_sigbm.json").read_text(encoding="utf-8"))
    pnsb = m["barragens_na_pnsb"]
    emb = m["pnsb_por_embargo"]
    ja = emb["Embargada"] + emb["Desembargada"]
    assert (f"Das {pnsb} barragens de mineração na Política Nacional de Segurança de Barragens (PNSB), "
            f"{emb['Embargada']} estão embargadas hoje e outras {emb['Desembargada']} já foram embargadas e "
            f"liberadas: {ja} ({round(100 * ja / pnsb)}%) passaram por embargo") in doc
    alto = m["pnsb_dpa_alto"]
    assert f"{alto['empresas']} deles têm barragem de dano potencial alto ({alto['barragens']} barragens, " \
           f"{alto['em_mg']} em Minas Gerais)" in doc
    assert f"| Na PNSB com dano potencial alto | {alto['barragens']} | {alto['empresas']} grupos |" in doc
    assert f"| Dano potencial alto em Minas Gerais | {alto['em_mg']} |" in doc
    assert f"| Embargadas hoje | {emb['Embargada']} |" in doc
    alerta = sum(n for k, n in m["pnsb_por_nivel_emergencia"].items() if k != "Sem emergência")
    assert f"| Em nível de alerta ou emergência | {alerta} |" in doc
    assert f"| Na PNSB | {pnsb} | {m['empresas_com_barragem_na_pnsb']} empresas " \
           f"({m['grupos_por_raiz_cnpj']['total']} grupos pela raiz do CNPJ) |" in doc
    assert f"| Barragens de mineração cadastradas | {m['barragens_mineracao']} | {m['empresas']} empresas |" in doc
    assert f"| Na PNSB em Minas Gerais | {m['mg']['barragens_na_pnsb']} | " \
           f"{m['mg']['empresas_com_barragem_na_pnsb']} empresas |" in doc
    sit = m["pnsb_por_situacao"]
    assert f"Situação das {pnsb}: {sit['Ativa']} ativas, {sit['Em descaracterização']} em descaracterização" in doc
    assert f"| Barragens de mineração fora da PNSB | {m['barragens_mineracao'] - pnsb} | SIGBM |" in doc

    g = m["grupos_por_raiz_cnpj"]
    for faixa, v in g["por_faixa_de_barragens"].items():
        assert f"| {faixa} | {v['grupos']} | {v['barragens']} |" in doc, faixa
    assert (f"o maior grupo tem {g['maior_grupo_barragens']} barragens "
            f"({round(100 * g['maior_grupo_barragens'] / pnsb)}%); os 10 maiores têm {g['top10_barragens']} "
            f"({round(100 * g['top10_barragens'] / pnsb)}%)") in doc
    meio = [g["por_faixa_de_barragens"][k] for k in ("2 a 4", "5 a 9")]
    assert f"soma {sum(v['grupos'] for v in meio)} grupos e {sum(v['barragens'] for v in meio)} barragens" in doc

    # TAM, SAM e SOM: barragens do SIGBM × R$ 27 mil por ano (premissas da aba Mercado)
    por_barragem = (1500 + 5 * 150) * 12
    mi = lambda x: f"{x / 1e6:.1f}".replace(".", ",")  # noqa: E731
    entrada = sum(v["barragens"] for v in meio)
    som = round(pnsb * 0.10)
    assert f"| {m['barragens_mineracao']} | R$ {mi(m['barragens_mineracao'] * por_barragem)} milhões |" in doc
    assert f"| {pnsb} | R$ {mi(pnsb * por_barragem)} milhões |" in doc
    assert f"| {entrada} | R$ {mi(entrada * por_barragem)} milhões |" in doc
    assert f"cerca de {round(som / (entrada / sum(v['grupos'] for v in meio)))} dos 59 grupos | {som} | "            f"R$ {mi(som * por_barragem)} milhão |" in doc
    # fiscalização da ANM: números do relatório guardados em data/fiscalizacao_anm.json
    fisc = json.loads((RAIZ / "data" / "fiscalizacao_anm.json").read_text(encoding="utf-8"))
    assert f"Só em {fisc['ano']} a ANM lavrou {fisc['autos_de_embargo']} autos de embargo" in doc
    for linha in (f"| Vistorias em campo | {fisc['vistorias_em_campo']} "
                  f"({fisc['vistorias_em_barragens_pnsb']} em barragens da PNSB) |",
                  f"| Autos de infração | cerca de {fisc['autos_de_infracao_aprox']} |",
                  f"| Multas | {fisc['multas']} |",
                  f"| Autos de embargo | {fisc['autos_de_embargo']} |",
                  f"cerca de 1 auto de embargo para cada {round(pnsb / fisc['autos_de_embargo'])} barragens",
                  fisc["suspensao_das_multas"]["ato"],
                  f"contra {fisc['relacao_52_2026']['responsaveis']} responsáveis"):
        assert linha in doc, linha
    # custo do problema: 4 barragens, R$ 13,9 mil × 1,8 ÷ 168 h ≈ R$ 150/h, de 6 a 20 h por semana
    hora = round(13_900 * 1.8 / 168, -1)
    assert hora == 150
    assert f"De R$ {round(6 * hora * 52 / 1000)} mil a R$ {round(20 * hora * 52 / 1000)} mil por ano" in doc
    assert f"| R$ {4 * por_barragem // 1000} mil por ano |" in doc

    # receita: mesma conta e premissas do pitch e da aba Mercado
    br = lambda v: f"{v:.2f}".replace(".", ",")  # noqa: E731
    for preco in (1000, 1500, 2500):
        anual = pnsb * (preco + 5 * 150) * 12 / 1e6
        assert f"| R$ {preco:,} | ".replace(",", ".") + " | ".join(
            f"R$ {br(anual * a)} mi" for a in (0.05, 0.10, 0.25, 1)) + " |" in doc, preco
    assert f"Conta: {pnsb} × (R$ 1.500 + 5 × R$ 150) × 12 = **R$ 12,4 milhões por ano**" in doc

    # entregas por ano: o cadastro da demo
    conn = db.conectar(":memory:")
    demo.montar(conn)
    por_barragem = []
    for a in db.ativos(conn, 1):
        if not a["codigo"].startswith("B"):
            continue
        obs = [o.vigente for o in db.obrigacoes_do_ativo(conn, a["id"], em="2026-06-01") if o.vigente]
        n = 0
        for v in obs:
            try:
                n += len(agenda.periodos(v["agenda"], date(2026, 1, 1), date(2026, 12, 31)))
            except agenda.AgendaInvalida:
                pass
        por_barragem.append((len(obs), n))
    assert f"de {min(o for o, _ in por_barragem)} a {max(o for o, _ in por_barragem)} obrigações e de " \
           f"{min(n for _, n in por_barragem)} a {max(n for _, n in por_barragem)} entregas com data por ano" in doc
    assert all(59 <= n <= 61 for _, n in por_barragem)             # "cerca de 60" continua verdade
    mil = f"{pnsb * 60 / 1000:.1f}".replace(".", ",")
    assert f"{pnsb} barragens × cerca de 60 entregas = **cerca de {mil} mil entregas datadas por ano**" in doc
