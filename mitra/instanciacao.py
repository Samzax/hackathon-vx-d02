"""Instanciação: levar uma cliente nova do zero até a torre funcionando.

A **base padrão** vale para todo cliente (catálogo de normas públicas, SIGBM público, descoberta,
vigência). Aqui fica a **base personalizada** de cada empresa: os ativos que o SIGBM não traz, as
unidades (operações), as licenças e condicionantes, os responsáveis técnicos, quem vê o quê dentro da
empresa e as regras próprias dela. Ninguém edita CSV à mão.

Oito etapas, cada uma com estado (`pendente`, `em_andamento`, `pronta`) tirado **dos dados**, não de um
número inventado; quem fez o quê e quando fica em `instanciacao_evento`:

 1. `cadastro`      CNPJ, razão social, UFs; as barragens do CNPJ no SIGBM que entram (ou nenhuma)
 2. `ativos`        o resto: minas, usinas, pilhas, equipamentos, licenças — formulário ou planilha
 3. `dados`         o que as regras do catálogo pedem e ninguém informou: lista de tarefas, não bloqueio
 4. `cobertura`     `descoberta.cobertura` assim que há ativos: o que vale e o que falta no catálogo
 5. `licencas`      PDF da licença ou do alvará -> condicionantes propostas com trecho conferido -> a dona
                    aprova; e o checklist municipal: alvarás e exigências municipais da sede e de cada
                    unidade (legislação municipal não tem fonte automática: entra pela implantação)
 6. `responsaveis`  responsável técnico e coordenador do PAEBM (CPF cifrado, ver `pessoal.py`)
 7. `contas`        a primeira conta da cliente (senha provisória) e as demais, com escopo por unidade
 8. `operacao`      resumo e "entrar em operação": grava `monitorado_desde` e a torre passa a valer

"Entrar em operação" aceita pendência: ela continua visível. O que a empresa não informou nunca é
presumido (a torre mostra "dado faltando"), e nada de dado pessoal sai daqui para a IA ou para o Git.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import date

from . import campos, db

# ------------------------------------------------------------------ as etapas

CADASTRO, ATIVOS, DADOS, COBERTURA = "cadastro", "ativos", "dados", "cobertura"
LICENCAS, RESPONSAVEIS, CONTAS, OPERACAO = "licencas", "responsaveis", "contas", "operacao"
ETAPAS = (CADASTRO, ATIVOS, DADOS, COBERTURA, LICENCAS, RESPONSAVEIS, CONTAS, OPERACAO)

PENDENTE, EM_ANDAMENTO, PRONTA = "pendente", "em_andamento", "pronta"

TITULOS = {
    CADASTRO: "Cadastro da empresa",
    ATIVOS: "Ativos e unidades",
    DADOS: "Dados que faltam",
    COBERTURA: "Cobertura normativa",
    LICENCAS: "Licenças e condicionantes",
    RESPONSAVEIS: "Responsáveis técnicos",
    CONTAS: "Contas e acessos",
    OPERACAO: "Revisão e entrada em operação",
}

# o que cada etapa pede, em português, para a tela e para o agente
O_QUE_FALTA = {
    CADASTRO: "informe CNPJ, razão social e as UFs em que a empresa opera",
    ATIVOS: "cadastre os ativos (barragens do SIGBM, minas, usinas, pilhas, equipamentos e licenças)",
    DADOS: "complete no cadastro dos ativos o que as regras do catálogo pedem",
    COBERTURA: "cadastre ao menos um ativo para a cobertura normativa ser calculada",
    LICENCAS: "envie o PDF das licenças e alvarás, aprove as condicionantes propostas e confirme as "
              "exigências municipais da sede e de cada unidade",
    RESPONSAVEIS: "informe o responsável técnico de cada unidade ou ativo",
    CONTAS: "crie a primeira conta da empresa (TI), que cria as demais",
    OPERACAO: "revise o resumo e entre em operação",
}

TIPOS_LICENCA = ("LP", "LI", "LO", "LAC", "outorga", "autorizacao", "alvara")
RENOVACAO_PADRAO = 120      # dias antes do vencimento, salvo o que a própria licença disser


class ErroInstanciacao(ValueError):
    """Pedido que deixaria a instanciação num estado ruim (sem empresa, unidade de outra, etc.)."""


@dataclass
class Etapa:
    etapa: str
    titulo: str
    estado: str
    falta: str = ""                  # o que fazer agora, vazio quando pronta
    numeros: dict[str, int] = field(default_factory=dict)
    por: str | None = None           # quem mexeu nela por último
    em: str | None = None

    @property
    def pronta(self) -> bool:
        return self.estado == PRONTA


@dataclass
class Estado:
    empresa_id: int
    empresa: str
    cnpj: str | None
    razao_social: str
    ufs: list[str]
    no_sigbm: bool
    etapas: list[Etapa]
    em_operacao: bool
    monitorado_desde: str | None
    criada_por: str
    criada_em: str

    @property
    def percentual(self) -> int:
        """Das etapas, não de um número inventado: cada pronta vale 1, cada em andamento vale 1/2."""
        pontos = sum(1.0 if e.pronta else 0.5 if e.estado == EM_ANDAMENTO else 0.0 for e in self.etapas)
        return round(100 * pontos / len(self.etapas))

    @property
    def pendencias(self) -> list[Etapa]:
        return [e for e in self.etapas if not e.pronta]


# ------------------------------------------------------------------ eventos


def registrar(conn, empresa_id: int, etapa: str, acao: str, por: str, detalhe: dict | None = None) -> None:
    """Quem fez o quê e quando, por etapa: é daqui que sai o 'por'/'em' de cada etapa na tela."""
    if etapa not in ETAPAS:
        raise ErroInstanciacao(f"etapa desconhecida: {etapa}")
    with conn:
        conn.execute("INSERT INTO instanciacao_evento (empresa_id, etapa, acao, detalhe, por, em) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     (empresa_id, etapa, acao, json.dumps(detalhe, ensure_ascii=False) if detalhe else None,
                      por, db.agora()))


def eventos(conn, empresa_id: int, etapa: str | None = None, limite: int = 200) -> list[dict]:
    sql = "SELECT * FROM instanciacao_evento WHERE empresa_id = ?"
    args: list = [empresa_id]
    if etapa:
        sql += " AND etapa = ?"
        args.append(etapa)
    return [dict(r) | {"detalhe": json.loads(r["detalhe"]) if r["detalhe"] else None}
            for r in conn.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, limite))]


def _ultimo(conn, empresa_id: int) -> dict[str, dict]:
    """O último evento de cada etapa, numa consulta só."""
    out: dict[str, dict] = {}
    for r in conn.execute("SELECT etapa, por, em FROM instanciacao_evento WHERE empresa_id = ? ORDER BY id",
                          (empresa_id,)):
        out[r["etapa"]] = {"por": r["por"], "em": r["em"]}
    return out


# ------------------------------------------------------------------ etapa 1: cadastro


def criar(conn, *, nome: str, razao_social: str, cnpj: str | None, ufs: list[str], por: str,
          no_sigbm: bool = False, ficticia: bool = False) -> int:
    """A empresa e a instanciação dela. `nome` é o que aparece na torre (UNIQUE, é por ele que contas e
    obrigações próprias se ligam); `cnpj` vazio é empreendedor pessoa física (ver `pessoal.py`)."""
    nome, razao_social = (nome or "").strip(), (razao_social or "").strip()
    if not nome:
        raise ErroInstanciacao("a empresa precisa de um nome para aparecer na torre")
    if not razao_social:
        raise ErroInstanciacao("informe a razão social")
    digitos = "".join(c for c in (cnpj or "") if c.isdigit()) or None
    if digitos and len(digitos) != 14:
        raise ErroInstanciacao(f"CNPJ {cnpj!r} não tem 14 dígitos")
    siglas = []
    for uf in ufs or []:
        try:
            siglas.append(campos.converter("uf", uf))
        except campos.ValorInvalido as e:
            raise ErroInstanciacao(str(e)) from None
    if conn.execute("SELECT 1 FROM empresa WHERE nome = ?", (nome,)).fetchone():
        raise ErroInstanciacao(f"já existe uma empresa chamada {nome!r} na torre")
    if digitos and conn.execute("SELECT 1 FROM instanciacao WHERE cnpj = ?", (digitos,)).fetchone():
        raise ErroInstanciacao(f"o CNPJ {cnpj} já está instanciado")
    with conn:
        eid = db.criar_empresa(conn, nome, ficticia=ficticia, origem="instanciação")
        conn.execute("INSERT INTO instanciacao (empresa_id, cnpj, razao_social, ufs, no_sigbm, criada_por, "
                     "criada_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (eid, digitos, razao_social, json.dumps(sorted(set(siglas))), int(no_sigbm), por, db.agora()))
    registrar(conn, eid, CADASTRO, "empresa criada", por,
              {"cnpj": digitos, "razao_social": razao_social, "ufs": sorted(set(siglas))})
    return eid


def da_empresa(conn, empresa_id: int) -> dict | None:
    r = conn.execute("SELECT i.*, e.nome, e.monitorado_desde FROM instanciacao i "
                     "JOIN empresa e ON e.id = i.empresa_id WHERE i.empresa_id = ?", (empresa_id,)).fetchone()
    return dict(r) | {"ufs": json.loads(r["ufs"])} if r else None


def instanciadas(conn) -> list[dict]:
    """Todas as instanciações, as que ainda não entraram em operação primeiro."""
    return [dict(r) | {"ufs": json.loads(r["ufs"])} for r in conn.execute(
        "SELECT i.*, e.nome, e.monitorado_desde FROM instanciacao i JOIN empresa e ON e.id = i.empresa_id "
        "ORDER BY CASE WHEN e.monitorado_desde IS NULL THEN 0 ELSE 1 END, i.criada_em")]


# ------------------------------------------------------------------ unidades (a operação)


def criar_unidade(conn, empresa_id: int, nome: str, por: str, uf: str | None = None,
                  municipio: str | None = None) -> int:
    """A operação ("Mina Serra Azul"), com as barragens e os equipamentos dela."""
    nome = (nome or "").strip()
    if not nome:
        raise ErroInstanciacao("a unidade precisa de um nome")
    if conn.execute("SELECT 1 FROM unidade WHERE empresa_id = ? AND nome = ?", (empresa_id, nome)).fetchone():
        raise ErroInstanciacao(f"a empresa já tem uma unidade chamada {nome!r}")
    sigla = None
    if uf:
        try:
            sigla = campos.converter("uf", uf)
        except campos.ValorInvalido as e:
            raise ErroInstanciacao(str(e)) from None
    with conn:
        cur = conn.execute("INSERT INTO unidade (empresa_id, nome, uf, municipio, criada_por, criada_em) "
                           "VALUES (?, ?, ?, ?, ?, ?)",
                           (empresa_id, nome, sigla, (municipio or "").strip() or None, por, db.agora()))
    registrar(conn, empresa_id, ATIVOS, f"unidade {nome}", por, {"uf": sigla, "municipio": municipio})
    return cur.lastrowid


def unidades(conn, empresa_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM unidade WHERE empresa_id = ? ORDER BY nome", (empresa_id,))]


def _unidade_valida(conn, empresa_id: int, unidade: str | None) -> str | None:
    """A unidade tem de ser da própria empresa: a de outra cliente não existe para esta."""
    nome = (unidade or "").strip()
    if not nome:
        return None
    if not conn.execute("SELECT 1 FROM unidade WHERE empresa_id = ? AND nome = ?",
                        (empresa_id, nome)).fetchone():
        raise ErroInstanciacao(f"a empresa não tem a unidade {nome!r}: crie a unidade antes")
    return nome


# ------------------------------------------------------------------ etapa 2: ativos

TIPOS_ATIVO = ("barragem", "unidade", "equipamento", "licenca", "obra")


def criar_ativo(conn, empresa_id: int, *, tipo: str, codigo: str, nome: str, por: str,
                atributos: dict | None = None, unidade: str | None = None,
                responsavel: str | None = None) -> int:
    """Um ativo da empresa, com o cadastro conferido campo a campo (`campos.conferir`)."""
    tipo = (tipo or "").strip().lower()
    if tipo not in TIPOS_ATIVO:
        raise ErroInstanciacao(f"tipo de ativo desconhecido: {tipo!r} (há: {', '.join(TIPOS_ATIVO)})")
    codigo, nome = (codigo or "").strip(), (nome or "").strip()
    if not codigo or not nome:
        raise ErroInstanciacao("o ativo precisa de código e nome")
    if db.ativo_por_codigo(conn, empresa_id, codigo):
        raise ErroInstanciacao(f"a empresa já tem o ativo {codigo}")
    nome_unidade = _unidade_valida(conn, empresa_id, unidade)
    try:
        conferidos = campos.conferir(tipo, atributos or {})
    except campos.ValorInvalido as e:
        raise ErroInstanciacao(str(e)) from None
    with conn:
        aid = db.criar_ativo(conn, empresa_id, tipo, codigo, nome, conferidos,
                             responsavel=(responsavel or "").strip() or None, unidade=nome_unidade)
    registrar(conn, empresa_id, ATIVOS, f"ativo {codigo}", por,
              {"tipo": tipo, "nome": nome, "unidade": nome_unidade})
    return aid


# ------------------------------------------------- a planilha (modelo CSV baixável)

COLUNAS_PLANILHA = ("tipo", "codigo", "nome", "unidade", "responsavel")


def modelo_csv(tipo: str = "barragem") -> str:
    """O modelo que a empresa baixa, preenche e sobe: as colunas fixas e, depois, uma por campo do
    cadastro daquele tipo de ativo, com o cabeçalho sendo o nome do campo (a pergunta vai na 2ª linha)."""
    do_tipo = campos.do_tipo(tipo)
    cabecalho = [*COLUNAS_PLANILHA, *do_tipo]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cabecalho)
    w.writerow(["# obrigatório: tipo, codigo, nome", f"ex.: {tipo[:1].upper()}1", f"ex.: {TITULOS[ATIVOS]}",
                "nome da unidade (crie antes)", "área responsável",
                *(campos.pergunta(c) for c in do_tipo)])
    return buf.getvalue()


@dataclass
class LinhaPlanilha:
    linha: int                      # número da linha no arquivo, como a pessoa vê
    tipo: str = ""
    codigo: str = ""
    nome: str = ""
    unidade: str | None = None
    responsavel: str | None = None
    atributos: dict = field(default_factory=dict)
    erro: str | None = None


def ler_planilha(conteudo: str | bytes, empresa_id: int | None = None, conn=None) -> list[LinhaPlanilha]:
    """O CSV da empresa, linha a linha, cada uma com o erro dela (nunca "o arquivo está inválido").

    A linha de comentário do modelo (começa com '#') é ignorada. Com `conn` e `empresa_id`, confere
    também a unidade e o código repetido. Nenhuma linha é gravada aqui: quem grava é `importar_planilha`,
    e só se **todas** passarem."""
    if isinstance(conteudo, bytes):
        for codec in ("utf-8-sig", "latin-1"):      # Excel do Brasil salva em qualquer dos dois
            try:
                conteudo = conteudo.decode(codec)
                break
            except UnicodeDecodeError:
                continue
    texto = str(conteudo).replace("\r\n", "\n")
    sep = ";" if texto.split("\n", 1)[0].count(";") > texto.split("\n", 1)[0].count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=sep)
    faltam = [c for c in ("tipo", "codigo", "nome") if c not in (leitor.fieldnames or [])]
    if faltam:
        return [LinhaPlanilha(linha=1, erro=f"o arquivo não tem a coluna {', '.join(faltam)}: "
                                            "baixe o modelo e preencha a partir dele")]
    out: list[LinhaPlanilha] = []
    vistos: dict[str, int] = {}
    for n, bruta in enumerate(leitor, start=2):      # 1 é o cabeçalho
        valores = {(k or "").strip(): (v or "").strip() for k, v in bruta.items() if k}
        if (valores.get("tipo") or "").startswith("#") or not any(valores.values()):
            continue                                  # a linha de ajuda do modelo e as linhas vazias
        linha = LinhaPlanilha(linha=n, tipo=valores.get("tipo", "").lower(), codigo=valores.get("codigo", ""),
                              nome=valores.get("nome", ""), unidade=valores.get("unidade") or None,
                              responsavel=valores.get("responsavel") or None)
        erros = []
        if linha.tipo not in TIPOS_ATIVO:
            erros.append(f"tipo {linha.tipo or '(vazio)'!r}: use {', '.join(TIPOS_ATIVO)}")
        if not linha.codigo:
            erros.append("código vazio")
        if not linha.nome:
            erros.append("nome vazio")
        if linha.codigo and linha.codigo in vistos:
            erros.append(f"código {linha.codigo} repetido (também na linha {vistos[linha.codigo]})")
        elif linha.codigo:
            vistos[linha.codigo] = n
        if linha.tipo in TIPOS_ATIVO:
            brutos = {k: v for k, v in valores.items() if k not in COLUNAS_PLANILHA and v}
            try:
                linha.atributos = campos.conferir(linha.tipo, brutos)
            except campos.ValorInvalido as e:
                erros.append(str(e))
        if conn is not None and empresa_id is not None:
            if linha.codigo and db.ativo_por_codigo(conn, empresa_id, linha.codigo):
                erros.append(f"a empresa já tem o ativo {linha.codigo}")
            if linha.unidade and not conn.execute(
                    "SELECT 1 FROM unidade WHERE empresa_id = ? AND nome = ?",
                    (empresa_id, linha.unidade)).fetchone():
                erros.append(f"a empresa não tem a unidade {linha.unidade!r}: crie a unidade antes")
        linha.erro = "; ".join(erros) or None
        out.append(linha)
    if not out:
        return [LinhaPlanilha(linha=1, erro="o arquivo não tem nenhuma linha preenchida")]
    return out


def importar_planilha(conn, empresa_id: int, conteudo: str | bytes, por: str) -> list[LinhaPlanilha]:
    """Importa a planilha inteira ou nada: com qualquer linha errada, ninguém entra e a empresa corrige
    o arquivo (meia importação deixaria a empresa sem saber o que entrou)."""
    linhas = ler_planilha(conteudo, empresa_id, conn)
    if any(l.erro for l in linhas):
        return linhas
    for l in linhas:
        criar_ativo(conn, empresa_id, tipo=l.tipo, codigo=l.codigo, nome=l.nome, por=por,
                    atributos=l.atributos, unidade=l.unidade, responsavel=l.responsavel)
    registrar(conn, empresa_id, ATIVOS, f"planilha com {len(linhas)} ativos", por,
              {"codigos": [l.codigo for l in linhas]})
    return linhas


# ------------------------------------------------------------------ etapa 3: dados que faltam


@dataclass
class DadoFaltando:
    ativo: str
    ativo_id: int
    ativo_nome: str
    campo: str
    pergunta: str
    obrigacoes: list[str]       # as obrigações que dependem deste dado


def dados_que_faltam(conn, empresa_id: int) -> list[DadoFaltando]:
    """Por ativo, o que as regras do catálogo pedem e ninguém informou. É lista de tarefas, não bloqueio:
    a torre mostra a obrigação como "dado faltando" e nunca presume o valor."""
    out: list[DadoFaltando] = []
    for a in db.ativos(conn, empresa_id):
        por_campo: dict[str, list[str]] = {}
        for o in db.obrigacoes_do_ativo(conn, a["id"]):
            for c in o.dados_faltando:
                por_campo.setdefault(c, []).append(o.codigo)
        for c, obrigacoes in sorted(por_campo.items()):
            out.append(DadoFaltando(ativo=a["codigo"], ativo_id=a["id"], ativo_nome=a["nome"], campo=c,
                                    pergunta=campos.pergunta(c), obrigacoes=sorted(obrigacoes)))
    return out


# ------------------------------------------------------------------ etapa 5: o checklist municipal
#
# Legislação municipal e alvarás não têm fonte automática (decisão de 7/11): entram pelo cadastro da
# empresa, na implantação. Cada local — a sede e cada unidade — responde uma pergunta: os alvarás e as
# exigências do município foram enviados? O alvará enviado em Licenças (tipo `alvara`) aparece como prova
# do local; sem ele, confirmar pede uma nota dizendo o que foi entregue. "Não se aplica" sempre pede o
# porquê. Enquanto um local está pendente, a etapa 5 não fica pronta.

SEDE = ""                                       # o local da sede; os demais são o nome da unidade
CONFIRMADO, NAO_SE_APLICA = "confirmado", "nao_se_aplica"
SITUACOES_MUNICIPAIS = (PENDENTE, CONFIRMADO, NAO_SE_APLICA)
PERGUNTA_MUNICIPAL = ("Os alvarás e as exigências do município (alvará de funcionamento, uso e ocupação do "
                      "solo, licença ambiental municipal, posturas) foram enviados?")
ROTULO_SITUACAO = {PENDENTE: "pendente", CONFIRMADO: "confirmado", NAO_SE_APLICA: "não se aplica"}


@dataclass
class ItemMunicipal:
    local: str                      # SEDE ("") ou o nome da unidade
    titulo: str                     # "Sede da empresa" ou o nome da unidade
    uf: str | None
    municipio: str | None
    alvaras: list[str]              # os números dos alvarás enviados para este local
    situacao: str = PENDENTE        # pendente, confirmado ou nao_se_aplica
    nota: str | None = None
    por: str | None = None
    em: str | None = None

    @property
    def resolvido(self) -> bool:
        return self.situacao != PENDENTE


def _alvaras_por_local(conn, empresa_id: int) -> dict[str, list[str]]:
    """Os alvarás enviados, por local: o da unidade vale para ela; o de um ativo vale para a unidade do
    ativo; o sem unidade (ou de ativo sem unidade) é da empresa, ou seja, da sede."""
    do_ativo = {a["codigo"]: (a.get("unidade") or SEDE) for a in db.ativos(conn, empresa_id)}
    out: dict[str, list[str]] = {}
    for r in conn.execute("SELECT numero, unidade, ativo_codigo FROM licenca "
                          "WHERE empresa_id = ? AND tipo = 'alvara' ORDER BY numero", (empresa_id,)):
        local = (r["unidade"] or "").strip() or do_ativo.get(r["ativo_codigo"] or "", SEDE)
        out.setdefault(local, []).append(r["numero"])
    return out


def checklist_municipal(conn, empresa_id: int) -> list[ItemMunicipal]:
    """A sede e cada unidade, com os alvarás enviados e a resposta de quem confirmou (ou pendente)."""
    alvaras = _alvaras_por_local(conn, empresa_id)
    respostas = {r["local"]: dict(r) for r in conn.execute(
        "SELECT local, situacao, nota, por, em FROM exigencia_municipal WHERE empresa_id = ?", (empresa_id,))}
    locais = [(SEDE, "Sede da empresa", None, None)] + [
        (u["nome"], u["nome"], u["uf"], u["municipio"]) for u in unidades(conn, empresa_id)]
    itens = []
    for local, titulo, uf, municipio in locais:
        r = respostas.get(local, {})
        itens.append(ItemMunicipal(local=local, titulo=titulo, uf=uf, municipio=municipio,
                                   alvaras=alvaras.get(local, []), situacao=r.get("situacao", PENDENTE),
                                   nota=r.get("nota"), por=r.get("por"), em=r.get("em")))
    return itens


def responder_municipal(conn, empresa_id: int, local: str | None, situacao: str, por: str,
                        nota: str | None = None) -> ItemMunicipal:
    """Grava a resposta de um local. `pendente` reabre (apaga a resposta). Confirmar sem alvará enviado
    para o local pede nota (o que foi entregue: protocolo, dispensa do município...); "não se aplica"
    sempre pede o porquê. Quem respondeu e quando fica no histórico da etapa 5."""
    local = (local or "").strip()
    nota = (nota or "").strip() or None
    if situacao not in SITUACOES_MUNICIPAIS:
        raise ErroInstanciacao(f"situação desconhecida: {situacao!r} (use {', '.join(SITUACOES_MUNICIPAIS)})")
    itens = {i.local: i for i in checklist_municipal(conn, empresa_id)}
    if local not in itens:
        raise ErroInstanciacao(f"a empresa não tem a unidade {local!r}: crie a unidade antes")
    item = itens[local]
    if situacao == NAO_SE_APLICA and not nota:
        raise ErroInstanciacao(f"diga por que não se aplica a {item.titulo} "
                               "(ex.: o município dispensa alvará para esta atividade)")
    if situacao == CONFIRMADO and not item.alvaras and not nota:
        raise ErroInstanciacao(f"nenhum alvará de {item.titulo} foi enviado: envie o PDF em Licenças "
                               "(tipo alvará) ou diga na nota o que foi entregue (ex.: protocolo da renovação)")
    with conn:
        if situacao == PENDENTE:
            conn.execute("DELETE FROM exigencia_municipal WHERE empresa_id = ? AND local = ?", (empresa_id, local))
        else:
            conn.execute(
                "INSERT INTO exigencia_municipal (empresa_id, local, situacao, nota, por, em) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(empresa_id, local) DO UPDATE SET "
                "situacao = excluded.situacao, nota = excluded.nota, por = excluded.por, em = excluded.em",
                (empresa_id, local, situacao, nota, por, db.agora()))
    registrar(conn, empresa_id, LICENCAS, f"exigências municipais de {item.titulo}: {ROTULO_SITUACAO[situacao]}",
              por, {"local": local, "situacao": situacao, "nota": nota, "alvaras": item.alvaras})
    return next(i for i in checklist_municipal(conn, empresa_id) if i.local == local)


# ------------------------------------------------------------------ etapa 8: entrar em operação


def entrar_em_operacao(conn, empresa_id: int, por: str, desde: date | str | None = None) -> str:
    """Grava `monitorado_desde`: daí em diante a torre cobra (o que venceu antes não vira atraso).
    Dá para entrar com pendência; ela continua visível no estado da instanciação."""
    inst = da_empresa(conn, empresa_id)
    if inst is None:
        raise ErroInstanciacao(f"a empresa {empresa_id} não tem instanciação")
    if inst["monitorado_desde"]:
        raise ErroInstanciacao(f"{inst['nome']} já está em operação desde {inst['monitorado_desde']}")
    if not db.ativos(conn, empresa_id):
        raise ErroInstanciacao("a empresa não tem nenhum ativo: a torre não teria o que cobrar")
    dia = (desde.isoformat() if isinstance(desde, date) else desde) or date.today().isoformat()
    try:
        date.fromisoformat(dia)
    except ValueError:
        raise ErroInstanciacao(f"{dia!r} não é data AAAA-MM-DD") from None
    with conn:
        conn.execute("UPDATE empresa SET monitorado_desde = ? WHERE id = ?", (dia, empresa_id))
    pendentes = [e.etapa for e in estado(conn, empresa_id).pendencias if e.etapa != OPERACAO]
    registrar(conn, empresa_id, OPERACAO, "entrou em operação", por,
              {"monitorado_desde": dia, "pendencias": pendentes})
    return dia


# ------------------------------------------------------------------ o estado das etapas


def _estado_ativos(conn, empresa_id: int) -> tuple[str, dict]:
    ativos = db.ativos(conn, empresa_id)
    nums = {"ativos": len(ativos), "unidades": len(unidades(conn, empresa_id))}
    return (PRONTA if ativos else PENDENTE), nums


def _estado_dados(conn, empresa_id: int, tem_ativos: bool) -> tuple[str, dict]:
    if not tem_ativos:
        return PENDENTE, {"faltando": 0}
    faltando = dados_que_faltam(conn, empresa_id)
    nums = {"faltando": len(faltando), "ativos_com_falta": len({d.ativo for d in faltando})}
    if not faltando:
        return PRONTA, nums
    # alguém já preencheu alguma coisa? então está em andamento, não parado
    mexeu = conn.execute("SELECT 1 FROM instanciacao_evento WHERE empresa_id = ? AND etapa = ?",
                         (empresa_id, DADOS)).fetchone()
    return (EM_ANDAMENTO if mexeu else PENDENTE), nums


def _estado_licencas(conn, empresa_id: int) -> tuple[str, dict, str]:
    """Licenças e condicionantes, mais o checklist municipal: pronta só com licença enviada, nenhuma
    condicionante esperando decisão e a sede e todas as unidades respondidas. O 'falta' diz qual parte."""
    n_lic = conn.execute("SELECT COUNT(*) FROM licenca WHERE empresa_id = ?", (empresa_id,)).fetchone()[0]
    por_status = {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM condicionante WHERE empresa_id = ? GROUP BY status",
        (empresa_id,))}
    itens = checklist_municipal(conn, empresa_id)
    pend_mun = sum(1 for i in itens if not i.resolvido)
    nums = {"licencas": n_lic, "propostas": por_status.get("pendente", 0),
            "aprovadas": por_status.get("aprovada", 0), "rejeitadas": por_status.get("rejeitada", 0),
            "municipais": len(itens), "municipais_pendentes": pend_mun}
    falta = []
    if not n_lic:
        falta.append("envie o PDF das licenças e alvarás")
    if nums["propostas"]:
        falta.append(f"decida {nums['propostas']} condicionante(s) proposta(s)")
    if pend_mun:
        falta.append(f"confirme os alvarás e exigências municipais de {pend_mun} local(is) (sede e unidades)")
    texto = "; ".join(falta)
    if not falta:
        return PRONTA, nums, ""
    if not n_lic and pend_mun == len(itens):
        return PENDENTE, nums, texto
    return EM_ANDAMENTO, nums, texto


def _estado_responsaveis(conn, empresa_id: int) -> tuple[str, dict]:
    n = conn.execute("SELECT COUNT(*) FROM responsavel_tecnico WHERE empresa_id = ?",
                     (empresa_id,)).fetchone()[0]
    # cobertos: as unidades e os ativos que já têm responsável técnico
    cobertos = {(r["unidade"], r["ativo_codigo"]) for r in conn.execute(
        "SELECT unidade, ativo_codigo FROM responsavel_tecnico WHERE empresa_id = ?", (empresa_id,))}
    com_resp = {u for u, _ in cobertos if u} | {a for _, a in cobertos if a}
    alvos = {u["nome"] for u in unidades(conn, empresa_id)} or {a["codigo"] for a in db.ativos(conn, empresa_id)}
    nums = {"responsaveis": n, "sem_responsavel": len(alvos - com_resp)}
    if not n:
        return PENDENTE, nums
    return (PRONTA if not (alvos - com_resp) else EM_ANDAMENTO), nums


def _estado_contas(conn, empresa_id: int, empresa: str) -> tuple[str, dict]:
    rows = conn.execute("SELECT papel, ativa, trocar_senha FROM usuario WHERE empresa = ?",
                        (empresa,)).fetchall()
    ativas = [r for r in rows if r["ativa"]]
    nums = {"contas": len(ativas), "provisorias": sum(1 for r in ativas if r["trocar_senha"]),
            "ti": sum(1 for r in ativas if r["papel"] == "admin")}
    if not ativas:
        return PENDENTE, nums
    # a primeira conta é a TI da empresa; enquanto ela não trocar a senha provisória, está em andamento
    if not nums["ti"] or nums["provisorias"] == nums["contas"]:
        return EM_ANDAMENTO, nums
    return PRONTA, nums


def estado(conn, empresa_id: int) -> Estado:
    """O estado das 8 etapas, tirado dos dados. `ErroInstanciacao` se a empresa não foi instanciada."""
    inst = da_empresa(conn, empresa_id)
    if inst is None:
        raise ErroInstanciacao(f"a empresa {empresa_id} não tem instanciação")
    ultimo = _ultimo(conn, empresa_id)
    est_ativos, n_ativos = _estado_ativos(conn, empresa_id)
    tem_ativos = bool(n_ativos["ativos"])
    est_dados, n_dados = _estado_dados(conn, empresa_id, tem_ativos)
    est_lic, n_lic, falta_lic = _estado_licencas(conn, empresa_id)
    est_resp, n_resp = _estado_responsaveis(conn, empresa_id)
    est_contas, n_contas = _estado_contas(conn, empresa_id, inst["nome"])
    em_operacao = bool(inst["monitorado_desde"])
    # a cobertura roda assim que há ativos: o que falta no catálogo é lacuna conhecida, não pendência
    bruto = {
        CADASTRO: (PRONTA, {"ufs": len(inst["ufs"])}),
        ATIVOS: (est_ativos, n_ativos),
        DADOS: (est_dados, n_dados),
        COBERTURA: ((PRONTA if tem_ativos else PENDENTE), {}),
        LICENCAS: (est_lic, n_lic),
        RESPONSAVEIS: (est_resp, n_resp),
        CONTAS: (est_contas, n_contas),
        OPERACAO: ((PRONTA if em_operacao else PENDENTE), {}),
    }
    faltas = {LICENCAS: falta_lic}         # a etapa 5 diz qual parte falta; as outras, o texto fixo
    etapas = [Etapa(etapa=e, titulo=TITULOS[e], estado=bruto[e][0],
                    falta="" if bruto[e][0] == PRONTA else (faltas.get(e) or O_QUE_FALTA[e]),
                    numeros=bruto[e][1],
                    por=ultimo.get(e, {}).get("por"), em=ultimo.get(e, {}).get("em")) for e in ETAPAS]
    return Estado(empresa_id=empresa_id, empresa=inst["nome"], cnpj=inst["cnpj"],
                  razao_social=inst["razao_social"], ufs=inst["ufs"], no_sigbm=bool(inst["no_sigbm"]),
                  etapas=etapas, em_operacao=em_operacao, monitorado_desde=inst["monitorado_desde"],
                  criada_por=inst["criada_por"], criada_em=inst["criada_em"])
